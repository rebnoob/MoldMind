# MoldMind Roadmap

## Phase 1: DFM / Moldability Analysis (MVP)

**Goal:** Upload a STEP file, get an instant moldability audit.

**Timeline target:** 8-12 weeks to closed beta.

### Milestones

#### M1: CAD Ingestion (Weeks 1-2)
- [ ] STEP file upload via web UI
- [ ] OpenCascade STEP parser in geometry service
- [ ] Tessellation to indexed mesh (vertices + faces)
- [ ] Store original STEP + tessellated mesh in object storage
- [ ] Thumbnail generation
- [ ] Basic Three.js viewer displaying uploaded part

#### M2: Geometry Analysis (Weeks 3-5)
- [ ] Face normal extraction and classification (planar, cylindrical, freeform)
- [ ] Wall thickness analysis (ray-casting approach)
- [ ] Draft angle computation per face relative to pull direction
- [ ] Undercut detection (faces with negative draft)
- [ ] Sharp corner / fillet detection
- [ ] Thin feature detection (ribs, bosses)
- [ ] Basic feature recognition (holes, slots, ribs, bosses)

#### M3: DFM Rules Engine (Weeks 4-6)
- [ ] Rule schema: condition → severity → suggestion → affected geometry
- [ ] Core rules:
  - Insufficient draft angle (< 0.5° warning, < 1° for textured)
  - Wall thickness uniformity (>25% variation = warning)
  - Minimum wall thickness (material-dependent, default 0.8mm)
  - Maximum wall thickness (sink risk > 4mm)
  - Rib-to-wall ratio (should be 50-75% of wall)
  - Sharp corners (stress concentration, < 0.5mm radius)
  - Undercut presence and complexity
  - Deep core / high aspect ratio features
  - Gate location feasibility
- [ ] Composite moldability score (0-100)
- [ ] Per-issue severity: critical / warning / info

#### M4: Results & Visualization (Weeks 5-7)
- [ ] 3D viewer with color-coded face highlighting by issue type
- [ ] Issue list panel with click-to-highlight
- [ ] Cross-section viewer for wall thickness
- [ ] Pull direction selector (user can change and re-analyze)
- [ ] Moldability score dashboard
- [ ] PDF report generation

#### M5: Platform (Weeks 6-8)
- [ ] User auth (JWT)
- [ ] Project / part organization
- [ ] Analysis history
- [ ] Job status tracking (queued → processing → complete)
- [ ] Basic audit trail

#### M6: Polish & Beta (Weeks 8-12)
- [ ] Test with 20+ real parts from mold shop partners
- [ ] Calibrate scoring against expert DFM reviews
- [ ] Performance optimization (target: <60s for typical part)
- [ ] Error handling for malformed STEP files
- [ ] Onboarding flow

---

## Phase 2: Mold Concept Generation

**Goal:** Given a validated part, suggest mold architecture.

- Parting line suggestion (geometry-based + heuristic)
- Pull direction optimization
- Slider / lifter detection and suggestion
- Mold base selection (standard bases)
- Gate type and location recommendation
- Ejector pin placement suggestion
- Multi-cavity layout (2/4/8)
- Concept comparison view

**Key risk:** Parting line generation on complex B-Rep geometry is genuinely hard.

---

## Phase 3: Designer Copilot

**Goal:** Interactive AI-assisted mold design editing.

- Real-time DFM feedback as designer modifies part
- "Fix this issue" one-click suggestions
- Natural language queries about mold design decisions
- Integration with SolidWorks / Fusion 360 via plugin
- Parametric design modification suggestions
- Cost estimation based on mold complexity

---

## Phase 4: Accelerated Simulation

**Goal:** Fast approximate simulation for fill, pack, cool, warp.

- Physics-informed neural network surrogates for Moldflow-class simulation
- Training data from Moldex3D / Moldflow simulation results
- Fill pattern prediction
- Weld line prediction
- Sink mark prediction
- Cooling uniformity analysis
- Warp prediction
- Cycle time estimation

**Key risk:** Surrogate accuracy vs. trust. Must be clearly labeled as approximate.

---

## What We Are Explicitly NOT Building

- A full parametric CAD modeler (use SolidWorks/Fusion/NX for that)
- A replacement for Moldflow/Moldex3D (we complement, not replace)
- A general-purpose DFM tool (injection molding only, at least for 2+ years)
- An AI chatbot that "designs molds" (no LLM-in-the-loop for geometry)
