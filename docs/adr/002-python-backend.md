# ADR 002: Python Backend, Not TypeScript

## Status
Accepted

## Context
The frontend is TypeScript/Next.js. The backend could be TypeScript (consistency) or Python (ecosystem).

## Decision
Python (FastAPI) for all backend services.

## Rationale
- **OpenCascade bindings (pythonocc)** are the only viable open-source B-Rep CAD kernel. They are Python/C++.
- **NumPy/SciPy/trimesh** are essential for geometric computation. No TypeScript equivalents exist at this quality.
- **ML/simulation** work (Phase 4) is entirely Python-ecosystem.
- **FastAPI** is production-grade, async, auto-documented, and type-safe via Pydantic.
- Having one backend language eliminates a serialization boundary between API and geometry services in v1.

## Consequences
- Two languages in the monorepo (TypeScript frontend, Python backend).
- Need shared type definitions (OpenAPI spec generated from FastAPI, consumed by frontend).
- Python packaging/deployment is less polished than Node (mitigated by Docker).
- Team must be comfortable with both languages.

## Alternatives Considered
- **TypeScript everywhere (tRPC):** Would require C++ FFI for OpenCascade, losing the entire Python geometry ecosystem.
- **Go backend:** Same FFI problem, less ML ecosystem.
- **Rust backend:** Great for geometry, but slower iteration speed and smaller hiring pool.
