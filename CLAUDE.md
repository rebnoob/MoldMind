# MoldMind - CLAUDE.md

## Project Overview
MoldMind is a manufacturing intelligence platform for injection mold DFM (Design for Manufacturability) analysis. Upload STEP files → parse with OpenCascade → tessellate to GLB → run DFM rules → view results in 3D with face-level highlighting.

## Tech Stack
- **Frontend**: Next.js 14 + TypeScript + Three.js (react-three-fiber) at `apps/web/`
- **Backend**: FastAPI (Python) at `apps/api/`, SQLite (dev), local filesystem storage
- **CAD Kernel**: pythonocc-core 7.9.3 (OpenCascade) installed via conda
- **Geometry**: Custom tessellator (`services/geometry/`), custom GLB builder (no trimesh export)
- **DFM Engine**: Rule-based at `services/dfm/` — draft angle, wall thickness, undercuts, sharp corners

## Running the App

Backend runs from the `moldmind` conda env (contains pythonocc-core 7.9.3 + scipy/matplotlib for the Hele-Shaw simulator). The `apps/api/venv/` is stale — do NOT use it.

```bash
# API (conda env "moldmind")
cd /Users/xiaoxizhou/Downloads/Molding/MoldMind/apps/api
PYTHONPATH=/Users/xiaoxizhou/Downloads/Molding/MoldMind \
  conda run --no-capture-output -n moldmind \
  uvicorn src.main:app --host 0.0.0.0 --port 8000 --log-level info

# Web
cd /Users/xiaoxizhou/Downloads/Molding/MoldMind/apps/web
pnpm dev
```

First-time env setup (already done on this machine):
```bash
conda create -n moldmind --override-channels -c conda-forge -y python=3.11 pythonocc-core=7.9.3
conda run -n moldmind pip install -r apps/api/requirements.txt
conda run -n moldmind pip install scipy matplotlib pillow
```
- Frontend: http://localhost:3000
- API: http://localhost:8000
- API docs: http://localhost:8000/docs

## Key Architecture Decisions
- **Non-indexed (flat) mesh geometry**: Each triangle has its own 3 vertices (no sharing). Makes per-face coloring exact with no bleed between adjacent faces.
- **Custom GLB builder**: Builds GLB manually to avoid trimesh auto-repair which breaks face_map indexing.
- **Face orientation handling**: Checks `face.Orientation() == TopAbs_REVERSED` and flips winding + normals.
- **asyncio background tasks**: No Celery/Redis. Uses `asyncio.create_task()` with retry loop to wait for DB commit.
- **SQLite for dev**: Cross-DB types (GUID, JSONType, IntArrayType) in `apps/api/src/core/types.py`.
- **face_map.json**: Stored alongside GLB. Maps B-Rep face_index → vertex ranges `{face_index, vert_start, vert_end}`.

## File Layout (Key Files)
```
apps/api/src/main.py              — FastAPI app, file serving endpoint
apps/api/src/routes/parts.py      — Upload, list, enriched with DFM scores
apps/api/src/routes/analysis.py   — DFM result retrieval
apps/api/src/workers/tasks.py     — Background pipeline: STEP→tessellate→DFM→store
apps/api/src/core/types.py        — Cross-DB column types (GUID, JSONType)
apps/api/src/core/storage.py      — Local filesystem / S3 abstraction
services/geometry/src/tessellator.py   — OCC tessellation → flat mesh → custom GLB
services/geometry/src/face_analysis.py — Per-face draft angle, undercut detection
services/geometry/src/wall_thickness.py — Ray-cast wall thickness (15s time cap)
services/geometry/src/step_parser.py   — STEP file parsing via OCC
services/dfm/src/engine.py        — DFM orchestrator
services/dfm/src/rules/           — Individual DFM rules
apps/web/src/app/analysis/[partId]/page.tsx — Analysis view
apps/web/src/components/viewer/part-viewer.tsx — Three.js GLB viewer with face highlighting
apps/web/src/app/dashboard/page.tsx — Parts list with polling
apps/web/src/app/upload/page.tsx   — File upload → redirect to dashboard
```

## Current State (2026-03-21)
- ✅ Upload STEP → parse → tessellate → GLB → view in browser (real geometry)
- ✅ Real DFM analysis on actual geometry (draft, thickness, undercuts, corners)
- ✅ Face-level highlighting when clicking DFM issues
- ✅ Dashboard with real-time polling (uploaded → processing → analyzed)
- ✅ Error messages surfaced to UI
- ✅ Auth (JWT), projects, parts CRUD
- ✅ High-quality tessellation: 0.01mm deflection, 0.1rad angular, adaptive scaling, CAD-style edge rendering
- ✅ Tessellation config centralized in services/dfm/src/dfm_config.py (TessellationConfig class)
- ✅ Tessellation debug metadata stored per analysis (brep_available, deflection, vertex/tri count, normals source)
- ✅ Feature-based DFM (like Onshape/Fusion): feature_recognition.py classifies faces into main_wall/boss/hole/rib/fillet/parting
- ✅ Core/cavity side detection via OCC solid classifier
- ✅ Per-feature draft thresholds: cavity wall=1°, core wall=0.5°, boss=0.5°, hole=0.25°, rib=0.5°
- ✅ All rules filter by feature type (fillets/transitions excluded from thickness, draft, undercut checks)
- ✅ CAD topology layer: topology.json with bodies, faces (vertex_ids), edges (polylines), vertices, adjacency, stable IDs, features
- ✅ BREP serialization: brep.bin stored alongside mesh for shape reconstruction without re-importing STEP
- ✅ Edge polylines: pre-tessellated curves (24pts for circles, 2pts for lines) for frontend rendering/raycasting
- ✅ Onshape-style hover + click: face/edge/vertex selection with overlays, edge highlighting, tooltips
- ✅ Injection molding planning: tooling assessment + material recommendation + pressure estimation (services/molding/)
- ✅ PASS/REVIEW/FAIL verdict with one-sentence summary
- ✅ Central config: services/dfm/src/dfm_config.py (all thresholds in one place)
- ✅ 3D annotations: lines from face surface to floating labels, color-coded by severity
- ✅ Face map includes per-face centroid + outward normal for annotation placement
- ✅ Click annotation label in 3D or issue in panel → highlights faces + selects annotation
- ⬜ Parting line suggestion (Phase 2)
- ⬜ CAD plugin integration (Phase 3)

## Known Issues / Gotchas
- `bcrypt` must be pinned to 4.0.x (passlib incompatible with >= 4.1)
- SQLAlchemy `metadata` is a reserved attribute name on Declarative models
- `PYTHONPATH` must include project root for `services/` imports
- `.env.local` required in `apps/web/` for `NEXT_PUBLIC_API_URL`
- Background task needs 1s sleep + retry loop due to SQLite commit race
- Wall thickness ray-casting has 15s time cap to prevent hanging on complex parts
