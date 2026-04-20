---
title: Spatial dimensionality of injection-molding models
kind: concept
tags: [1d, 2d, 2.5d, 3d, modelling]
sources: [polymers_15_4220_baum_review]
updated: 2026-04-20
---

# Spatial dimensionality — 1D / 2D / 2.5D / 3D

## Summary

Choosing the **spatial dimensionality** is the biggest single decision in setting
up a filling-phase simulation. It trades accuracy against compute: every step
up is ~10× the cost for a comparable mesh [Baum 2023 §2](../sources/polymers_15_4220_baum_review.md#-2-modeling-of-the-filling-phase).

| Dim | When | Cost | Captures |
|---|---|---|---|
| **1D** | Runner / sprue only | milliseconds | 1D pressure drop |
| **2D** | True midplane of a thin plate | 1 s | In-plane pressure + gap-averaged flow |
| **2.5D** | Thin-walled 3D part (surface mesh) | 1-10 s | 2D Hele-Shaw on a triangulated skin + connector elements |
| **3D** | Thick / chunky / extreme-thickness-variation | 10 min - hours | Full NS + VOF, true velocity profile |

MoldMind's **Simple Model** sits between 2.5D and 3D: 3D voxelised geometry
but a scalar fill-time field (no velocity or pressure).

## 1D

Canonical geometries: **center-gated disc, tube, strip** (Baum §2.1, p. 3-5,
Fig. 1). Analytical pressure-drop formula:

- Disc: `Λ = V̇ / (2πR·S)`, `S = ∫ y²/η dy`
- Tube (Hagen-Poiseuille): `Λ = 2V̇ / (π·S)`, `S = ∫ r³/η dr`
- Strip: `Λ = V̇ / (2b·S)`, `S = ∫ y²/η dy`

**When useful:** sprue / runner networks where flow is effectively pipe-like.
Still used today as the backbone of "layflat" analyses where a complex cavity
is decomposed into a tree of 1D strips.

**When not:** any real 3D geometry — non-Newtonian + non-isothermal behaviour
can't be captured.

## 2D

True 2D Hele-Shaw on a midplane (a single planar triangulation through the
centre of the gap). Needs an external CAD step to extract the midplane, which
is hard for anything with ribs or a topology change. See [hele_shaw](hele_shaw.md).

**Historical: Tadmor et al. 1974, Hieber & Shen 1978, Wang et al. 1986.**

## 2.5D

Surface model — a **boundary triangulation** (like a GLB / STL skin) of the
part. For each pair of opposing triangles, the solver uses the local gap `h`
and applies the Hele-Shaw pressure equation as if it were 2D. Where surfaces
can't be paired (thin ribs joining a back wall, T-junctions), **connector
elements** carry flow between faces [Baum 2023 §2.3](../sources/polymers_15_4220_baum_review.md#-2-3-2-5d-surface-model-p-8-9).

**Zhou et al. 2001-2002** first formulated this. Moldex3D's eDesign and
Moldflow's dual-domain mode are 2.5D under the hood.

**Big win**: no midplane extraction needed. You can feed a raw CAD STL
straight into a 2.5D solver.

**Big caveat**: connector elements are a heuristic, not physics. Results at
rib bases, bosses, and T-junctions are less trustworthy than a full 3D solve.

## 3D

Full volumetric NS + energy + rheology. See [navier_stokes_vs_hele_shaw](navier_stokes_vs_hele_shaw.md)
(stub) for the decision boundary.

**Needed for:**

- Parts with `h/L > 0.2` (chunky)
- Thick bosses, hubs, undercut regions
- Accurate weld-line / air-trap prediction
- Fibre orientation where the 2.5D assumption masks the through-thickness gradient

**Cost**: ~1000× Hele-Shaw. 20-60 min for a cellphone-sized part on 4 cores.

In MoldMind: routed via the **OpenFOAM container** and `interFoam` solver
(`services/simulation/src/openfoam_runner.py`; case templates in
`services/simulation/src/case_generator.py`).

## Decision rule (MoldMind)

From [solver_selector.py](../../../services/simulation/src/solver_selector.py):

```
aspect = median_thickness / flow_length
undercuts = topology.undercut_count

if aspect ≥ 0.30 or undercuts ≥ 3:
    → vof_3d  (OpenFOAM interFoam)
elif aspect ≥ 0.20 or undercuts > 0 or has_3d_features:
    → fmm_3d  (our Simple Model)
elif aspect < 0.05 and no undercuts:
    → hele_shaw_2d  (classical midplane)
else:
    → fmm_3d  (borderline 2.5D range)
```

The thresholds are heuristic. **synthesis:** Baum doesn't give hard numbers; our 0.05 / 0.20 / 0.30 are informed by the "thin-walled" qualitative language in §2.2 plus Moldex3D's published guidance.

## Historical summary (Baum §3, p. 14-19)

- **1950s-70s**: purely 1D (Kamal, Kenig, Stevenson, Williams, Lord, Thienel, Menges, Harry, Parrott).
- **1974-1980s**: 2D Hele-Shaw (Tadmor, Hieber, Shen, Richardson, Broyer).
- **1990s-2000s**: 2.5D surface (Zhou, Chang, Yang, Kwon) — became the commercial default.
- **2000s-now**: 3D full NS becomes feasible, used for special parts. Cross-WLF / Cross-Arrhenius dominate the rheology.

## Cross-references

- [filling_phase](filling_phase.md)
- [hele_shaw](hele_shaw.md)
- [rheological_models](rheological_models.md)
- [reynolds_number_polymer_melt](reynolds_number_polymer_melt.md)
