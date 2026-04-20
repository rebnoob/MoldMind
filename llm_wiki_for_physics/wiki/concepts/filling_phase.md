---
title: Filling phase
kind: concept
tags: [filling, injection-molding, cavity, pressure, temperature]
sources: [polymers_15_4220_baum_review, optimal_gate_position_note]
updated: 2026-04-20
---

# Filling phase

## Summary

The **filling phase** is the portion of the injection-molding cycle between
melt entry at the gate and the instant the cavity is completely filled. It
sets up the field of flow lines, weld lines, pressure, temperature, density,
and orientation that every later phase (packing, holding, cooling) inherits
[Baum 2023 §2](../sources/polymers_15_4220_baum_review.md#-2-modeling-of-the-filling-phase).

Modelling the filling phase accurately requires solving, at minimum:

1. **Conservation of mass** — incompressible (filling) or slightly compressible (packing)
2. **Conservation of momentum** — Navier-Stokes or one of its reductions
3. **Conservation of energy** — with viscous-heating source term
4. **A rheological constitutive law** — `η(T, p, γ̇)` (see [rheological_models](rheological_models.md))
5. **A free-surface / flow-front tracking method** — VOF, level-set, geodesic proxy

For polymer melts the flow is always in the **Stokes regime** (`Re ≪ 1`, see
[reynolds_number_polymer_melt](reynolds_number_polymer_melt.md)), so inertia
is dropped in practically every formulation except fully 3D VOF for complex parts.

## Governing equations

### General 3D form (Baum §2.4, p. 9)

- Mass: `∂ρ/∂t + ∇·(ρu) = 0`
- Momentum: `∂(ρu)/∂t + ∇·(ρuu − τ) = ρg`
- Energy: `ρcp(∂T/∂t + u·∇T) = ∇·(λ∇T) + η·γ̇²`

Where τ is the stress tensor, g is gravity, λ is thermal conductivity, cp is
specific heat. The last term of the energy equation is **viscous heating** —
important for thin/high-shear regions, can raise local T by 20-50 °C.

### Hele-Shaw reduction (Baum §2.2)

For `h ≪ L`, the pressure becomes z-independent and the 3D system collapses
to a **2D pressure Poisson equation on the midplane**:

```
∇·(S·∇p) = 0        with fluidity S = ∫₀ʰ⁄² ρ·z²/η dz
```

This is what commercial Hele-Shaw solvers actually integrate. See [hele_shaw](hele_shaw.md).

### Energy equation in Hele-Shaw (Baum §2.2, eq. 30)

```
ρcp(∂T/∂t + u·∂T/∂x + v·∂T/∂y) = λ·∂²T/∂z² + η·γ̇²
```

Note: only **z-conduction** is kept (in-plane conduction is neglected because
the thin-gap aspect ratio makes it sub-dominant). The midplane holds, so
`T(z)` varies from the wall temperature `T_wall` at `z = ±h/2` to the melt
temperature `T_inj` at `z = 0`.

## Phase boundaries

| Phase | Starts | Ends | Dominant physics |
|---|---|---|---|
| **Filling** | Screw advances, gate opens | Cavity volume is fully occupied by melt | Momentum + energy |
| Packing | Pressure-hold to compensate shrinkage | Gate freezes off | Compressibility, thermal shrinkage |
| Cooling | Pressure released | Part rigid enough to eject | Energy only |

This wiki (and MoldMind's Simple Model) focuses on filling.

## Initial and boundary conditions

- **Gate (inlet) patch**: either `u = U_inj` (velocity-controlled) or `p = P_inj` (pressure-controlled). In commercial molding both are switched: velocity during filling, pressure during packing.
- **Cavity walls**: `u = 0` (no-slip), `T = T_wall` (fixed mold temperature). No-slip is questionable at the polymer–mold interface but near-universal.
- **Free surface (melt front)**: stress-free, `p = P_atm`. Tracked either explicitly (VOF, level-set) or implicitly (front advances on the geodesic / Eikonal time field in our Simple Model).

## Where in MoldMind

| Piece | File | Which eq. it solves |
|---|---|---|
| Simple Model 3D FMM | `services/simulation/src/fill_time.py:170` | Eikonal proxy for front arrival time + Arrhenius T decay + Arrhenius η(T) coupling |
| Gate optimizer | `services/simulation/src/gate_optimizer.py` | Enumerates candidate gate positions, ranks by `max(fill_time)` |
| OpenFOAM VOF case | `services/simulation/src/case_generator.py` | (Session 2/3) full 3D NS + VOF + Newtonian rheology; Cross-WLF planned |

## Open questions

- Our fill-time proxy does not solve a pressure field — it's a **geodesic speed field**, not Navier-Stokes. Documenting how close this is to a real Hele-Shaw solution on standard test geometries (iPhone back, dogbone) would make the claim stronger. → future [navier_stokes_vs_hele_shaw](navier_stokes_vs_hele_shaw.md) comparison.
- Viscous heating is not in our Simple Model. For thin ribs this can bias the T field by tens of °C.
