---
title: Optimal Injection Gate Position — user note
kind: source
type: note
authors: [Lexie]
year: 2026
tags: [gate, optimization, dfm, runner, heuristics]
path: lexie_test_raw/reference_paper/injection molding/how to figure out the optimize position for injection molding.md
updated: 2026-04-20
---

# Optimal Injection Gate Position — user note

**Raw file:** [`../../lexie_test_raw/reference_paper/injection molding/how to figure out the optimize position for injection molding.md`](../../lexie_test_raw/reference_paper/injection%20molding/how%20to%20figure%20out%20the%20optimize%20position%20for%20injection%20molding.md)

## TL;DR

- Practical gate-placement rules of thumb, mixed with a Bing-aggregated DFM overview.
- The **heuristic the user authored** at the top is the actionable bit:
  > **Symmetric parts** → try the centre of the XY / XZ / YZ planes (3 candidates).
  > **Asymmetric parts** → try axis-parallel lines through the centre of mass.
- The aggregated DFM text below is a general primer on gate / runner / orientation
  considerations — useful as a checklist but not a physical model.

## Key claims

1. For symmetric geometry, the optimum gate often sits on a plane of symmetry at the centroid of that plane's projection. → [gate_optimization](../concepts/gate_optimization.md#symmetric-parts)
2. For asymmetric geometry, restrict the search to lines parallel to the coordinate axes through the centre of mass (a low-dimensional, physically motivated search space). → [gate_optimization](../concepts/gate_optimization.md#asymmetric-parts)
3. DFM-relevant gate-placement objectives (from the aggregated text):
   - Balanced, unidirectional flow
   - Fill thickest sections first, thinner regions last
   - Minimise sink marks, warp, and weld lines
   - Respect material rheology (higher-viscosity materials → larger gates / different runner)
   - Respect draft angles for ejection
4. Common gate types and their tradeoffs (edge / submarine / direct) — cosmetic vs stress vs weld-line tradeoff.

## Heuristic, verbatim

> 比较朴实的办法
> try out
> 如果是对称的话
> the center of xy, xz, yz plane; (3 options)
>
> 如果不对称的话
> try out center of mass 与 x y z 轴平行的连线

**Translation / synthesis:**
Try the naive options first — for a symmetric part there are only three candidate
planes (XY, XZ, YZ) and the gate is at each plane's geometric centre. For an
asymmetric part, parametrise the candidate gate by picking one coordinate axis
and sweeping along the line through the centre of mass parallel to that axis.

## Downstream DFM context

The aggregated content restates standard DFM guidance (balanced flow, runner
type, material rheology, draft angles, gate type tradeoffs) with links to
several trade-shop blogs. Those sources are **not** peer-reviewed — treat them
as industry folklore, not physics. They are useful for building a UI /
reporting layer but shouldn't override a proper Moldflow-class simulation.

Referenced sources (for possible future web-ingest):
- shinzoft.com — DFM in injection molding
- seawinindustrial.com — processes/technology
- gotomold.com — design guidelines
- zetarmold.com — runner and gate design
- firstmold.com — gate types
- aaamould.com — gate placement strategies
- capablemaching.com — mold flow analysis

## Cross-references

- [concepts/gate_optimization](../concepts/gate_optimization.md) — our implementation of this heuristic lives there
- [polymers_15_4220_baum_review](polymers_15_4220_baum_review.md) — the peer-reviewed baseline for *how* to simulate once a gate is chosen

## Relevance to MoldMind

The heuristic in this note is **directly implemented** in
`services/simulation/src/gate_optimizer.py`:

- `strategy="symmetric_centers"` → the 3 plane-centre candidates.
- `strategy="com_axes"` → axis-parallel lines through the centre of mass
  (for asymmetric parts).
- Default UI behaviour for phone cases: the largest face is XY → default gate
  = centre of the XY plane (the top of the back cover in the user's mental model).
