# Brutal Truth

Hard-won realities about building a mold design intelligence platform. This is not marketing — it's the honest engineering picture.

---

## What is actually hard

### 1. pythonocc-core is the whole game and the biggest pain point
It's the only viable open-source B-Rep kernel. It's hard to install, poorly documented, and the API is a thin wrapper over OpenCascade's C++ API which was designed by committee in the 1990s. You will spend more time fighting OCC than writing analysis logic. But there is no alternative unless you pay for Parasolid/ACIS ($$$) or build a kernel from scratch (years).

### 2. Real STEP files are nightmares
They have assembly structures, missing faces, non-manifold geometry, inconsistent units, multiple bodies, and vendor-specific extensions. Robust STEP parsing that works on 95% of real-world files is a 3-6 month grind. Every CAD vendor writes STEP slightly differently. Files from Creo will fail differently than files from SolidWorks which will fail differently than NX.

### 3. Rule calibration is where the product lives or dies
The code to detect a draft angle is easy. The knowledge of what thresholds matter, for which materials, in which contexts, is what makes the product useful. You need experienced mold makers reviewing every rule, on dozens of real parts, iterating the logic. Without this, the tool produces technically correct but practically useless results.

### 4. Parting line generation is a genuine research problem
There is no off-the-shelf algorithm that reliably generates parting lines for arbitrary B-Rep geometry. Academic papers exist but they handle simple cases. Real injection molded parts with complex surface topology, undercuts, and shutoff requirements make this genuinely hard. This is why it's Phase 2, not Phase 1. When you get there, expect it to take 2-3x longer than estimated.

### 5. Wall thickness by ray-casting has known failure modes
Thin ribs, complex curvature, tapered walls — all produce unreliable results. The proper approach (medial axis transform or Voronoi-based) is significantly more complex. v1 should ship with ray-casting + a disclaimer that results are approximate.

### 6. Auth, infra, and DevOps eat real time
SQLite works for demos. PostgreSQL + Redis + MinIO + Celery workers in production is a real operational burden for a small team. Don't underestimate the time spent on infrastructure vs. product features.

### 7. 3D web viewers are harder than they look
Displaying a tessellated mesh is easy. Per-face highlighting with issue coloring, cross-section views, measurement tools, and smooth interaction on large models — that's months of work. Three.js is powerful but low-level.

---

## What is fakeable in demos

- The 3D viewer with colored faces looks impressive even with hardcoded data. A demo with 3-4 carefully chosen STEP files and tuned rules can be extremely compelling.
- The moldability score dashboard looks like a polished product even before the analysis is perfect. Put a number on screen and people react to it.
- PDF report generation is trivial to implement and makes the product feel "enterprise-ready."
- Mock data flows through the whole UI and can impress investors or early design partners before the geometry pipeline is robust.
- A well-designed issue panel with "measured vs. threshold" values looks authoritative even when the measurements are approximate.

---

## What would truly create defensibility

### 1. Depth and accuracy of the rules engine
Not the code — the domain knowledge encoded in it. A rule set calibrated against 500+ real parts with expert feedback is a moat that takes years to replicate. This is knowledge engineering, not software engineering.

### 2. A closed-loop data flywheel (Phase 5+)
Connect DFM predictions to actual mold performance data (cycle time, reject rate, tool wear). The system that learns "this geometry configuration actually caused problems in production" becomes exponentially more valuable. No one has this data set.

### 3. Manufacturing network effects
If mold shops and product companies both use the platform, the data about which designs succeed becomes a unique asset. But this is a multi-year, multi-sided marketplace play.

### 4. Speed of analysis
A 30-second DFM review vs. a 4-hour manual review is the wedge. But a 30-second DFM review that's wrong 40% of the time is worse than useless. **Accuracy first**, speed is table stakes.

### 5. Integration stickiness
Phase 3's CAD plugin creates switching cost. But only after the analysis is trusted enough that designers rely on it daily. Premature plugin development before the analysis is reliable is wasted effort.

---

## The honest competitive picture

Moldex3D, Moldflow, and Plastic Insight all have DFM modules — but they're bolted onto expensive simulation suites that cost $20K+/year. The gap is a standalone, fast, web-accessible DFM tool at a price point mold shops can justify ($500-2000/mo). The window exists, but closes if Autodesk or Hexagon decides to unbundle their DFM analysis.

Startups like Protolabs and Xometry have internal DFM engines but don't sell them as standalone tools. If they did, they'd be the immediate threat.

---

## What we learned building this scaffold

1. **passlib + modern bcrypt versions are broken.** The Python password hashing ecosystem has version conflicts between passlib and bcrypt >= 4.1. Pin bcrypt to 4.0.x or switch to argon2.
2. **SQLAlchemy `metadata` is a reserved attribute name.** You cannot have a column called `metadata` on a Declarative model. Discovered at runtime.
3. **PostgreSQL-specific types (JSONB, UUID, ARRAY) don't work with SQLite.** Cross-database dev requires type abstractions from day one. We had to build GUID, JSONType, and IntArrayType wrappers.
4. **pnpm doesn't read the `workspaces` field in package.json.** It requires a separate `pnpm-workspace.yaml` file.
5. **No Node.js on the target machine.** Don't assume dev environments. Zero-dep local startup (SQLite, local filesystem storage) is essential for onboarding.
6. **The upload flow requires auth but there was no login UI.** End-to-end testing of every user flow matters — building APIs and UIs separately means gaps at the seams.

---

## Summary

The technical work is real but bounded. The hard part is **domain knowledge** — encoding decades of injection molding expertise into rules, calibrating against real parts, and building trust with experienced mold makers who will immediately spot wrong answers. Software engineers can build the platform, but the product quality depends on manufacturing domain experts.
