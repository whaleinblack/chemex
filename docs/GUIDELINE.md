# ChemEx Development Guideline

## 1. Purpose

This document defines how ChemEx should be extended.

It exists to keep product decisions, code changes, deployment behavior, and scientific semantics consistent as more tools are added.


## 2. Product Rules

### 2.1 Product Identity

ChemEx is:

- a COF / porous-material computation workbench
- bilingual by default
- tool-oriented rather than content-oriented
- honest about runtime status, warnings, and limitations

ChemEx is not:

- a clone of upstream project websites
- a fake-demo shell with fabricated outputs
- a place to hide raw scientific output from advanced users


### 2.2 UX Principles

Every workflow should preserve these rules:

- Users must be able to upload local files directly.
- Every long task must show real backend-driven progress.
- Every result must show explicit units.
- Warnings must be visible without being confused with fatal failures.
- Raw output should remain accessible.
- Export paths should exist for both structured summaries and raw logs.


### 2.3 Tab Strategy

Each major engine should be represented as either:

- its own top-level tab, or
- a clearly separated mode inside an existing top-level tab

Recommended split:

- `SESAMI` for fast surface-area analysis
- `ZEO++` for geometry-based porous structure analysis
- future `pyGAPS` tab for richer adsorption analysis
- future `RASPA` tab for simulation workflows

Do not overload one tab with unrelated scientific intent.


## 3. Scientific Integration Rules

### 3.1 Upstream Truth

Scientific meaning must follow primary upstream documentation or source code.

Rules:

- use official docs, source, or maintainers' published guidance as the semantic source of truth
- do not rename metrics in a way that changes their scientific meaning
- where a metric is ambiguous, display upstream naming and a short UI explanation


### 3.2 Normalized Result Contract

Every engine integration should expose:

- engine name
- engine version
- user inputs
- normalized metrics
- raw output
- warnings
- artifact URLs

The normalized result should be designed for the UI first, but never discard the raw scientific record.


### 3.3 Input Handling

Input handling must be explicit and layered:

1. upload validation
2. format parsing
3. preprocessing / normalization
4. engine execution
5. result parsing

If preprocessing is incomplete, say so clearly instead of pretending full support.


### 3.4 Units and Labels

All outputs must include units wherever appropriate.

Examples:

- `A`
- `A^2`
- `A^3`
- `m^2/g`
- `cm^3/g`
- `Pa`
- `P/P0`

Charts must not ship without readable axes, ticks, and units.


## 4. Frontend Guidelines

### 4.1 Stack

Current frontend stack:

- React 19
- TypeScript
- Vite
- Mantine

Keep the frontend thin. It should orchestrate jobs, render results, and manage interactions, but not perform scientific computation.


### 4.2 Branding and Visual Language

Keep these stable:

- ChemEx brand
- glass-style floating workspace look
- bilingual copy
- ChemEx wordmark styling and logo placement

Current brand font handling:

- wordmark uses bundled `Rajdhani`
- base UI still uses system sans stacks

Do not switch branding fonts casually. If changed, update both code and docs.


### 4.3 Progress and State

Never use fake timer-only progress again.

Rules:

- progress must be driven by backend job state
- stages should map to understandable UI text
- completed, warning, and failed states must be distinct
- the button state and result state must never contradict each other


### 4.4 Relative Asset Handling

ChemEx must remain deployable under both:

- a root domain such as `chemex.space`
- a subpath such as `/chemex/`

Rules:

- prefer relative asset references in built HTML
- frontend runtime URLs must be derived dynamically
- do not hardcode domain-specific paths in UI logic


## 5. Backend Guidelines

### 5.1 Execution Model

Current backend is Flask-based and uses in-memory job records with worker threads.

Short-term acceptable:

- thread-based background execution
- in-memory job polling

Not acceptable long-term:

- assuming jobs survive restarts
- assuming single-process memory is enough for production-scale workflows


### 5.2 API Namespace Design

Use this pattern for future APIs:

- `/api/health`
- `/api/jobs/<job_id>`
- `/api/<tool>/<action>`

Examples:

- `/api/sesami/bet`
- `/api/zeopp/psd`
- future `/api/zeopp/sa`
- future `/api/pygaps/model-fit`

Keep tool namespaces isolated so integrations do not bleed into one another.


### 5.3 Artifacts

Each job should produce a clear artifact directory under:

- `backend_artifacts/<job_id>/`

That directory should contain:

- original upload when useful
- engine output files
- rendered plots
- structured summaries where possible

Do not hide artifacts only inside logs or temporary memory objects.


### 5.4 Warnings vs Failures

Some scientific engines produce useful output even when exit codes are messy.

Rules:

- if usable output exists, parse it and return a warning state rather than discarding everything
- preserve stderr/stdout for review
- make warning semantics explicit in both backend response and UI


## 6. Repository and Refactor Guidelines

### 6.1 Current Reality

`backend/app.py` currently contains:

- routing
- upload parsing
- SESAMI adapters
- ZEO++ runtime detection
- job handling
- static file serving

This is acceptable for the current prototype stage, but future work should gradually split it.


### 6.2 Recommended Refactor Shape

When refactoring, move toward:

- `backend/routes/`
- `backend/services/`
- `backend/parsers/`
- `backend/jobs/`
- `backend/models/`

Refactor only when it simplifies delivery. Do not perform a large architectural rewrite before adding the next scientific capabilities.


## 7. Deployment Guidelines

### 7.1 Shared Server Safety

ChemEx shares a server with another project.

Hard rule:

- do not modify the map app's codebase or service files unless explicitly requested

Current separation model:

- `chufa.wang` -> map project
- `chemex.space` -> ChemEx
- raw HTTP IP access -> denied


### 7.2 Domain Policy

ChemEx production should treat:

- `https://chemex.space/` as canonical
- `https://www.chemex.space/` as redirect to canonical

Keep `chufa.wang/chemex/` only if it remains useful as a compatibility route. Do not assume it is the long-term public entry point.


### 7.3 Secrets and Local Keys

Never commit:

- SSH private keys
- server access credentials
- API secrets

Any local helper keys used for deployment must remain ignored and documented only operationally, not embedded in public docs.


## 8. Documentation Rules

These files must be updated when relevant changes happen:

- `docs/ROADMAP.md`
- `docs/GUIDELINE.md`
- `docs/HANDOFF.md`

Update docs when any of the following changes:

- supported tools
- supported metrics
- domain / deployment layout
- runtime model
- artifact structure
- major UI information architecture


## 9. Recommended Next Delivery Order

When in doubt, prioritize in this order:

1. make existing workflows more trustworthy
2. add the next highest-value metric for an existing engine
3. improve preprocessing and exports
4. only then add a new heavyweight engine

This keeps ChemEx credible as a scientific tool rather than a shallow feature list.
