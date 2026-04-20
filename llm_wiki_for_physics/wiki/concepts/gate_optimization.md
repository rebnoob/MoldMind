---
title: Gate position optimization
kind: concept
tags: [gate, optimization, dfm, symmetry, centre-of-mass, search]
sources: [optimal_gate_position_note, polymers_15_4220_baum_review]
updated: 2026-04-20
---

# Gate position optimization

## Summary

Where the melt enters the cavity determines the filling pattern, weld-line
location, clamp force, and residual stress distribution. There is no closed-form
"best" gate — it's an optimisation over a geometry-dependent search space with
a physics-based objective function.

The practical approach MoldMind uses is the one in
[optimal_gate_position_note](../sources/optimal_gate_position_note.md):

- **Symmetric parts**: evaluate a handful of candidates on the part's planes of symmetry (centres of XY / XZ / YZ bounding-face projections).
- **Asymmetric parts**: evaluate candidates along axis-parallel lines through the centre of mass.

Each candidate is scored by running a fast Simple-Model fill-time evaluation
and the best one wins.

## Objective function

For each candidate gate `g`, we compute the per-vertex fill-time field
`T_fill(v; g)` and score it. Common objectives:

| Objective | Formula | What it captures |
|---|---|---|
| **Max fill time** (lower is better) | `max_v T_fill(v)` | Balanced flow — the last-filled region reaches the front in minimum time |
| Fill-time uniformity | `stdev_v(T_fill) / mean_v(T_fill)` | How even the filling is |
| Flow-length ratio | `max_v T_fill / h_nominal` | Weld-line risk proxy (too long → cold front) |
| Front-convergence count | count of saddle points in `T_fill` | Weld-line count proxy |

MoldMind's v1 uses **max fill time** as the single objective. It's monotonic,
fast to evaluate, and has a clear interpretation: minimise the longest path the
melt has to travel.

## Candidate strategies

### `symmetric_centers` (3 candidates)

For a box-like part, place candidates at the **centres of the three principal
bounding faces**:

- XY-plane centre: `(cx, cy, z_max)` — top face
- XZ-plane centre: `(cx, y_min, cz)` — front face (or `y_max`)
- YZ-plane centre: `(x_min, cy, cz)` — side face

For a phone case (largest face on XY), the XY-plane centre is the physically
meaningful default — the gate sits at the centre of the back cover, which
minimises the longest flow path to any edge.

### `com_axes` (9 candidates)

For an asymmetric part, compute the **centre of mass** and sample 3 points
along each axis-parallel line through it:

- Along X: `(cm_x ± α·extent_x, cm_y, cm_z)` for `α ∈ {0, 0.25, 0.5}`
- Along Y: `(cm_x, cm_y ± α·extent_y, cm_z)` similar
- Along Z: `(cm_x, cm_y, cm_z ± α·extent_z)` similar

This gives 9 candidates focused on the physical centre of the part.

### `exhaustive_xy_grid` (N×N candidates, slower)

Sample an `N × N` grid of candidates on the largest face (typically XY for a
phone case). N = 5 gives 25 candidates, ~30 s total. Used when the user wants
to see a **heatmap** of gate-quality over the face, not just the best point.

## Phone-case default (MoldMind)

For a phone case, the largest face area is on the XY plane (back cover).
The default gate the user specified is **the centre of the XY plane**, which
`gate="xy_center"` maps to:

```
(cx, cy, z_top)  where (cx, cy) = bbox-centre of the part, z_top = max z
```

This is also the recommendation a `symmetric_centers` search would return
for a plate-like part — so the default is consistent with the optimisation
algorithm.

## Where in MoldMind

| Piece | File | What it does |
|---|---|---|
| `gate` param in Simple Model | `services/simulation/src/fill_time.py` | Accepts `"top_z"`, `"top_y"`, `"top_x"`, **`"xy_center"`**, **`"xz_center"`**, **`"yz_center"`**, or explicit `(x, y, z)` |
| Gate optimizer | `services/simulation/src/gate_optimizer.py` | `optimize_gate(vertices, indices, strategy, max_grid)` returns ranked candidates |
| API endpoint | `apps/api/src/routes/analysis.py:/simulation/gate/optimize/{part_id}` | Triggers the optimizer on an already-processed part |

## Algorithm sketch

```python
def optimize_gate(vertices, indices, strategy="symmetric_centers", max_grid=64):
    candidates = pick_candidates(vertices, strategy)
    results = []
    for gate_xyz in candidates:
        fill = compute_fill_time(vertices, indices, gate=gate_xyz, max_grid=max_grid)
        score = fill["max_time"]           # lower = better
        results.append({"gate": gate_xyz, "score": score, "fill_meta": fill_meta})
    results.sort(key=lambda r: r["score"])
    return results
```

We downshift `max_grid` from the default 96 to 64 for speed — the optimiser
runs several fill evaluations and we want it responsive. The winning gate can
then be re-evaluated at full resolution for the final visualisation.

## Open questions

- **synthesis:** `max fill time` as the sole objective ignores weld-line risk
  and clamp force. A weighted score like
  `0.6 * normalized_max_time + 0.3 * flow_ratio + 0.1 * confluence_count`
  would be more faithful to DFM practice. We'll add this when session 3
  produces real flow-front convergence detection.
- **synthesis:** The user's note doesn't address **gate type** (direct vs edge
  vs submarine). Position ≠ type. A gate at the XY centre might be a direct
  gate in practice, which leaves a visible vestige — an edge gate on the
  perimeter would be cosmetically cleaner but filling-wise worse. This is
  captured in the [molding_plan] panel (`services/molding/src/tooling_assessment.py`)
  but not in the optimiser.

## Cross-references

- [optimal_gate_position_note](../sources/optimal_gate_position_note.md) — the user heuristic this implements
- [filling_phase](filling_phase.md)
- [hele_shaw](hele_shaw.md) — the physics underlying the fill-time objective
