# ADR 003: Deterministic Rules Engine, Not LLM-Driven Analysis

## Status
Accepted

## Context
DFM analysis could be implemented via:
1. Hand-coded rules with geometric analysis
2. LLM-based reasoning over geometry descriptions
3. ML classification models
4. Hybrid approach

## Decision
Deterministic rules engine with computational geometry for Phase 1. ML only for feature classification where rules are insufficient.

## Rationale
- **Explainability:** Engineers must understand WHY a feature is flagged. "Draft angle on face #47 is 0.3°, minimum is 1.0° for ABS" is useful. "AI thinks this might be hard to mold" is not.
- **Reproducibility:** Same input must produce same output. LLMs are stochastic.
- **Accuracy:** Geometric properties (angles, thicknesses, radii) must be computed, not estimated. An LLM cannot measure a draft angle.
- **Trust:** Mold shops stake money and reputation on DFM calls. They need to verify, not trust.
- **Editability:** Rules can be tuned per material, per customer, per shop. Black-box models cannot.

## Where AI Actually Helps (Later)
- **Feature classification:** Identifying that a geometry cluster is a "snap fit" vs a "living hinge" — pattern recognition on B-Rep topology.
- **Suggestion ranking:** When multiple fixes exist, ML can rank by historical success.
- **Surrogate simulation:** Neural network approximations of fill/pack/cool (Phase 4).
- **NLP interface:** Natural language queries about analysis results (Phase 3).

## Consequences
- Must manually encode injection molding DFM knowledge (large but finite rule set).
- Rules need calibration against expert reviews (planned for M6).
- Cannot handle novel/exotic geometries without new rules.
- Competitive moat is in rule quality and geometric analysis depth, not model training.
