# ADR 001: Web-First, Not Plugin-First

## Status
Accepted

## Context
We could deliver MoldMind as:
1. A web application (upload STEP → get results)
2. A CAD plugin (SolidWorks, Fusion 360, NX)
3. A desktop application

## Decision
Web-first.

## Rationale
- **Ship speed:** Web app can ship in weeks. CAD plugins require vendor-specific SDKs, certification, and per-version maintenance.
- **No vendor lock-in:** Mold shops use mixed CAD environments. STEP is the universal exchange format.
- **Distribution:** No install, no IT approval, no version management.
- **Iteration speed:** Deploy daily, not quarterly.
- **Plugin later:** Phase 3 adds CAD plugins for real-time copilot features that genuinely need in-CAD integration.

## Consequences
- Users must export STEP files manually (friction, but acceptable for analysis workflow).
- We lose access to parametric feature tree (STEP is B-Rep only, no history).
- 3D viewer must be built in-browser (Three.js), not native.
- File size limits for upload (~100MB practical limit for web).

## Alternatives Considered
- **Fusion 360 plugin first:** Smaller market, API instability, Autodesk platform risk.
- **SolidWorks plugin first:** Largest installed base, but COM/Windows-only, slow certification.
- **Desktop app (Electron):** Worst of both worlds for v1.
