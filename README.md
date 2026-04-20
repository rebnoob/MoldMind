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
- **3D fill simulation (Simple Model)**: voxel fast-marching solver with local `h²` geometry weighting and Arrhenius `η(T)` viscosity coupling. Runs in ~2 s on upload; produces a per-vertex melt-arrival-time field rendered as an interactive 3D animation
- **Adaptive solver selector**: picks the cheapest fluid model (Hele-Shaw 2D / FMM 3D / Stokes 3D / VOF 3D) that still captures the part's physics, based on aspect ratio, Reynolds number, and geometric features
- **Gate position optimizer**: ranks candidate gate locations using either the three plane-centres (XY/XZ/YZ) or axis lines through the centre of mass, scoring each by `max(fill_time)`
- **OpenFOAM VOF scaffolding**: Docker container, STEP→STL export, automatic `interFoam` case generation. Full solver pipeline is in progress (blockMesh + snappyHexMesh + interFoam in sessions 2–3)
- **3D viewer**: Three.js with face-level highlighting, edge/vertex picking, and a separate fill-animation mode with timeline scrubber and adjustable `T_inj` / `T_wall` / decay length

## Physics Models

Injection molding has a well-established modelling hierarchy in the literature — this section summarises what MoldMind actually solves, the assumptions it makes, and the references those assumptions come from. Primary reference: **Baum, Anders & Reinicke 2023**, *Approaches for Numerical Modeling and Simulation of the Filling Phase in Injection Molding: A Review* (Polymers 15, 4220, [doi:10.3390/polym15214220](https://doi.org/10.3390/polym15214220)).

### Flow regime — Stokes, always

For any thermoplastic polymer melt injected at realistic speeds, the Reynolds number is

```
Re = ρ·v·L/μ ≈ (1000)(0.1)(0.01)/(1000) ≈ 10⁻³
```

This is four orders of magnitude below the turbulent transition. Every injection-molding formulation in MoldMind therefore **drops the inertial `(u·∇)u` term** and works in the Stokes regime (Baum §2.2, p. 6).

### Spatial dimensionality — pick by aspect ratio

| Model | Regime | Where MoldMind uses it |
|---|---|---|
| **1D** (disc / tube / strip) | Analytical, runner systems only | Not used — too crude for realistic parts (Baum §2.1) |
| **2D Hele-Shaw** | `h/L < 0.05`, pure shell | The "Hele-Shaw 2D" branch of the solver selector (Baum §2.2) |
| **2.5D surface** | Thin-walled 3D, Moldflow default | Not directly implemented; our FMM 3D is spiritually close |
| **3D Navier-Stokes + VOF** | `h/L > 0.2`, undercuts, chunky parts | OpenFOAM `interFoam` path (Baum §2.4) |

The decision boundary (tunable in [`services/simulation/src/solver_selector.py`](services/simulation/src/solver_selector.py)):

```python
if aspect ≥ 0.30 or undercuts ≥ 3:            → vof_3d       (OpenFOAM interFoam)
elif aspect ≥ 0.20 or undercuts > 0
                  or has_3d_features:         → fmm_3d       (Simple Model)
elif aspect < 0.05 and no undercuts:          → hele_shaw_2d (classical midplane)
else:                                         → fmm_3d       (borderline 2.5D)
```

### Hele-Shaw approximation — the industry workhorse

When `h ≪ L` and symmetry about the midplane holds, the 3D momentum equation collapses to a 2D pressure Poisson equation [Baum §2.2, eq. 18-29]:

```
∇·(S·∇p) = 0        with fluidity S = ∫₀ʰ⁄² ρ·z²/η dz
```

Gap-averaged velocity components are then

```
ū = −(∂p/∂x)·S/(h/2)
v̄ = −(∂p/∂y)·S/(h/2)
```

This is what commercial solvers (Moldflow, Moldex3D, C-Flow) integrate under the hood.

### MoldMind's "Simple Model" — voxel fast-marching

Instead of solving the Poisson equation directly, MoldMind computes a **geodesic proxy for Hele-Shaw** on a voxel grid using `scikit-fmm`. The trick is to make the Eikonal speed field match the Hele-Shaw physics:

1. **Voxelise** the solid interior (`trimesh.voxelized(pitch).fill()`).
2. **Local gap thickness** `h(x,y,z) = 2·EDT(x,y,z)` from a 3D Euclidean distance transform — a voxel in the middle of a 3 mm plate gets `h ≈ 3 mm`, a voxel near a rib wall gets much less.
3. **Speed field** `v(x,y,z) ∝ h² / η(T)` — matches the Hele-Shaw parabolic scaling.
4. **First FMM pass** with `v = h²` gives a preliminary fill-time field.
5. **Temperature estimate**: `T(r) = T_wall + (T_inj − T_wall)·exp(−r / L_decay)` (Arrhenius spatial decay, matches the approach in [hele_shaw_step.py](https://github.com/rebnoob/MoldMind/) reference implementation).
6. **Arrhenius viscosity**: `η(T) = η₀·exp(B·(1/T − 1/T_ref))`.
7. **Second FMM pass** with viscosity-corrected speed `v = h² / η(T)`.

Implementation: [`services/simulation/src/fill_time.py`](services/simulation/src/fill_time.py). Runs in ~2 s on a 100k-vertex iPhone-sized part at `max_grid=96`.

### Rheology — what we use vs what's standard

Polymer melts are strongly shear-thinning and temperature-sensitive (Baum §2.5). The commercial stack (Moldflow, Moldex3D) pairs a **shear-thinning factor** with a **temperature shift**:

| Model | Form | Used by |
|---|---|---|
| **Power-Law** | `η = m·γ̇^(n−1)` | Quick prototypes; fails at low shear |
| **Cross** | `η = η₀ / (1 + (η₀·γ̇/τ*)^(1−n))` | **Commercial default** (shear-thinning) |
| **Carreau / Bird-Carreau-Yasuda** | smooth Newtonian → shear-thinning transition | Academic + some commercial |
| **Arrhenius shift** | `η₀ = B·exp(T_b/T)·exp(β·p)` | **What MoldMind currently uses** (crude but cheap) |
| **WLF shift** | 5-parameter, near-glass-transition accurate | Required for amorphous polymers near T_g |
| **Cross-WLF** | combined | Industry standard, not yet in MoldMind |

Current limitation: MoldMind uses Arrhenius only, no shear-thinning. Fine for fill-sequence visualisation and gate-placement ranking; **not** accurate for clamp force, weld-line location, or cycle time. Cross-WLF on the OpenFOAM path is planned work.

### Gate position optimization

For the injected polymer entry point, MoldMind implements a practical heuristic:

- **Symmetric parts**: try the three plane-centres (XY / XZ / YZ), pick the one that minimises `max(fill_time)`.
- **Asymmetric parts**: sweep 3 points along each axis line through the centre of mass (9 candidates total).
- **Exhaustive search** (optional): 5×5 grid on the XY face for a full heat-map.

Default for phone-case-shaped parts (largest face on XY): gate at the **centre of the XY plane**, dropped onto the top-Z surface. Implementation: [`services/simulation/src/gate_optimizer.py`](services/simulation/src/gate_optimizer.py). Exposed as `GET /api/analysis/simulation/gate/optimize/{part_id}?strategy=symmetric_centers`.

The scoring function `max(fill_time)` captures "longest flow path" — the shorter this is, the more balanced the fill. Future work: combine with flow-length ratio and weld-line count for a weighted score.

### Equations actually solved

| Stage | Equations | File |
|---|---|---|
| Solver selection | Re estimate, aspect-ratio thresholds | [`solver_selector.py`](services/simulation/src/solver_selector.py) |
| Simple Model fill-time | Eikonal `\|∇T\|·F = 1` with `F ∝ h²/η(T)` | [`fill_time.py`](services/simulation/src/fill_time.py) |
| Simple Model rheology | Arrhenius `η = η₀·exp(B·(1/T−1/T_ref))` | [`fill_time.py:196`](services/simulation/src/fill_time.py) |
| Gate optimization | Argmin over candidate set of `max(fill_time)` | [`gate_optimizer.py`](services/simulation/src/gate_optimizer.py) |
| OpenFOAM VOF (WIP) | 3D Navier-Stokes + VOF α-field + energy eq. | [`case_generator.py`](services/simulation/src/case_generator.py), [`openfoam_runner.py`](services/simulation/src/openfoam_runner.py) |

### Assumptions to remember

- **Re ≪ 1**: inertia dropped everywhere.
- **Mid-plane symmetry** (Hele-Shaw branch only): `∂u/∂z = ∂v/∂z = 0` at `z=0`.
- **Newtonian η(T)** in the Simple Model: no shear-thinning yet.
- **Single-gate**: multi-gate / hot-runner geometries not handled.
- **Isothermal mold wall**: constant `T_wall` assumed.
- **No fountain flow** in any branch (matters near the melt front).
- **No compressibility**: density constant during filling (real packing is compressible).

## Architecture

```
apps/web              → Next.js frontend (upload, 3D viewer, flow sim, dashboards)
apps/api              → FastAPI gateway (auth, projects, jobs, results, simulation endpoints)
services/geometry     → STEP parsing, tessellation, topology, face analysis (pythonocc-core)
services/dfm          → Rule-based moldability analysis engine
services/molding      → Tooling / material / pressure / ceramic feasibility
services/simulation   → Flow simulation (FMM 3D, solver selector, gate optimizer, OpenFOAM runner)
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
conda run -n moldmind pip install scipy matplotlib pillow scikit-fmm trimesh aiosqlite pypdf

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
- **Geodesic proxy for Hele-Shaw.** Instead of solving a pressure Poisson equation we run a fast-marching Eikonal with the same `h²/η(T)` speed scaling — gives a visualisable fill-time field in 2 s at the cost of not producing a pressure field.

## References

- Baum, M.; Anders, D.; Reinicke, T. **Approaches for Numerical Modeling and Simulation of the Filling Phase in Injection Molding: A Review.** *Polymers* 2023, 15, 4220. [doi:10.3390/polym15214220](https://doi.org/10.3390/polym15214220) — the primary modelling reference used throughout this README.
- Kennedy, P.; Zheng, R. **Flow Analysis of Injection Molds**, 2nd ed. Hanser Gardner, 2013 — foundational text on Hele-Shaw / commercial Moldflow-style analysis.
- OpenFOAM v2312 documentation — https://www.openfoam.com/documentation/user-guide
- scikit-fmm — https://pythonhosted.org/scikit-fmm/ (Eikonal / level-set fast marching)

## License

Proprietary. All rights reserved.
