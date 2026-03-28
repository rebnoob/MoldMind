# MoldMind

**Manufacturing intelligence platform that converts part geometry into an optimized, editable, and factory-aware mold design workflow.**

## What is this?

MoldMind analyzes CAD models (STEP files) for injection moldability, scores design issues, suggests fixes, and progressively assists with mold concept generation. Think "nTop for mold making" — but starting with the intelligence layer, not a full CAD tool.

## Who is it for?

Contract mold shops and product design firms who currently spend 2-8 hours of senior engineer time per part on DFM review. MoldMind reduces this to minutes with automated, explainable analysis.

## Product Phases

| Phase | What | Status |
|-------|------|--------|
| **Phase 1** | DFM / Moldability Analysis | 🔨 Building |
| Phase 2 | Mold Concept Generation | Planned |
| Phase 3 | Designer Copilot | Planned |
| Phase 4 | Accelerated Simulation | Planned |

## Architecture

```
apps/web          → Next.js frontend (upload, 3D viewer, dashboards)
apps/api          → FastAPI gateway (auth, projects, jobs, results)
services/geometry → STEP parsing, tessellation, feature extraction (OpenCascade)
services/dfm      → Rule-based moldability analysis engine
services/mold_concept → (Phase 2) Mold architecture suggestion
services/jobs     → Celery worker for async analysis pipelines
packages/ui       → Shared React components
packages/types    → Shared TypeScript types
packages/config   → Shared configuration
```

## Tech Stack

- **Frontend:** Next.js 14, TypeScript, Three.js (react-three-fiber)
- **API:** Python 3.11+, FastAPI, SQLAlchemy, Celery
- **CAD Kernel:** pythonocc-core (OpenCascade Community Edition)
- **Database:** PostgreSQL 15
- **Queue:** Redis 7
- **Storage:** MinIO (dev) / S3 (prod)
- **Infra:** Docker Compose (dev), Turborepo (monorepo)

## Quick Start

```bash
# Prerequisites: Docker, Node 20+, Python 3.11+, pnpm
cp .env.example .env
docker compose up -d postgres redis minio
cd apps/api && pip install -r requirements.txt && uvicorn src.main:app --reload
cd apps/web && pnpm install && pnpm dev
```

## Key Design Decisions

See [docs/adr/](docs/adr/) for Architecture Decision Records.

- **Web-first, not plugin-first.** Ship value without CAD vendor lock-in.
- **Python backend, not TypeScript.** Geometry libraries are Python/C++.
- **Rules engine, not LLM.** DFM analysis must be deterministic and explainable.
- **AI only where it helps.** Feature classification, not geometry computation.
- **Parametric outputs.** Every suggestion is inspectable and editable.

## License

Proprietary. All rights reserved.
