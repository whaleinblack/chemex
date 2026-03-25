# ChemEx Handoff

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
