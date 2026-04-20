# Physics Wiki Schema

Configuration for the LLM-maintained knowledge base in `llm_wiki_for_physics/`.
Follows the LLM-Wiki pattern: raw sources are immutable, the wiki is the
LLM's compounding synthesis, and this schema is the contract between us.

## Scope

Injection-molding simulation physics and its neighbouring CFD topics:
- Filling-phase modelling (1D / 2D / 2.5D / 3D)
- Rheology for polymer melts (Power-Law, Carreau, Cross, WLF, Arrhenius)
- Numerical methods (FDM, FEM, FVM, VOF, level-set, Hele-Shaw)
- Gate / runner / cavity design & optimisation
- Relevant reference code (open-source simulators, PIC/SPH fluid demos)

Out of scope: general polymer chemistry, mold cooling circuits unrelated to
simulation, packaging / shipping, business / cost analysis.

## Directory layout

```
llm_wiki_for_physics/
├── Schema/
│   └── CLAUDE.md          # this file
├── lexie_test_raw/        # raw sources — NEVER modified by the LLM
│   ├── reference_paper/   # PDFs, md notes, web-clipped articles
│   └── reference_git/     # cloned / copied open-source projects
└── wiki/                  # all LLM-authored pages live here
    ├── index.md           # content catalogue
    ├── log.md             # append-only chronological log
    ├── sources/           # one page per ingested raw source
    ├── concepts/          # topic synthesis pages (filling_phase, rheology, …)
    └── entities/          # people, software packages, repos
```

## Page conventions

Every page has YAML frontmatter:

```yaml
---
title: Human-readable title
kind: source | concept | entity
tags: [hele-shaw, viscosity, …]
sources: [relative/path/to/raw.pdf, …]   # for concept pages: the raw sources cited
updated: 2026-04-20
---
```

**Cross-linking:** use Obsidian-style wikilinks `[[concepts/rheology|rheology]]`
or relative markdown links `[rheology](../concepts/rheology.md)`. Prefer
wikilinks — Obsidian users get the graph view for free.

**Citations:** inline, `[Baum 2023 §2.2](../sources/polymers_15_4220_baum_review.md#2.2-hele-shaw-2d-model)`.
Never cite a fact without pointing at a source page. If a claim is the LLM's
synthesis, say so explicitly ("**synthesis:**").

**Math:** plain LaTeX-ish text, e.g. `η₀ = D₁·exp(A₁(T−T_s)/(A₂+T−T_s))`.
Optional KaTeX blocks (`$$ … $$`) if Obsidian plugins render them.

**Length:** concept pages 200-600 lines; source pages 80-300 lines; entity
pages 30-150 lines. Break up anything longer.

## Source page template

```markdown
---
title: <short title>
kind: source
type: paper | note | repo | article
authors: [...]
year: 2023
tags: [...]
path: lexie_test_raw/…
updated: YYYY-MM-DD
---

# <Title>

**Reference:** <citation line>
**Raw file:** [`lexie_test_raw/...`](../../lexie_test_raw/...)

## TL;DR
<3-5 bullets, the single-sentence verdict each>

## Key claims
<numbered list, each claim links the concept page it updates>

## Notes by section
<sub-headings with page/line refs>

## Cross-references
<links to concept pages that cite this source>
```

## Concept page template

```markdown
---
title: <concept>
kind: concept
tags: [...]
sources: [...]
updated: YYYY-MM-DD
---

# <Concept>

## Summary
<1-2 paragraphs, with inline source cites>

## Definitions / equations
<formal statements, cite the source each comes from>

## Variants
<subsections per variant, each with citations>

## Where this appears in MoldMind
<link code locations in the main repo: `services/simulation/src/fill_time.py:170`>

## Open questions / contradictions
<things the sources disagree on, or that need more reading>
```

## Ingest workflow

When a raw source lands in `lexie_test_raw/`:

1. Read the whole thing (or paginate for PDFs). Take notes.
2. Write / update the `sources/<slug>.md` page.
3. Update every concept page that the source touches. Leave a `**synthesis:**`
   note where you resolve or flag a disagreement with prior sources.
4. Append to `log.md`:
   ```
   ## [YYYY-MM-DD] ingest | <slug> | <one-sentence takeaway>
   ```
5. Update `index.md` (add the source page, bump any concept pages in the TOC).
6. If the source references external URLs that look critical, follow them and
   treat them as secondary sources (log as `## [YYYY-MM-DD] web | <url>`).

## Query workflow

When the user asks a question:

1. Read `index.md`, then any concept pages whose titles match the question.
2. If no concept covers it, check source pages (grep their TL;DRs).
3. Synthesise an answer with inline citations. If the answer is substantial,
   **file it as a new page** (a comparison, a derivation, a recommendation) and
   log it: `## [YYYY-MM-DD] query → page | <title>`.

## Lint workflow

Run periodically with `lint the wiki`:

1. Find orphan pages (no inbound links). Either link them or delete.
2. Find concepts cited in source TL;DRs but missing a concept page → create.
3. Find contradictions: same claim with different numbers / conclusions across
   pages. Reconcile or flag `**contradiction:**` inline.
4. Find stale dates (concept page older than the newest source that cites it).
   Re-read and update.

## Authoring voice

- Write for a future reader (probably the user, possibly another LLM session).
  State things plainly, include units, link where claims live.
- Skip filler. A concept page should be dense, not verbose.
- If you don't know something, say so. Don't synthesise physics that isn't in
  the sources.
- When updating a page, preserve the structure. Don't rewrite a page's
  ontology unless a new source forces it.

## MoldMind integration

When a wiki concept has a direct implementation in the main repo, link the
code from the concept page (use absolute-like path `services/simulation/src/fill_time.py:142`).
This keeps the simulation code and the physics wiki in sync.
