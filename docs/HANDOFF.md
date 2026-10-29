# ChemEx Handoff

## Explicit conformer candidate workflow

- A failed fractional-occupancy/grouped-disorder job exposes `errorCode: cif_disorder`. The UI offers “生成候选有序模型并计算”, with 1–4 candidates (default 2), after this explicit user choice.
- `disorderStrategy=ordered_candidates` matches symmetry-expanded local fragments by identical fixed-atom anchor sets. Equal composition and group populations are checked. Periodic overlap / nonbonded-heavy contacts and neighbour-count anomalies are constrained before selecting diverse arrangements; original parent symmetry is not reapplied to the mixed P1 model.
- A bounded search (200000 nodes, pool 128) reports truncation. Multiple local units must reproduce occupancies within 1%; otherwise request a stoichiometric supercell. Unknown/ungrouped occupancies, substitution/vacancy disorder, implicit single-group alternatives, ambiguous anchors and metal coordination remain unsupported by the candidate adapter.
- Results contain `orderedModels` and `disorderSummary`, a model selector, explicit per-model engine output and TXT attachment, candidate CIF downloads, an audit JSON and candidate metric ranges. The original upload is unchanged. Each job has isolated `ordered-models/model-N/` artifacts.
- These are screened representative periodic candidates, not energy-minimized structures or inferred real disorder statistics. No ensemble mean or confidence interval is claimed.
- ZEO++ run URLs carry `?job=<id>` so the existing in-memory job can be reopened for inspection; service restarts still lose the in-memory job record. Durable artifacts remain available.
- Regression command adds `backend.test_disorder`; its public fixtures are synthetic ethane conformers. Keep all real research CIFs and their derived models out of Git.

## Research reliability update (2026-10-29)

- Volume cards distinguish AV/NAV and POAV/PONAV. Missing channel/pocket fields remain unknown and display “未提供 / Not reported”; measured zeros remain zero.
- TXT exports use `GET /api/zeopp/export/<job_id>/<mode>.txt` with `Content-Disposition: attachment`, a stable `chemex-<mode>.txt` name and exact raw bytes. The route reads the output file, independent of in-memory jobs. MD blob URL cleanup is delayed to allow consumption; export names use the result's mode.
- Install `backend/requirements-structure.txt` into the ChemEx virtual environment before restarting the updated backend. CIF validation must not silently fall back to the raw engine reader if Gemmi is missing.
- Ordered CIFs are expanded to full P1 with Gemmi; special-position duplicates are handled by symmetry expansion and legal multiline atom records are parsed. Original uploads are preserved. Staged models and preparation metadata are job artifacts.
- Fractional/unknown occupancy and explicit disorder groups are rejected with an actionable bilingual error. General mutually exclusive conformer selection or disorder-ensemble averaging is not implemented. Users must supply physically consistent ordered configurations; changing output density alone does not repair geometry.
- Regression command: `python -m unittest backend.test_zeopp_execution backend.test_zeopp_science backend.test_zeopp_export -v`, followed by `npm ci`, `npm run build` and a background browser check. Synthetic test structures only; do not publish calculation uploads or private CIFs.
- Production `/research/` serves a snapshot at `/srv/chemex/home/current/research/`, while `/research/api/` proxies the service at port 4180. Updating `/srv/chemex/app/dist` alone does **not** update the visible research workbench. Inspect live source differences, retain a backup and update only this research snapshot. Preserve homepage, auth gate and unrelated applications.
- Deployment status must be reported separately from local implementation/testing. SSH credentials are ignored; never add `server_key` or `known_hosts` to a commit.

## 1. Project Summary

ChemEx is a bilingual web application for porous-material and COF computation.

Current live scientific workflows:

- `SESAMI BET`
  - `SESAMI 2.9`
  - `SESAMI 1.0`
- `ZEO++ PSD`

The product is no longer tied only to `chufa.wang/chemex/`.
It now supports:

- root-domain hosting
- subpath hosting

Current public domains:

- `https://chemex.space/` -> ChemEx
- `https://www.chemex.space/` -> redirect to `https://chemex.space/`
- `https://chufa.wang/` -> map application, not ChemEx


## 2. Repository Layout

Key paths:

