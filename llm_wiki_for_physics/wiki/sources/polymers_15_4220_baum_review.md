---
title: "Approaches for Numerical Modeling and Simulation of the Filling Phase in Injection Molding — Baum et al. 2023"
kind: source
type: paper
authors: [Markus Baum, Denis Anders, Tamara Reinicke]
year: 2023
journal: Polymers
doi: 10.3390/polym15214220
pages: 28
tags: [filling-phase, hele-shaw, rheology, cross-wlf, review, 1d-2d-2.5d-3d]
path: lexie_test_raw/reference_paper/injection molding/polymers-15-04220.pdf
updated: 2026-04-20
---

# Approaches for Numerical Modeling and Simulation of the Filling Phase in Injection Molding — Baum, Anders, Reinicke (2023)

**Reference:** Baum, M.; Anders, D.; Reinicke, T. *Approaches for Numerical Modeling and Simulation of the Filling Phase in Injection Molding: A Review.* Polymers 2023, 15, 4220. https://doi.org/10.3390/polym15214220
**Raw file:** [`../../lexie_test_raw/reference_paper/injection molding/polymers-15-04220.pdf`](../../lexie_test_raw/reference_paper/injection%20molding/polymers-15-04220.pdf)

## TL;DR

- A 28-page review that **classifies the filling-phase modelling landscape by spatial dimensionality (1D / 2D / 2.5D / 3D) and by rheology (Power-Law, Carreau, Cross, WLF, Arrhenius)**.
- **2D Hele-Shaw on a midplane** is the dominant modelling approach for thin-walled parts and the basis of most commercial software (Moldflow, Moldex3D, C-Flow).
- **2.5D surface models** (Zhou et al.) use a boundary mesh plus "connector elements" to bridge opposite faces and have replaced midplane meshes in many commercial tools.
- **3D full Navier-Stokes** is justified only for thick / massive / extreme-thickness-variation parts.
- **Cross-WLF** and **Cross-Arrhenius** are the workhorse viscosity models in commercial injection molding; Power-Law is a crude high-shear approximation.
- Polymer melts are always in the **Stokes regime (Re ≪ 1)**, so inertial terms are safely dropped in 1D/2D/2.5D formulations.

## Key claims (with where each lives in the wiki)

