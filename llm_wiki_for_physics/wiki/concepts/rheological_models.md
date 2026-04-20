---
title: Rheological models for polymer melts
kind: concept
tags: [rheology, cross, wlf, arrhenius, carreau, power-law, viscosity]
sources: [polymers_15_4220_baum_review]
updated: 2026-04-20
---

# Rheological models — viscosity `η(T, p, γ̇)`

## Summary

Polymer melts are **strongly shear-thinning** and **temperature-sensitive**.
Picking a rheological model is the second-biggest decision after dimensionality
(see [spatial_dimensionality](spatial_dimensionality.md)). The hierarchy runs
from trivial (Power-Law) to production-grade (Cross-WLF) [Baum 2023 §2.5, p. 10-14](../sources/polymers_15_4220_baum_review.md#-2-5-rheology-p-10-14).

In broad strokes, any real injection-molding viscosity model has three
pieces that multiply:

1. **Zero-shear viscosity `η₀(T, p)`** — low-shear plateau, temperature & pressure dependent
2. **Shear-thinning factor** — Power-Law, Carreau, or Cross form
3. **Temperature-shift factor** — Arrhenius or WLF; multiplies `η₀`

## Shear-thinning families

### Power-Law (fastest, crudest)

```
η(γ̇) = m · γ̇^(n−1)
```

`n < 1` for shear-thinning, `n = 1` for Newtonian. Straight-line fit in
log-log space. **Fails at low shear rate** (viscosity diverges). Fine for
the high-shear filling regime; not for packing.

### Carreau (1979)

```
η(γ̇) = η_∞ + (η₀ − η_∞) · [1 + (λ·γ̇)²]^((n−1)/2)
```

Smooth transition from Newtonian plateau `η₀` to Power-Law regime.

### Bird-Carreau-Yasuda

Carreau with an extra exponent `a`:

```
η(γ̇) = η_∞ + (η₀ − η_∞) · [1 + (λ·γ̇)^a]^((n−1)/a)
```

Slightly better fit in the transition region. Overkill for most DFM work.

### Cross (de-facto commercial standard)

```
(η − η_∞) / (η₀ − η_∞) = 1 / (1 + (K·γ̇)^(1−n))
```

Or in the `η_∞ → 0` simplification used in Moldflow:

```
η(γ̇) = η₀ / (1 + (η₀·γ̇ / τ*)^(1−n))
```

`τ*` is the critical shear stress at which the melt starts to shear-thin.
**This is what Moldflow, Moldex3D, and C-Flow ship by default.**

### Herschel-Bulkley, Bingham

Yield-stress models. Relevant for ceramic-powder feedstocks, metal injection
moulding, or very high-filler compounds. Out of scope for standard thermoplastic
injection.

### Second-order (Moldflow, 1980s)

Polynomial fit in `(ln γ̇, T)` with 6 parameters. Empirical, hard to relate
to physics. Still supported in Moldflow's material database but mostly legacy.

## Temperature shift factors

These multiply `η₀` (the zero-shear value) to incorporate temperature (and
sometimes pressure) dependence.

### Arrhenius (semi-crystalline)

```
η₀(T, p) = B · exp(T_b / T) · exp(β · p)
```

Simple two-parameter (three with pressure). Widely used for PP, PE, PA —
materials where the glass transition is well below the melt temperature.
**What MoldMind currently uses** (in `fill_time.py`: `η = η₀ · exp(B·(1/T − 1/T_ref))`).

### WLF (Williams-Landel-Ferry, amorphous)

```
η₀(T, p) = D₁ · exp(−A₁·(T − (D₂ + D₃·p)) / (A₂ + T − D₂))
```

Five-parameter. Much more accurate near the glass transition (amorphous
polymers: PC, PMMA, ABS). Baum §2.5.5 p. 12-13, §2.5.8 p. 14.

## The full commercial stack

Production simulators multiply Cross and WLF:

**Cross-WLF:**

```
η(T, γ̇) = η₀(T) / (1 + (η₀(T)·γ̇ / τ*)^(1−n))
η₀(T) = D₁ · exp(−A₁·(T − D₂) / (A₂ + T − D₂))
```

Seven material constants: `η_∞ ≈ 0`, `τ*`, `n`, `D₁`, `D₂`, `A₁`, `A₂`. Available
for hundreds of grades in Moldflow's material library and CoreTech's databases.

**Cross-Arrhenius:** drop-in replacement of WLF with Arrhenius for
semi-crystalline materials. Simpler to calibrate, often used in academic papers.

## When to use which (synthesis)

| Regime | Model |
|---|---|
| Quick prototype / educational | Power-Law (or our Arrhenius `η(T)`) |
| Thin-walled thermoplastic at high shear | Power-Law + Arrhenius (borderline OK) |
| Any commercial-grade DFM analysis | **Cross-WLF** |
| Amorphous near Tg | WLF is mandatory |
| Semi-crystalline melt-processed | Cross-Arrhenius is enough |
| Ceramic / metal injection moulding | Herschel-Bulkley |

**synthesis:** MoldMind's current Arrhenius-only approach is adequate for
fill-sequence visualisation and gate-placement ranking, but **not** for
predicting clamp force, cycle time, or weld-line location accurately. Adding
Cross-WLF is Session 3 work on the OpenFOAM path.

## Where in MoldMind

| Piece | File | Model used |
|---|---|---|
| Simple Model viscosity coupling | `services/simulation/src/fill_time.py:196` | Arrhenius on `η₀`; no shear-thinning |
| 2D Hele-Shaw flow GIF (historical) | `services/simulation/src/hele_shaw.py` | Same Arrhenius; no Cross |
| Planned OpenFOAM | `services/simulation/src/case_generator.py` | Newtonian (session 1); Cross-WLF (session 3) |

## Open questions

- What's the best default material for the UI? Currently defaulting to ABS-ish
  `η₀ = 1000 Pa·s`, `T_inj = 250 °C`. Should expose a material picker that
  swaps in real Cross-WLF coefficients from a public database.
- **Contradiction:** Baum §2.5.1 says Power-Law "is often used to model flows
  in injection molding technology" (p. 11) but also §2.5.8 says Cross is the
  modern standard. **synthesis:** Power-Law is used *inside* simpler research
  codes or as a quick first pass; commercial software defaults to Cross-WLF.