- `src/App.tsx` -> main frontend UI and client-side workflow logic
- `src/styles.css` -> product styling
- `src/main.tsx` -> frontend bootstrap and font imports
- `backend/app.py` -> Flask app, job execution, parsing, static serving
- `public/chemex-logo.png` -> main page logo
- `public/favicon.ico` -> favicon
- `docs/ROADMAP.md` -> product roadmap
- `docs/GUIDELINE.md` -> development rules
- `docs/HANDOFF.md` -> this handoff


## 3. Current Technical Stack

Frontend:

- React 19
- TypeScript
- Vite
- Mantine
- `@fontsource/rajdhani` for ChemEx wordmark branding

Backend:

- Flask
- pandas / numpy / scipy
- local thread-based job execution
- artifact files served from `backend_artifacts`

Scientific engines:

- `sesami==2.9` installed in `pydeps`
- vendored SESAMI legacy source for `1.0` workflow
- ZEO++ runtime compiled and used from the project-local runtime path


## 4. Current Feature State

### 4.1 SESAMI

Supported now:

- upload `.csv` and `.aif`
- choose `Argon` or `Nitrogen`
- choose `SESAMI 2.9` or `SESAMI 1.0`
- run BET asynchronously
- see real stage-driven progress
- view returned metrics
- inspect all generated plots
- enlarge plots
- inspect BET fitting region points

Not yet done:

- `BET+ESW` as first-class UI mode
- `betml`
- advanced fit parameter panel
- richer comparison across versions


### 4.2 ZEO++

Supported now:

- upload structure file
- run `PSD`
- real stage-driven progress
- PSD chart with labels and units
- hover coordinate display
- raw output copy
- raw output export to `txt` and `md`

Important limitation:

- current uploaded structure is passed to the runtime largely as-is
- a robust preprocessing / normalization pipeline is still missing
- current product has not yet exposed `-res`, `-chan`, `-sa`, `-vol`, `-volpo`


## 5. Runtime and Job Model

Current job handling:

- jobs are stored in memory in `JOBS`
- access synchronized by `JOBS_LOCK`
- workers run as background threads
- clients poll `/api/jobs/<job_id>`

ZEO++ execution (updated 2026-10-08):

- `CHEMEX_ZEOPP_TIMEOUT_SECONDS` controls the engine subprocess deadline; the default is `1800` seconds (30 minutes). Values must be finite and positive.
- The previous fixed 300-second deadline interrupted 100000-sample PSD runs. A TK-COF-6 reproduction took about 465 seconds on the production host; runtime varies with structure, parameters, and load.
- Each launched job writes `zeopp-run.json`, `zeopp-stdout.log`, and `zeopp-stderr.log` in its artifact directory, including on timeout, engine failure, or output-parsing failure. The JSON records the command, parameters, deadline, timing, exit code, status, and error.
- Engine output is streamed to disk. Timed-out engines are killed and reaped before logs are finalized.
- The ZEO++ UI displays the backend job error and a failed result state, without presenting failed work as 100% complete.
- These files survive service restarts; the in-memory job polling record still does not. Existing failed jobs are not automatically resumed.
- Changing only Nginx or Gunicorn timeouts does not change the engine deadline. Configure the environment on the ChemEx service and reload it between jobs when overriding the default.

Important caveat:

- jobs and job status are lost if the service restarts

This is acceptable for prototype use, but it is the biggest platform limitation to solve before heavier tools such as `RASPA3`.


## 6. Important API Endpoints

Current endpoints:

- `GET /api/health`
- `GET /api/zeopp/status`
- `GET /api/jobs/<job_id>`
- `POST /api/sesami/bet`
- `POST /api/zeopp/psd`
- `GET /api/artifacts/<job_id>/<filename>`

Static serving:

- `GET /`
- `GET /assets/<filename>`
- `GET /<filename>` for dist-root assets such as favicon and logo


## 7. Deployment Layout

Server:

- shared Ubuntu host
- server IP currently used by both public domains

ChemEx app layout on server:

- app path: `/srv/chemex/app`
- virtual env: `/srv/chemex/venv`
- service: `chemex.service`
- gunicorn bind: `127.0.0.1:4180`

Nginx files of interest:

- `/etc/nginx/sites-available/travel-planner-preview.conf`
- `/etc/nginx/sites-available/chemex-space.conf`
- `/etc/nginx/sites-available/default-deny.conf`

Current routing intent:

- `chufa.wang` stays with the map app
- `chemex.space` is the canonical ChemEx domain
- direct HTTP access by raw IP is denied

Certificates:

