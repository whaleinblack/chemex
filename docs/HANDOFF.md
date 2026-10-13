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


## COF Experiment Design delivery (2026-10-13)

New files: `backend/services_research.py`, `backend/routes_research.py`, `src/features/research/ResearchWorkbench.tsx`, and `backend/test_research.py`.

Endpoints:
- GET /api/research/status
- POST /api/research/identify: multipart `monomers` JSON (2–4 text objects); optional image0–image3 PNG/JPEG/WebP, ≤5 MB/image and ≤12 megapixels. Images require enhanced mode.
- POST /api/research/search: JSON with confirmed:true, 2–4 monomers (name, aliases, cas, backbone), notes and locale.
- Existing GET /api/jobs/<id> polls both research phases. Completed reports persist as identity.json / research.json in the job artifact folder. Job records remain in memory.

Default mode queries public PubChem identity records and Crossref metadata. All papers are explicitly unverified candidates; conditions are null. Monomer identity confirmation, aliases and backbone edits expand retrieval.

Enhanced mode requires OPENAI_API_KEY in the ChemEx service environment (never commit it). CHEMEX_RESEARCH_MODEL is optional; default gpt-5.4, which must support vision, Responses structured outputs and web_search. The service uses required web search, actual source receipts, and store:false. Follow https://developers.openai.com/api/docs/guides/tools-web-search and https://developers.openai.com/api/docs/guides/images-vision. API usage has provider charges. ChatGPT subscription is not server API access.

Python dependency: Pillow is used to validate uploads (normally installed with existing matplotlib); verify it exists in /srv/chemex/venv before enabling image inputs. No new JavaScript dependencies.

Research requests are capped at two simultaneous workers and 30 starts/hour per process. Gunicorn multi-process deployments multiply those limits; use a shared limiter/authentication before exposing paid research broadly. Existing job restarts still lose polling records. No inputs are sent to AI in public mode. In AI mode, user-confirmed names/context and uploaded images are sent to OpenAI; public queries go to PubChem/Crossref.

Validation: Python unittest backend.test_research + backend.test_zeopp_execution; TypeScript build and Vite production build. No paid AI end-to-end call has been run without credentials. Production deployment was completed on 2026-10-13 using the supplied codex account key.

Production update: preserve server working-tree edits; back up the app and dist; pull the approved commit; npm ci; npm run build; verify Pillow in venv; restart chemex.service only when existing calculations are idle. Validate /api/health, /api/research/status and a name/CAS search. Do not change shared-host Nginx or other apps. Roll back the prior app/dist and restart ChemEx if health verification fails.


### Production delivery receipt: 2026-10-13

- Deployed source commit: 6a546bb7823c564ac453728039cbda148a103bf9 (PR #2).
- Applied only the runtime/frontend delta onto the existing production working tree; did not reset or discard its uncommitted SESAMI improvements, engine code or styles. Their hashes were checked before and after deployment. The live checkout retains its older Git HEAD and server-local changes.
- Complete private backup: /srv/chemex/backups/cof-design-before-20261013-2028.tar.gz; gzip integrity verified. Previous dist also retained at /srv/chemex/staging/dist-before-cof-design-20261013.
- Patch SHA-256: 9bbf374b8e497c5befb16f52b29b2609fce8fba260442d2e6d8e49229660b3f3.
- Production validation: 11 research tests passed using the production venv, TypeScript/Vite build passed with the preserved live sources, chemex.service active, SESAMI and ZEO++ health ready.
- New public page title and research tab verified at https://chemex.space/. Current research mode is public-metadata; enhanced/vision are false. AI credentials and paid end-to-end verification remain outstanding.
- Rollback: reverse the runtime patch only if the source has not changed subsequently; restore previous dist from staging; restart chemex.service. For later/conflicting changes, use the complete backup carefully without overwriting newer user work.


2026-10-13 update: At the owner’s request, the COF Experiment Design tab, research routes and module code were removed. The COF多功能工具箱 name, removal of the decorative version label, and existing SESAMI/ZEO++ workflows are retained. Earlier research sections above are historical delivery records.
