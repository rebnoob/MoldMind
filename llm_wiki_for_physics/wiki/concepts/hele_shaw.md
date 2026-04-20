---
title: Hele-Shaw approximation
kind: concept
tags: [hele-shaw, 2d, midplane, pressure-equation, stokes]
sources: [polymers_15_4220_baum_review, reynolds_number_note]
updated: 2026-04-20
---

# Hele-Shaw approximation

## Summary

**Hele-Shaw** reduces 3D viscous flow in a thin gap (`h ≪ L`) to a 2D pressure
equation on the midplane. It's the workhorse of commercial injection-molding
simulation (Moldflow, Moldex3D, C-Flow) and remains accurate to a few percent
for thin-walled parts like phone cases [Baum 2023 §2.2, p. 6-8](../sources/polymers_15_4220_baum_review.md#2-2-2d-hele-shaw-p-6-8-the-core-of-the-review).

## Assumptions (all must hold)

1. `h ≪ L` — gap much smaller than in-plane extent (aspect ratio ≤ 0.05 is safe; up to 0.2 is borderline).
2. **Stokes regime**: `Re ≪ 1` so inertia `(u·∇)u` is negligible. Automatically true for polymer melts (see [reynolds_number_polymer_melt](reynolds_number_polymer_melt.md)).
3. **Mid-plane symmetry**: `∂u/∂z = ∂v/∂z = ∂T/∂z = 0` at `z = 0`.
4. **No fountain flow**: front advancement is tracked separately, not as part of the Hele-Shaw field.
5. **No surface tension**, no body forces (gravity negligible at these scales).
6. **Constant thermal properties** `λ, cp` (the energy equation's conduction term assumes this).
7. `∂p/∂z = 0` — pressure is z-independent, a direct consequence of (1).

Under these, the 3D momentum equation collapses to just x and y components:

```
∂p/∂x = ∂/∂z(η · ∂u/∂z)
∂p/∂y = ∂/∂z(η · ∂v/∂z)
∂p/∂z = 0
```

with no-slip `u = v = 0` at `z = ±h/2`.

## The pressure equation

Integrating momentum through the gap thickness and combining with the
continuity equation gives the Hele-Shaw pressure equation:

```
∇·(S · ∇p) = 0       in the midplane (x, y)
```

where the **fluidity** `S` is the gap-averaged mobility:

```
S(x, y) = ∫₀ʰ⁄² ρ(T) · z² / η(T, γ̇) dz
```

`S` carries all the information about local thickness, temperature, and
viscosity. For an **isoviscous, isothermal Newtonian** fluid with constant
density, the integral evaluates to `S = ρ·h³ / (24·η)` and the Hele-Shaw
equation simplifies to the familiar form

```
∇·(h³/(12η) · ∇p) = 0
```

which is what MoldMind's [case_generator.py](../../../services/simulation/src/case_generator.py) uses
as motivation for the interFoam case defaults.

## Averaged velocity

After solving for `p`, the gap-averaged velocity components are

```
ū = −∂p/∂x · S / (h/2)
v̄ = −∂p/∂y · S / (h/2)
```

Per Baum §2.2. These are what flows the melt front forward in a Hele-Shaw
simulation.

## Shear rate (gap-averaged form)

Because `u = u(x, y, z)` varies parabolically across the gap (Poiseuille),
the shear rate at a wall is

```
γ̇_wall = |∂u/∂z|_{z=±h/2} = 6·|ū| / h
```

Viscous heating in the energy equation uses `γ̇²` summed through the gap.

## Where Hele-Shaw breaks

- Thick sections (`h/L > 0.2`) → gap-averaging loses accuracy, 2.5D or 3D needed.
- Ribs, bosses, and hubs where flow has a true 3D component.
- Complex corners where the parabolic velocity assumption fails.
- Fountain flow at the melt front (the parabolic assumption breaks near the front).
- Near the gate itself, where the inlet is not a parallel plate.

Commercial practice: use 2.5D surface models (Moldflow dual-domain, Moldex3D eDesign)
that apply Hele-Shaw on triangulated boundaries with "connector elements"
bridging opposing surfaces [Baum 2023 §2.3](../sources/polymers_15_4220_baum_review.md#-2-3-2-5d-surface-model-p-8-9).

## Where in MoldMind

- The **Simple Model** at `services/simulation/src/fill_time.py:140` is a **geodesic proxy for Hele-Shaw**, not a true pressure solver:
  - Local thickness `h(x, y, z)` from 3D distance transform → `fill_time.py:142`
  - Speed field `v ∝ h² / η(T)` matches the Hele-Shaw parabolic velocity scaling → `fill_time.py:182`
  - Viscosity coupling `η(T)` uses Arrhenius, two-pass → `fill_time.py:196`
  - Front advances by fast-marching, skipping the pressure Poisson solve
- The **solver selector** at `services/simulation/src/solver_selector.py:145` routes to `hele_shaw_2d` when `aspect < 0.05` and no undercuts — the classical regime.

## Open questions

- We never compute a pressure field. For DFM heuristics that need `p_max`
  (e.g., clamp force, flow-length ratio), we fall back to the `services/molding/src/pressure_estimation.py` analytical formula instead of a Hele-Shaw solve. Would be good to validate that formula against a Moldflow-class result.
- **synthesis:** The aspect-ratio threshold of 0.05 is our own — Baum doesn't give a hard number. Moldex3D recommends midplane Hele-Shaw up to roughly 0.1 in practice.
