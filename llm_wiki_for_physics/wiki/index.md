# Physics Wiki — Index

Injection-molding simulation knowledge base. Built incrementally from
`lexie_test_raw/` following the pattern in [`../Schema/CLAUDE.md`](../Schema/CLAUDE.md).

## Sources

Every source has a dedicated page under `sources/` that summarises it in our own
words and links to the raw file. See [`log.md`](log.md) for chronological ingest order.

### Papers

| Slug | Authors · Year | One-line |
|---|---|---|
| [polymers_15_4220_baum_review](sources/polymers_15_4220_baum_review.md) | Baum, Anders, Reinicke · 2023 | Review of 1D/2D/2.5D/3D filling-phase models + polymer rheology |
| [flow_analysis_of_injection_molds](sources/flow_analysis_of_injection_molds.md) | Kennedy & Zheng · 2013 | Book (2nd ed.); foundational text on Hele-Shaw / Moldflow-style analysis — *stub, pending deep ingest* |

### Notes (user-authored)

| Slug | Topic |
|---|---|
| [optimal_gate_position_note](sources/optimal_gate_position_note.md) | Practical heuristics for picking gate location (symmetric / asymmetric rules) |
| [reynolds_number_note](sources/reynolds_number_note.md) | Pointer to Wikipedia Re + Navier-Stokes |

### Reference repositories

| Slug | Purpose |
|---|---|
| [donny_molding_injection](sources/donny_molding_injection.md) | Hele-Shaw + 2.5D NumPy/FEniCS scripts (iPhone 15 Pro reference) — *stub* |
| [moldsim_repo](sources/moldsim_repo.md) | Injection-mold web app — *stub* |
| [openinjmoldsim_repo](sources/openinjmoldsim_repo.md) | OpenFOAM-based open-source injection-mold sim (dogbone) — *stub* |
| [ultimate_fluid_sim_repo](sources/ultimate_fluid_sim_repo.md) | Processing SPH particle-fluid demo — *stub* |

## Concepts

Topic syntheses that compound across sources.

| Page | What it covers |
|---|---|
| [filling_phase](concepts/filling_phase.md) | The injected-melt flow from gate to cavity full-fill |
| [spatial_dimensionality](concepts/spatial_dimensionality.md) | 1D vs 2D vs 2.5D vs 3D modelling — when to use which |
| [hele_shaw](concepts/hele_shaw.md) | Gap-averaged 2D pressure equation + assumptions |
| [rheological_models](concepts/rheological_models.md) | Power-Law, Carreau, Cross, WLF, Arrhenius |
| [reynolds_number_polymer_melt](concepts/reynolds_number_polymer_melt.md) | Why Re ≪ 1 for polymer injection → Stokes regime |
| [gate_optimization](concepts/gate_optimization.md) | Heuristics + algorithms for picking gate position |
| [navier_stokes_vs_hele_shaw](concepts/navier_stokes_vs_hele_shaw.md) | When full 3D NS is needed vs when Hele-Shaw is exact — *stub* |

## Entities

| Page | Role |
|---|---|
| [moldflow](entities/moldflow.md) | First commercial injection-molding simulator (Autodesk) — *stub* |
| [moldex3d](entities/moldex3d.md) | CoreTech System's commercial 3D solver — *stub* |
| [openfoam](entities/openfoam.md) | Open-source CFD toolbox used by MoldMind's VOF path — *stub* |

## Conventions

- Every claim cites a source page. Never state a fact without a link.
- Pages tagged `*stub*` are placeholders — read the raw first, then write the page.
- See [`log.md`](log.md) for the chronological timeline.
- See [`../Schema/CLAUDE.md`](../Schema/CLAUDE.md) for templates + workflows.
