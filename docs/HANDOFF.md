# ChemEx Handoff

## 1. Project Summary

ChemEx is a bilingual web application for porous-material and COF computation.

Repository capability audit: `2026-10-07`, main `85ad2ff82f1079f08e89d5cf2d0222da10059e30`. This describes repository code, not a fresh production verification. GitHub returned no PRs, workflow runs, check runs, or commit statuses for this baseline.

Implemented backend APIs and exposed frontend workflows:

- SESAMI BET (2.9 / 1.0), BET+ESW (2.9), BET-ML (2.9), Compare, and Advanced fit controls
- ZEO++ PSD, RES / RESEX, CHAN, SA, VOL, VOLPO

See [verification evidence](VERIFICATION.md) for test coverage and runtime limitations.

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

- `src/App.tsx` -> top-level tool selection
- `src/features/sesami/SesamiWorkbench.tsx` -> SESAMI modes, parameters, results
- `src/features/zeopp/ZeoppWorkbench.tsx` -> ZEO++ modes, parameters, results
- `src/lib/api.ts` -> relative API endpoints and multipart requests
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

Backend implemented and frontend exposed:

- BET+ESW and BET-ML as first-class tabs (fixed to 2.9)
- Compare: modern BET / BET+ESW, plus legacy BET and ML when their dependencies are available
- Advanced: BET / BET+ESW with R² cutoffs, DPI, font size, legend controls
- area / fit cards, comparison warnings, plots and selected-region points

Verification: five real Argon example workflows pass benchmark assertions. BET-ML retains an upstream scikit-learn model-version warning. Compare optional engine exceptions can still fail the job; cross-environment stability is not established.


### 4.2 ZEO++

Supported now:

- upload structure file
- choose `PSD`, `RES / RESEX`, `CHAN`, `SA`, `VOL`, or `VOLPO`
- control standard/extended RES, CHAN probe radius, or sampling radii and sample count
- view numeric metrics with units, channel summary, and raw output
- real stage-driven progress
- PSD chart with labels and units
- hover coordinate display
- raw output copy
- raw output export to `txt` and `md`

Important limitation:

- current uploaded structure is passed to the runtime largely as-is
- a robust preprocessing / normalization pipeline is still missing
- all six modes are exposed through `ZeoppWorkbench` and `src/lib/api.ts`
- command/API contracts and vendored reference parsers are tested; VOLPO uses a synthetic parser fixture
- no compiled `network` binary is present in the checkout: real ZEO++ execution remains unverified on this machine


## 5. Runtime and Job Model

Current job handling:

- jobs are stored in memory in `JOBS`
- access synchronized by `JOBS_LOCK`
- workers run as background threads
- clients poll `/api/jobs/<job_id>`

Important caveat:

- jobs and job status are lost if the service restarts

This is acceptable for prototype use, but it is the biggest platform limitation to solve before heavier tools such as `RASPA3`.


## 6. Important API Endpoints

Current endpoints:

- `GET /api/health`
- `GET /api/zeopp/status`
- `GET /api/jobs/<job_id>`
- `POST /api/sesami/bet`, `/api/sesami/bet-esw`, `/api/sesami/betml`, `/api/sesami/compare`
- `POST /api/zeopp/psd`, `/api/zeopp/res`, `/api/zeopp/chan`, `/api/zeopp/sa`, `/api/zeopp/vol`, `/api/zeopp/volpo`
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

1. run all ZEO++ modes against a compiled runtime and representative inputs
2. validate SESAMI supported dependency versions, model compatibility and Compare optional failures
3. add `pymatgen` preprocessing for CIF
4. plan persistent job storage as a separate platform change; `JOBS` remains in memory in this PR


## 12. Notes for the Next Developer

- Treat `chemex.space` as the public ChemEx home.
- Keep root-domain and subpath compatibility unless there is a deliberate migration plan.
- Preserve raw scientific output and warning visibility.
- Do not remove the current export paths just because the UI becomes more polished.
- Update roadmap, guideline, and handoff whenever a new engine or domain rule is introduced.
