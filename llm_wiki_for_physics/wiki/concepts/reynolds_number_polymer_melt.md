---
title: Reynolds number for polymer melts
kind: concept
tags: [reynolds, stokes, viscosity, polymer]
sources: [reynolds_number_note, polymers_15_4220_baum_review]
updated: 2026-04-20
---

# Reynolds number for polymer melts

## Summary

For any thermoplastic polymer melt injected at realistic speeds, the Reynolds
number is around **`10⁻³`**. This is four orders of magnitude below the
transition to turbulent flow, and three orders of magnitude below where
inertia matters at all. Every injection-molding fill simulation can therefore
**drop the inertial term `(u·∇)u`** and work in the Stokes regime without
penalty [Baum 2023 §2.2](../sources/polymers_15_4220_baum_review.md#-2-2-2d-hele-shaw-p-6-8-the-core-of-the-review).

## The estimate

```
Re = ρ · v · L / μ
```

Representative numbers for polymer injection moulding:

| Quantity | Value | Source |
|---|---|---|
| Density `ρ` | ~1000 kg/m³ | ABS, PP, PC all within 2× |
| Melt velocity `v` | ~0.1 m/s | Typical gate velocity (10 cm/s) |
| Characteristic length `L` | ~0.01 m (10 mm) | Part thickness or gap |
| Dynamic viscosity `μ` | ~1000 Pa·s | Melt viscosity at injection T |

```
Re = (1000)(0.1)(0.01) / 1000 = 10⁻³
```

## Consequences

1. **Inertia is negligible.** Drop `(u·∇)u` from the momentum equation → Stokes flow.
2. **Laminar always.** The transition to turbulence is at `Re ≈ 2300` — we're nowhere close.
3. **Hele-Shaw is valid** wherever the thin-gap assumption holds (see [hele_shaw](hele_shaw.md)).
4. **Viscous heating dominates over convective cooling** when shear rates are high (thin ribs).

## Sanity check against other fluids

| Fluid / flow | Re |
|---|---|
| Blood in capillary | 10⁻³ |
| Glycerol pipe | 10⁻¹ |
| **Polymer melt (injection)** | **10⁻³** |
| Water pipe | 10⁵ |
| Atmospheric wind | 10⁷ |

## Where in MoldMind

- [solver_selector.py:113-115](../../../services/simulation/src/solver_selector.py) computes Re with these reference values and displays it in the Auto-mode recommendation card.
- [fill_time.py](../../../services/simulation/src/fill_time.py) drops inertia implicitly — our speed model `v ∝ h² / η` is the Hele-Shaw low-Re scaling.

## Cross-references

- [hele_shaw](hele_shaw.md) — the low-Re assumption is what makes Hele-Shaw valid
- [filling_phase](filling_phase.md) — see the governing-equation reductions there
- [reynolds_number_note](../sources/reynolds_number_note.md) — user's raw note

## Open questions

- **synthesis:** some high-speed injection (e.g., micro-moulding, thin LED lens
  gates) can push local velocity to 1 m/s. Re still `10⁻²` — safe. If we ever
  model something like a sprue-less micro-mould, re-check.