1. 1D models (disc, tube, strip) are fast but apply only to runner systems and simple cavities. → [spatial_dimensionality](../concepts/spatial_dimensionality.md#1d)
2. The 2D Hele-Shaw pressure equation `∇·(h³/(12η)·∇p) = …` is accurate for thin-walled parts when `h ≪ L` and the flow is quasi-stationary. → [hele_shaw](../concepts/hele_shaw.md)
3. The 2.5D surface model uses connector elements between opposing surfaces to transfer flow across thickness transitions (e.g. ribs). This is what modern Moldflow-style tools actually run under the hood. → [spatial_dimensionality](../concepts/spatial_dimensionality.md#2-5d)
4. Full 3D NS is necessary for parts where h/L is not small or where the gap-averaged pressure assumption breaks (thick bosses, hubs, complex junctions). → [navier_stokes_vs_hele_shaw](../concepts/navier_stokes_vs_hele_shaw.md)
5. The Cross model `η(γ̇)/η₀ = 1 / (1 + (η₀γ̇/τ*)^(1−n))` extended by WLF or Arrhenius for T-dependence is the de-facto commercial standard. → [rheological_models](../concepts/rheological_models.md#cross)
6. The energy equation with viscous heating `ρcp(∂T/∂t + u·∇T) = ∇·(λ∇T) + η·γ̇²` must be solved alongside momentum in any non-trivial simulation. → [filling_phase](../concepts/filling_phase.md#energy-equation)

## Notes by section

### §1 Introduction (p. 1-2)
Motivation: filling phase is a multi-phase, non-Newtonian, non-isothermal problem. Research has evolved 1D → 2D → 2.5D → 3D since the 1950s. Prior reviews (Cardozo, Zhou) under-classified the spatial / rheology axes — this paper's contribution is a cleaner taxonomy.

### §2.1 1D models (p. 3-5)
Three canonical geometries: **center-gated disc, tube, strip**.

Pressure-gradient / fluidity formulation, assuming laminar Poiseuille + no-slip:
- Center-gated disc: `Λ = V̇/(2πR·S)` with `S = ∫ y²/η dy`
- Tube (Hagen–Poiseuille): `Λ = 2V̇/(π·S)` with `S = ∫ r³/η dr`
- Thin strip: `Λ = V̇/(2·b·S)` with `S = ∫ y²/η dy`

Useful only for sprue/runner analysis today.

### §2.2 2D Hele-Shaw (p. 6-8) — the core of the review
Assumes `h ≪ L` and flow symmetry about the midplane. Reynolds ≪ 1 → inertia dropped.

Governing equations (from Chiang & Hieber):
- Mass: `∂/∂x(∫₀ʰ⁄² ρu dz) + ∂/∂y(∫₀ʰ⁄² ρv dz) = ∫₀ʰ⁄² dρ/dt dz`
- Momentum (x, y): `∂p/∂x = ∂/∂z(η·∂u/∂z)` , `∂p/∂y = ∂/∂z(η·∂v/∂z)`
- Pressure independent of z: `∂p/∂z = 0`
- Shear rate: `γ̇ = √((∂u/∂z)² + (∂v/∂z)²)` (z-direction neglected)
- BCs: `u = v = 0` at `z = ±h/2`; symmetry `∂u/∂z = ∂v/∂z = ∂T/∂z = 0` at midplane
- Averaged velocity components: `ū = −∂p/∂x · S/(h/2)` with fluidity `S = ∫₀ʰ⁄² ρ·z²/η dz`
- Pressure-drop equation: **`∇·(S·∇p) = 0`** (the main 2D equation solved by Moldflow-class tools)

Energy equation: convection in x/y + z-conduction + viscous heating (eq. 30).

Simplifications folded in: inelastic flow, no body/inertial forces, no fountain flow, constant λ and cp, no in-plane thermal conduction. Despite those, this is the **industry default**.

### §2.3 2.5D surface model (p. 8-9)
A skin (boundary triangulation) of the 3D solid, like our GLB. Opposing faces are linked by **connector elements** so flow on one side of a thin feature can transfer to the other. Zhou et al. (2001-2002) pioneered it; now used by Moldex3D and others.

The authors note: "the surface model can in principle be converted into a 2D mesh model. This is why the Hele–Shaw approximation is often used for surface models". So 2.5D ≈ Hele-Shaw on a triangulated midsurface.

### §2.4 3D model (p. 9-10)
Full Navier-Stokes + energy on volumetric mesh:
- `∂ρ/∂t + ∇·(ρu) = 0`
- `∂(ρu)/∂t + ∇·(ρuu − τ) = ρg`
- `ρcp(∂T/∂t + u·∇T) = ∇·(λ∇T) + η·γ̇²`

Needed for: massive parts, extreme thickness variation, free surface phenomena (weld lines, air traps). 1000× more expensive than Hele-Shaw.

### §2.5 Rheology (p. 10-14)
Seven models, in rough order of sophistication:

1. **Power-Law**: `η = m·γ̇^(n−1)`. Fails at low shear rate.
2. **Second-Order** (Moldflow): multi-term polynomial in `ln(γ̇)` and T.
3. **Herschel-Bulkley**: adds yield stress, useful for suspensions / ceramic feedstock.
4. **Bingham plastic**: yield-stress-dominated, two-phase flow.
5. **Temperature shift factors**: Arrhenius `η₀ = B·exp(Tb/T)·exp(βp)` vs WLF `η₀ = D₁·exp(−A₁(T−(D₂+D₃p))/(A₂+T−D₂))`.
6. **Carreau** / **Bird-Carreau-Yasuda**: smooth transition from Newtonian plateau to shear-thinning regime.
7. **Cross**: `(η·γ̇ − η∞)/(η₀ − η∞) = 1/(1 + (K·γ̇)^(1−n))` — currently the most common choice in commercial software, usually combined with WLF (Cross-WLF) or Arrhenius (Cross-Arrhenius).

### §3 Historical overview (p. 14-19)
Table on p. 19 lists ~30 years of research publications tagged by dimensionality + rheology. Notable: Moldflow (1978, first commercial); Autodesk-Moldflow is still dominant. Moldex3D (CoreTech) and Simuflow (C-Solution) are the main alternatives.

### §4 Conclusions (p. 19-20)
> "For customized solutions, 2D, 2.5D, and 3D models are particularly promising. While 1D models offer speed and efficiency, they are limited in their ability to provide a comprehensive understanding of injection molding processes for most molded parts."

Pick dimensionality by geometry. Pick rheology (Cross-WLF for most, Power-Law as a fast crude approximation).

## Cross-references

- [concepts/filling_phase](../concepts/filling_phase.md) — this is the canonical overview
- [concepts/hele_shaw](../concepts/hele_shaw.md) — §2.2 equations live here
- [concepts/spatial_dimensionality](../concepts/spatial_dimensionality.md) — §2.1–2.4 summary
- [concepts/rheological_models](../concepts/rheological_models.md) — §2.5 summary
- [concepts/reynolds_number_polymer_melt](../concepts/reynolds_number_polymer_melt.md) — the "Re ≪ 1" pervasive assumption

## Relevance to MoldMind

This paper is the single most-useful source for the simulation service. Concretely:

- **Our "Simple Model" / FMM 3D** (`services/simulation/src/fill_time.py`) is a geodesic approximation that lies somewhere between 2.5D and 3D — not discussed in the paper directly, but consistent with the spirit of §2.3 (surface-model Hele-Shaw).
- **Our OpenFOAM VOF path** (`services/simulation/src/openfoam_runner.py`) is a §2.4 3D NS solver with the Cross-WLF rheology planned for session 3 per §2.5.
- **Gate-position optimisation** isn't deeply covered — the paper focuses on *given a gate*, how to simulate. For gate placement we lean on the user's practical note + classical DFM heuristics. See [gate_optimization](../concepts/gate_optimization.md).
