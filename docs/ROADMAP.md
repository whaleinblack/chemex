# ChemEx Product Roadmap

## 1. Product Positioning

ChemEx is a bilingual web toolbox for COF and porous-material computation.

The near-term product goal is not to reproduce upstream websites, but to turn mature open-source calculation cores into a clean, research-friendly web workbench with:

- local file upload
- explicit parameter control
- real job progress
- structured results + raw output
- downloadable artifacts
- deployable domain-separated web services

Current domain split:

- `https://chemex.space/` -> ChemEx
- `https://chufa.wang/` -> existing map project


## 2. Current Baseline

As of `2026-03-26`, ChemEx already has:

- React + TypeScript + Vite + Mantine frontend
- Chinese / English UI switching
- branded glass-style workbench UI
- SESAMI tab with version selector:
  - `SESAMI 2.9`
  - `SESAMI 1.0`
- ZEO++ tab with live PSD workflow
- backend-driven job progress polling
- figure gallery, enlarged preview, raw output export, and artifact serving
- root-domain and subpath compatible frontend asset resolution
- production deployment on a shared server with domain separation

This is the base for the next phases. The roadmap below assumes we keep ChemEx focused on porous-material computation rather than turning it into a generic file portal.


## 3. Product Workstreams

ChemEx should evolve along five parallel workstreams.

### 3.1 Structure Intake

- CIF / CSSR / AIF / CSV upload and validation
- structure preprocessing and conversion
- metadata extraction
- reusable presets for common adsorbates and probes

### 3.2 Geometry Analysis

- pore diameters
- channel dimensionality
- surface area
- accessible volume
- probe-occupiable volume
- pore size distribution

### 3.3 Adsorption Analysis

- BET / BET+ESW
- ML area prediction
- model fitting and comparison
- multicomponent adsorption analysis

### 3.4 Reporting and Data Products

- result tables
- charts
- markdown / txt / csv / json export
- reproducible calculation reports
- task history and comparison

### 3.5 Platform and Operations

- stable deployment
- long-job execution model
- artifact lifecycle
- logging / monitoring
- domain and environment separation


## 4. Recommended Tool Expansion

### 4.1 Priority External Tools

These are the most promising next integrations after the current ZEO++ + SESAMI baseline.

1. `pyGAPS`
- Best next step for experimental adsorption analysis.
- Good fit for web workflows.
- Can extend ChemEx from BET-only into broader isotherm analytics.

2. `RASPA3`
- Best next step for adsorption simulation and separation workflows.
- High scientific value, but also the heaviest backend lift.
- Should come after preprocessing, queueing, and artifact discipline are stronger.

3. `PoreBlazer`
- Strong complement to ZEO++ for geometric cross-checking.
- Useful for pore volume, surface area, and PSD comparison workflows.

4. `pymatgen`
- Not a primary tab by itself, but extremely valuable as a preprocessing layer.
- Especially useful for CIF cleanup, parsing, and structure normalization.


## 5. Versioned Roadmap

## v0.6 Core Stabilization

Goal: make the current two-tool foundation trustworthy for daily internal use.

Scope:

- ZEO++:
  - add `-res`
  - add `-chan`
  - improve PSD result labeling and parameter guidance
  - standardize warnings when Windows runtime returns non-zero after writing output
- SESAMI:
  - expose `BET+ESW`
  - make SESAMI version choice visible in result cards and exports
  - expose a small set of advanced fit controls in an expert panel
- Shared:
  - stronger upload validation
  - clearer units everywhere
  - normalized error states and warning states
  - domain-level smoke tests in deployment checklist

Exit criteria:

- user can upload a typical CIF / CSV / AIF and understand success vs warning vs failure without reading logs
- ZEO++ and SESAMI outputs have stable downloadable summaries
- documentation is kept in sync with production


## v0.7 Geometry Workbench

Goal: turn the ZEO++ tab into a genuinely useful geometry suite instead of a PSD-only entry point.

Scope:

- add `-sa`
- add `-vol`
- add `-volpo`
- show channel / pocket contributions when present
- support result comparison across multiple runs
- add csv / json export for normalized numeric outputs

Recommended UI shape:

- same tab, multiple calculation modes
- simple mode + expert mode
- persistent run summary card on the right

Exit criteria:

- one structure upload can support at least five geometry metrics in a consistent UX
- exported outputs are analysis-friendly and not just raw text dumps


## v0.8 Adsorption Analysis Suite

Goal: expand SESAMI into a broader adsorption-analysis workspace.

Scope:

- add `betml`
- integrate `pyGAPS` for model-driven isotherm analysis
- add Henry / Langmuir / selected isotherm fitting
- support richer upload metadata
- add downloadable analysis report bundles

Recommended product split:

- `SESAMI` remains the fast, focused surface-area route
- `pyGAPS` becomes the broader adsorption-analysis route

Exit criteria:

- ChemEx can handle both fast BET-style screening and richer isotherm interpretation
- users can compare outputs from different analysis engines on the same dataset


## v0.9 Structure Preparation and Simulation Bridge

Goal: reduce preprocessing friction and prepare the jump from geometry analysis to simulation workflows.

Scope:

- add `pymatgen`-based structure preprocessing:
  - CIF validation
  - atom-name normalization
  - format conversion pipeline
- add more ZEO++ exports:
  - `-block`
  - `-gridG`
  - `-gridBOV`
  - `-nt2`
- introduce a pre-simulation handoff format for `RASPA3`

Exit criteria:

- users can move from uploaded raw structure to simulation-ready artifacts without leaving ChemEx


## v1.0 Research Platform

Goal: move from prototype workbench to durable research platform.

Scope:

- project / task history
- persistent job storage
- artifact retention policy
- batch execution
- reusable templates
- report generation
- optional user / team separation
- monitoring and admin views

Possible headline capability:

- upload one structure
- run geometry analysis
- run adsorption analysis
- export a report bundle
- hand off a prepared input set to simulation workflows


## 6. Scientific Backlog by Existing Tools

### 6.1 ZEO++ Backlog

High priority:

- `-res`
- `-resex`
- `-chan`
- `-sa`
- `-vol`
- `-volpo`

Medium priority:

- `-ray_atom`
- `-block`
- `-strinfo`
- `-oms`

Advanced / visualization:

- `-gridG`
- `-gridBOV`
- `-nt2`
- `-xyz`
- `-v1`


### 6.2 SESAMI Backlog

High priority:

- `BET+ESW`
- `betml`
- richer advanced fit controls
- adsorbate-specific expert options

Medium priority:

- result comparison between `1.0` and `2.9`
- better plot annotations
- automated markdown / pdf report export


## 7. Platform Risks to Watch

- Jobs are currently in memory, so service restart loses job state.
- Backend logic is concentrated in a single `backend/app.py`, which is fine for fast iteration but not ideal for long-term maintainability.
- ZEO++ currently accepts uploaded structure files as provided; robust preprocessing and normalization are still thin.
- Scientific semantics must always follow upstream documentation, not UI convenience assumptions.
- Shared-server deployment means ChemEx changes must not leak into the map project.


## 8. Near-Term Recommendation

If we only fund one next sprint, the best return is:

1. ZEO++ `-res`, `-chan`, `-sa`, `-vol`, `-volpo`
2. SESAMI `BET+ESW`
3. CIF preprocessing via `pymatgen`
4. persistent job/result storage

That combination would move ChemEx from “working prototype” to “real internal research tool.”
