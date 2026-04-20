# MoldMind

**Manufacturing intelligence platform that converts part geometry into an optimized, editable, and factory-aware mold design workflow.**

## What is this?

MoldMind analyzes CAD models (STEP files) for injection moldability, scores design issues, suggests fixes, runs interactive 3D fill simulations, and progressively assists with mold concept generation. Think "nTop for mold making" — but starting with the intelligence layer, not a full CAD tool.

## Who is it for?

Contract mold shops and product design firms who currently spend 2-8 hours of senior engineer time per part on DFM review. MoldMind reduces this to minutes with automated, explainable analysis.

## Product Phases

| Phase | What | Status |
|-------|------|--------|
| **Phase 1** | DFM / Moldability Analysis | 🔨 Building |
| Phase 2 | Mold Concept Generation | Partially shipped |
| Phase 3 | Designer Copilot | Planned |
| **Phase 4** | Accelerated Flow Simulation | 🔨 Building |

## Current capabilities

- **STEP → GLB pipeline**: OpenCascade tessellation, face-level mapping, topology extraction (faces / edges / vertices + adjacency + feature classification), per-face DFM rules
- **DFM analysis**: draft angle, wall thickness, undercuts, sharp corners, feature-aware thresholds; PASS / REVIEW / FAIL verdict
- **Molding planning**: tooling assessment, material recommendation, injection/clamp pressure estimation, cavity count
- **Ceramic-insert feasibility**: GO / CAUTION / NO-GO with categorised checks
- **3D fill simulation (Simple Model)**: voxel fast-marching solver with local h² geometry weighting and Arrhenius η(T) viscosity coupling. Runs in ~2 s on upload; produces a per-vertex melt-arrival-time field rendered as an interactive 3D animation
- **Adaptive solver selector**: picks the cheapest fluid model (Hele-Shaw 2D / FMM 3D / Stokes 3D / VOF 3D) that still captures the part's physics, based on aspect ratio, Reynolds number, and geometric features
- **OpenFOAM VOF scaffolding**: Docker container, STEP→STL export, automatic `interFoam` case generation. Full solver pipeline is in progress (blockMesh + snappyHexMesh + interFoam in sessions 2–3)
- **3D viewer**: Three.js with face-level highlighting, edge/vertex picking, and a separate fill-animation mode with timeline scrubber and adjustable T_inj / T_wall / decay length

## Architecture

```
apps/web              → Next.js frontend (upload, 3D viewer, flow sim, dashboards)
apps/api              → FastAPI gateway (auth, projects, jobs, results, simulation endpoints)
services/geometry     → STEP parsing, tessellation, topology, face analysis (pythonocc-core)
services/dfm          → Rule-based moldability analysis engine
services/molding      → Tooling / material / pressure / ceramic feasibility
services/simulation   → Flow simulation (FMM 3D, solver selector, OpenFOAM runner)
  └── openfoam_templates → Smoke tests + future case templates
services/mold_concept → (Phase 2) Mold architecture suggestion
services/jobs         → Celery worker for async analysis pipelines
openfoam_cases/       → Per-part generated OpenFOAM case directories (bind-mounted into container)
packages/ui, types, config → Shared React / TS / config
```

## Tech Stack

- **Frontend:** Next.js 14, TypeScript, Three.js (react-three-fiber), custom WebGL shader for fill animation
- **API:** Python 3.11, FastAPI, SQLAlchemy (async), Celery
- **CAD kernel:** pythonocc-core 7.9.3 (OpenCascade, conda-only)
- **Numerical:** NumPy, SciPy, scikit-fmm (fast marching), trimesh (voxelization)
- **3D CFD:** OpenFOAM v2312 via Docker (`opencfd/openfoam-default:2312`)
- **Database:** SQLite (dev) / PostgreSQL 15 (prod)
- **Queue:** Redis 7
- **Storage:** local FS (dev) / MinIO or S3 (prod)
- **Infra:** Docker Compose (dev), conda (Python env), Turborepo (monorepo)

## Quick Start

Because `pythonocc-core` is conda-only, the API runs from a conda env.

```bash
# One-time setup
conda create -n moldmind --override-channels -c conda-forge -y python=3.11 pythonocc-core=7.9.3
conda run -n moldmind pip install -r apps/api/requirements.txt
conda run -n moldmind pip install scipy matplotlib pillow scikit-fmm trimesh aiosqlite

# Optional: OpenFOAM VOF solver container (~2 GB image, ~5 min first pull)
docker compose up -d openfoam

# API
cd apps/api
PYTHONPATH=$(pwd)/../.. conda run --no-capture-output -n moldmind \
  uvicorn src.main:app --host 0.0.0.0 --port 8000 --log-level info

# Web (separate terminal)
cd apps/web && pnpm install && pnpm dev
```

Open http://localhost:3000, sign up, create a project, upload a STEP file.

## Key Design Decisions

See [docs/adr/](docs/adr/) for Architecture Decision Records.

- **Web-first, not plugin-first.** Ship value without CAD vendor lock-in.
- **Python backend, not TypeScript.** Geometry libraries are Python/C++.
- **Rules engine for DFM, not LLM.** Analysis must be deterministic and explainable.
- **Adaptive solver selection.** Don't solve full 3D Navier-Stokes on a 0.5 mm shell when Hele-Shaw is exact to a few percent at 1000× the speed.
- **Parametric outputs.** Every suggestion is inspectable and editable.
- **Custom GLB builder.** Non-indexed flat mesh output preserves per-face vertex mapping (trimesh export would auto-repair and break face indexing).

## License

Proprietary. All rights reserved.