- `chemex.space` certificate issued by Let's Encrypt
- `www.chemex.space` included on same certificate


## 8. Local Development Runbook

Frontend build:

```powershell
cd D:\chemex
npm run build
```

Backend local run:

```powershell
cd D:\chemex
python -m backend.app
```

Local app URL:

- `http://127.0.0.1:8000/`


## 9. Production Update Runbook

Typical update sequence on the server:

```bash
cd /srv/chemex/app
git pull --ff-only origin main
npm install
npm run build
sudo systemctl restart chemex.service
sudo systemctl is-active chemex.service
```

If Nginx changes are involved:

```bash
sudo nginx -t
sudo systemctl reload nginx
```


## 10. Known Issues and Risks

### 10.1 Backend Monolith

`backend/app.py` currently contains too much responsibility.

This is manageable now, but future work should gradually split:

- routes
- scientific adapters
- job logic
- parsers
- artifact helpers


### 10.2 In-Memory Jobs

This is the biggest operational limitation.

Effects:

- restart loses state
- no durable task history
- weak basis for batch execution


### 10.3 ZEO++ Input Pipeline

The current ZEO++ workflow works for tested files, but does not yet provide a robust CIF normalization pipeline.

Recommended future layer:

- parse / validate with `pymatgen`
- normalize labels and structure metadata
- convert or stage formats explicitly before runtime execution


### 10.4 Shared Server Discipline

ChemEx shares infrastructure with another application.

Rule:

- never assume ChemEx owns the whole machine
- preserve `chufa.wang` behavior unless explicitly asked to migrate it


## 11. Recommended Next Tasks

Highest-value next tasks:

1. add ZEO++ `-res`
2. add ZEO++ `-chan`
3. add ZEO++ `-sa`
4. add ZEO++ `-vol`
5. add ZEO++ `-volpo`
6. add SESAMI `BET+ESW`
7. add persistent job storage
8. add `pymatgen` preprocessing for CIF


## 12. Notes for the Next Developer

- Treat `chemex.space` as the public ChemEx home.
- Keep root-domain and subpath compatibility unless there is a deliberate migration plan.
- Preserve raw scientific output and warning visibility.
- Do not remove the current export paths just because the UI becomes more polished.
- Update roadmap, guideline, and handoff whenever a new engine or domain rule is introduced.


## EPUB reader (2026-10-18)

Added the independent /epubreader/ tool with mouse-wheel page navigation, local books, search, bookmarks and notes. Source: public/epubreader/. See [EPUB Reader](EPUB_READER.md) for the release layout, rollback and verification steps. Production serves the reader from a separate Nginx alias to preserve existing server changes.

Follow-up compatibility repair: real-book QA now covers publisher font overrides, nested navigation/CSS, encoded chapter paths, Japanese vertical writing, large collections and fixed-layout picture books. The reader waits for resource readiness, preserves page position during typography changes and supports cancellation during loading. See the compatibility section of EPUB_READER.md and the original regression-fixture generator.

Reading preferences are now stored per book (IndexedDB v3) and ordinary body typography uses shared absolute metrics. Existing books receive independent snapshots of the last legacy global settings once; new imports use defaults. See EPUB_READER.md and run the preference regression tests before publishing changes to settings or typography.

## Pachong / film discovery (2026-10-20)

Independent `/pachong/` film search/details/player lives in `tools/pachong/`, served by `chemex-pachong.service` on loopback port 4198. Source data comes from iKanBot public pages and playback listings; movie bytes load directly in the browser. See [Pachong](PACHONG.md) for API boundaries, checks, versioned deployment and rollback. Preserve the existing ChemEx, EPUB and survival applications.

## Personal homepage and player keys (2026-10-20)

The root is now a personal portal (`tools/home/`), with COF under research `/research/`, film and EPUB under leisure, and survival under life. `deploy-home.py` preserves the live scientific frontend as a server-side snapshot and routes its relative APIs to the existing backend. See [Personal home](PERSONAL_HOME.md). The scientific product guidance applies within the research tool; domain-level identity is now personal. Existing book storage URLs remain unchanged.

The film player handles Space for play/pause and left/right arrows for 10-second seeks, avoiding text fields, focused controls, modifiers and unloaded/no-video views. `player-shortcuts.js` must ship before `app.js`. Run `node --test scripts/test-player-shortcuts.cjs` and verify real browser playback/seek, including native video focus and search input isolation.

## Private owner access and compact portal

