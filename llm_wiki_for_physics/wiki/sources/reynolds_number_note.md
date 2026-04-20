---
title: Reynolds number + Navier-Stokes — user note
kind: source
type: note
authors: [Lexie]
year: 2026
tags: [reynolds, navier-stokes, wikipedia]
path: lexie_test_raw/reference_paper/fluid dynamics/How to calculate Re.md
updated: 2026-04-20
---

# Reynolds number + Navier-Stokes — user note

**Raw file:** [`../../lexie_test_raw/reference_paper/fluid dynamics/How to calculate Re.md`](../../lexie_test_raw/reference_paper/fluid%20dynamics/How%20to%20calculate%20Re.md)

## TL;DR

Two-line pointer file containing two Wikipedia URLs:

- https://en.wikipedia.org/wiki/Reynolds_number
- https://en.wikipedia.org/wiki/Navier–Stokes_equations

With a comment: *"Navier stokes equations for different conditions"*.

## Interpretation

The user flagged these as the canonical references for:

1. **`Re = ρ·v·L/μ`** — the dimensionless inertia/viscosity ratio. For polymer
   melts in injection molding, with `ρ ≈ 10³`, `v ≈ 0.1`, `L ≈ 10⁻² m`,
   `μ ≈ 10³ Pa·s`, we get `Re ≈ 10⁻³` — i.e. **inertia is always negligible**.
2. **Navier-Stokes** equations with appropriate simplifications for each regime
   (Stokes, Hele-Shaw, creeping flow, etc.).

## Cross-references

- [concepts/reynolds_number_polymer_melt](../concepts/reynolds_number_polymer_melt.md) — where the numerical justification for dropping inertia lives
- [concepts/hele_shaw](../concepts/hele_shaw.md) — the Hele-Shaw approximation relies on Re ≪ 1
- [polymers_15_4220_baum_review](polymers_15_4220_baum_review.md) — peer-reviewed confirmation (p. 6: "inertial terms can be neglected due to the low Reynolds numbers")

## TODO

- Pull the exact derivation chain Wikipedia → Stokes → Hele-Shaw into
  `concepts/navier_stokes_vs_hele_shaw.md` when that stub gets promoted.
