"""Background tasks: geometry processing, topology extraction, and molding planning."""

import asyncio
import logging
import sys
import os
from datetime import datetime, timezone
from uuid import UUID

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))

logger = logging.getLogger(__name__)


async def _wait_for_records(session, AnalysisJob, Part, job_id, part_id):
    """Wait for DB records to exist (race with request commit)."""
    from sqlalchemy import select
    for attempt in range(10):
        r1 = await session.execute(select(AnalysisJob).where(AnalysisJob.id == UUID(job_id)))
        job = r1.scalar_one_or_none()
        r2 = await session.execute(select(Part).where(Part.id == UUID(part_id)))
        part = r2.scalar_one_or_none()
        if job and part:
            return job, part
        logger.info(f"Waiting for records (attempt {attempt+1}/10)...")
        await asyncio.sleep(1)
    return None, None


async def process_geometry_and_analyze(job_id: str, part_id: str, pull_direction: list[float]):
    """Full pipeline: parse STEP → tessellate → extract topology → generate molding plan."""
    from ..core.database import async_session
    from ..core.storage import download_file, upload_file
    from ..models.analysis import AnalysisJob
    from ..models.part import Part
    from sqlalchemy import select

    logger.info(f"Starting geometry pipeline: job={job_id} part={part_id}")
    await asyncio.sleep(1)  # Wait for request commit

    async with async_session() as session:
        try:
            job, part = await _wait_for_records(session, AnalysisJob, Part, job_id, part_id)
            if not job or not part:
                logger.error(f"Records not found after retries")
                return

            job.status = "processing"
            job.started_at = datetime.now(timezone.utc)
            job.progress = 5
            part.status = "processing"
            await session.commit()

            # Step 1: Download STEP file
            logger.info(f"Downloading STEP file: {part.file_key}")
            step_data = download_file(part.file_key)
            job.progress = 10
            await session.commit()

            # Step 2: Parse STEP (runs in thread to avoid blocking event loop)
            logger.info("Parsing STEP file...")
            loop = asyncio.get_event_loop()

            def _parse_and_process():
                from services.geometry.src.step_parser import parse_step_bytes
                from services.geometry.src.tessellator import tessellate_shape, mesh_to_glb
                from services.geometry.src.properties import extract_properties

                shape = parse_step_bytes(step_data)
                props = extract_properties(shape)
                # Tessellate with config defaults (no hardcoded values)
                mesh_data = tessellate_shape(shape)
                glb_bytes = mesh_to_glb(mesh_data["vertices"], mesh_data["normals"], mesh_data.get("indices"))
                return shape, props, mesh_data, glb_bytes

            try:
                shape, props, mesh_data, glb_bytes = await loop.run_in_executor(None, _parse_and_process)
            except Exception as e:
                raise RuntimeError(f"STEP parsing failed: {e}")

            job.progress = 40
            await session.commit()

            # Step 3: Upload GLB mesh, face map, and serialized B-Rep to storage
            import json as _json
            from services.geometry.src.topology_extractor import serialize_brep

            mesh_key = f"parts/{part_id}/mesh.glb"
            facemap_key = f"parts/{part_id}/facemap.json"
            brep_key = f"parts/{part_id}/brep.bin"
            upload_file(mesh_key, glb_bytes, "model/gltf-binary")
            upload_file(facemap_key, _json.dumps(mesh_data["face_map"]).encode(), "application/json")
            upload_file(brep_key, serialize_brep(shape), "application/octet-stream")
            tess_meta = mesh_data.get("tess_metadata", {})
            logger.info(
                f"Stored GLB: {len(glb_bytes)} bytes, "
                f"{tess_meta.get('vertex_count', '?')} verts, "
                f"{tess_meta.get('triangle_count', '?')} tris, "
                f"deflection={tess_meta.get('linear_deflection_mm', '?')}mm"
            )

            # Step 4: Update part with geometry properties
            part.mesh_key = mesh_key
            part.face_count = props.get("face_count")
            part.volume_mm3 = props.get("volume_mm3")
            part.surface_area_mm2 = props.get("surface_area_mm2")
            part.bounding_box = props.get("bounding_box")
            job.progress = 50
            await session.commit()

            # Step 4b: 3D fill-time field (voxel + fast-marching)
            # Default gate is the centre of the XY plane (the phone-case back cover).
            # See llm_wiki_for_physics/wiki/concepts/gate_optimization.md
            # Users can re-rank via /api/analysis/simulation/gate/optimize/{part_id}.
            def _compute_fill_time(verts, idx):
                from services.simulation.src.fill_time import compute_fill_time
                return compute_fill_time(verts, idx, gate="xy_center", max_grid=96)

            try:
                fill_result = await loop.run_in_executor(
                    None, _compute_fill_time,
                    mesh_data["vertices"], mesh_data.get("indices"),
                )
                fill_bin_key = f"parts/{part_id}/fill_time.bin"
                fill_meta_key = f"parts/{part_id}/fill_time.json"
                upload_file(fill_bin_key, fill_result["vertex_fill_time"].tobytes(), "application/octet-stream")
                meta = {k: v for k, v in fill_result.items() if k != "vertex_fill_time"}
                upload_file(fill_meta_key, _json.dumps(meta).encode(), "application/json")
                logger.info(
                    f"Stored fill_time: {fill_result['vertex_count']} verts, "
                    f"max={fill_result['max_time']:.1f}mm, "
                    f"grid={fill_result['voxel_grid']}"
                )
            except Exception as e:
                logger.warning(f"Fill-time computation failed (continuing): {e}", exc_info=True)

            job.progress = 55
            await session.commit()

            # Step 5: Run geometry analysis, topology extraction, and molding plan
            logger.info("Running analysis...")

            def _run_analysis():
                from services.geometry.src.face_analysis import analyze_faces
                from services.geometry.src.wall_thickness import analyze_wall_thickness
                from services.geometry.src.topology_extractor import extract_topology
                from services.molding.src import generate_molding_plan

                face_infos = analyze_faces(shape, pull_direction)
                thickness = analyze_wall_thickness(shape, num_samples=300)
                topology = extract_topology(shape, face_infos, mesh_data["face_map"])
                molding_plan = generate_molding_plan(face_infos, props, thickness, topology)

                from services.molding.src.ceramic_feasibility import analyze_ceramic_feasibility
                ceramic = analyze_ceramic_feasibility(face_infos, props, thickness, topology, molding_plan)
                return face_infos, topology, molding_plan, ceramic

            try:
                face_infos, topology, molding_plan, ceramic = await loop.run_in_executor(None, _run_analysis)
            except Exception as e:
                logger.warning(f"Analysis failed (storing geometry anyway): {e}")
                part.status = "analyzed"
                job.status = "completed"
                job.progress = 100
                job.completed_at = datetime.now(timezone.utc)
                job.error_message = f"Analysis failed: {e}"
                await session.commit()
                return

            job.progress = 85
            await session.commit()

            # Step 6: Store topology
            topology_key = f"parts/{part_id}/topology.json"
            upload_file(topology_key, _json.dumps(topology).encode(), "application/json")
            logger.info(
                f"Stored topology: {topology['metadata']['face_count']} faces, "
                f"{topology['metadata']['edge_count']} edges, "
                f"{topology['metadata']['vertex_count']} vertices"
            )

            # Step 7: Store molding plan
            plan_key = f"parts/{part_id}/molding_plan.json"
            upload_file(plan_key, _json.dumps(molding_plan).encode(), "application/json")
            logger.info(
                f"Stored molding plan: {molding_plan['tooling']['mold_type']}, "
                f"material={molding_plan['material']['primary']['name']}, "
                f"clamp={molding_plan['pressure']['clamp_force_tons']}t"
            )

            # Step 8: Store ceramic feasibility
            ceramic_key = f"parts/{part_id}/ceramic_feasibility.json"
            upload_file(ceramic_key, _json.dumps(ceramic).encode(), "application/json")
            logger.info(f"Ceramic feasibility: {ceramic['rating']}")

            job.progress = 92
            await session.commit()

            job.status = "completed"
            job.progress = 100
            job.completed_at = datetime.now(timezone.utc)
            part.status = "analyzed"
            part.error_message = None
            await session.commit()

            logger.info(f"Pipeline complete: part={part_id}")

        except Exception as e:
            logger.error(f"Pipeline failed: job={job_id} error={e}", exc_info=True)
            await session.rollback()
            try:
                r1 = await session.execute(select(AnalysisJob).where(AnalysisJob.id == UUID(job_id)))
                job = r1.scalar_one_or_none()
                r2 = await session.execute(select(Part).where(Part.id == UUID(part_id)))
                part = r2.scalar_one_or_none()
                if job:
                    job.status = "failed"
                    job.error_message = str(e)
                    job.completed_at = datetime.now(timezone.utc)
                if part:
                    part.status = "error"
                    part.error_message = str(e)
                await session.commit()
            except Exception as inner:
                logger.error(f"Failed to save error status: {inner}")