Owner selected the existing Survival MX player identity for the entire ChemEx domain. `tools/auth/` and `deploy-auth.py` add a server-side gate with 30-day device sessions; the existing MX password is imported as a hash on the host, with no secret output. The authenticated Survival bootstrap restores MX without another login. All app/API/asset paths are protected; only auth endpoints remain reachable anonymously. See `OWNER_AUTH.md` before touching authentication or restoring Nginx backups. Homepage now removes the introductory hero and uses compact cards; do not re-add the large introduction.

Film canonical URL is now /miying/; legacy /pachong/ redirects. Internal service/source names remain pachong. deploy-pachong.py now replaces its managed Nginx block and retains the inherited owner auth gate. All app pages/APIs/assets require the existing MX session; login remains remembered across navigation and the URL change.



## Unified visual theme (2026-10-20)

Home, film, EPUB and owner-account pages align with the existing cool white / blue-gray COF and Survival visual language; COF/research and Survival receive no changes. Light and dark variants use the same tokens, typography, borders and controls. See [Shared theme](THEME.md) for scope, deployment and rollback.


Homepage entrances now use owner-provided transparent illustrations without cards; Survival uses the sleeping-on-pillow image. EPUB adds a per-book 米黄 option while the homepage remains blue-gray. COF and Survival app sources/styles stay untouched. See `PERSONAL_HOME.md` and `EPUB_READER.md`.

Homepage entrances now stay in one compact row with equal image boxes and fit common viewport heights. Survival gains an isolated transparent-image shortcut to the ChemEx homepage; app sources, API behavior and the authentication bridge remain unchanged.

The shared transparent return-home image is now 56px: on Survival it sits to the right of the desktop clock or, on mobile, the 生存计划 title; on Miying, COF and EPUB it sits in the top-left corner. It preserves EPUB back-to-library controls, hides superseded text home links, and uses isolated Nginx HTML script injection without rebuilding or replacing application sources. deploy-return-links.py keeps the previous home release and Nginx configuration for rollback.

EPUB reading settings now offer 原书排版 / 横排 for reflowable books. Horizontal mode overrides nested publisher vertical writing before layout, uses left-to-right progression, preserves the current CFI when recreating the renderer, and persists per book. Restore original mode to recover publisher layout; fixed-layout image books keep their original pages. Existing annotations and stored EPUB payloads remain unchanged. Verification includes a two-chapter Japanese vertical/RTL/ruby fixture, per-book persistence, page advance, restore, mobile scrolling and fixed-layout protection. Publish with deploy-reader-writing.py, which guards the reviewed live script hashes, versions only the two script URLs and retains the prior reader release.

Japanese-language reflowable books now default to horizontal layout, including existing automatic original-layout preferences. A writingExplicit flag preserves subsequent manual original/horizontal choices. Horizontal conversion clears publisher root dimensions/columns before engine layout and resets nested text containers that otherwise clip or hide content, while retaining media and ruby. Real wheel input now works over linked text and reading gutters; continuous mode scrolls the viewport and turns chapters at boundaries. Regression checks include constrained publisher CSS, desktop/mobile clipping, real forward/back wheel events, continuous chapter transitions and explicit-choice persistence. deploy-reader-reflow.py guards the previous script hashes, copies the current reader release, versions the two script URLs, and retains rollback without changing Nginx or other applications.

Pagination follow-up: horizontal conversion now clears publisher negative text indents and inline/physical side margins and padding, including TOC links and dialogue labels. These could place first characters outside the current column and leak next-column labels at the right edge. An original Japanese hanging-indent fixture reproduced the failure on WebKit before the fix; test-reader-pagination.cjs now checks WebKit and Chromium at desktop/mobile widths, four consecutive pages, font resizing and original/horizontal restoration. The versioned deploy-reader-pagination.py replaces only reader.js and its URL, retaining all other reader resources and the previous release.

Highlights and note-taking have been removed from the reader UI and selection lifecycle. Selecting text retains native selection/copy without the former bottom action popup. Previously stored annotations are no longer painted, and their data is retained without deletion. Bookmarks, search, chapter navigation and progress remain available; the combined panel is now bookmarks-only. deploy-reader-quiet-selection.py checks the live reader hash, patches only the affected HTML snippets and script version, and retains the old release. WebKit/Chromium checks cover text selection, absence of popup/dialog/highlight painting, existing bookmarks and wheel navigation.
