# ChemEx personal homepage

The root `https://chemex.space/` is the owner's personal portal. `tools/home/` contains its buildless HTML/CSS, local Rajdhani font and license, and original SVG/CSS artwork. The page makes no requests to external APIs and has no analytics dependency. Its account gate is implemented by the separate owner-auth service.

The compact revision removes the introductory hero, descriptive section prose and large artwork. All four tool entries fit in a normal desktop viewport; mobile uses short stacked cards. The header's account link opens `/auth/account` for logout/device revocation. The whole domain is now protected using the existing Survival MX credentials, with a remembered 30-day device session; see `OWNER_AUTH.md`. No new account/password is created.

## Navigation

| Section | Tool | URL |
| --- | --- | --- |
| 科研 / Research | Existing COF workbench | `/research/` |
| 娱乐 / Leisure | Film discovery/player | `/miying/` |
| 娱乐 / Leisure | Local EPUB reader | `/epubreader/` |
| 生活 / Everyday | Existing survival app | `/survival/` |

The root is a navigation page; each existing application keeps its own state, service and API behavior. In particular, `/epubreader/` stays on its original URL so local browser books/preferences remain accessible. Film and survival URLs also stay unchanged.

## Deploy without replacing live scientific changes

Commit and push first. Tar exactly `index.html`, `style.css`, `favicon.svg`, `favicon.png`, `favicon.ico`, `apple-touch-icon.png`, `rajdhani-600.woff2` and `FONT-LICENSE` from `tools/home/`. Upload this archive with `scripts/deploy-home.py`, and run `sudo python3 deploy-home.py <full-commit> <tar>`.

The helper installs `/srv/chemex/home/releases/<commit>`, with home assets under `assets/`, and copies the **current server's** `/srv/chemex/app/dist` into that release's `research/` directory. This snapshot stays on the server; do not commit independent live modifications or private runtime fonts. The original server checkout, backend, calculation data and app services are not overwritten/restarted. On later research frontend changes, refresh the research snapshot through a new home release after verifying the changed workbench.

Nginx gains only a marked block: exact `/` serves the new home; `/home-assets/` serves its assets; `/research` redirects to `/research/`; `/research/` serves the captured frontend; `/research/api/` maps to the existing `/api/` backend routes on port 4180. The existing root `/api/`, `/assets/`, `/miying/`, `/epubreader/`, `/survival/` and unrelated host routes remain intact. Relative frontend module assets and all relative API endpoints resolve within the research prefix. No Vite rebuild of the old scientific app is part of this portal-only deployment.

The helper backs up Nginx, atomically switches `current`, validates and reloads Nginx, and restores config/symlink on failure. Manual rollback for an established home: restore the previous `current` and saved Nginx config, validate and reload. For the first home deployment, restore the original config. Backups are under `/srv/chemex/home/backups/<UTC timestamp>/`.

Verify root title and all four tool links, desktop/mobile layout, the research JS/CSS/font assets, `/research/api/health`, `/research/api/zeopp/status`, `/api/health`, all existing tool routes and service health. Compare the research HTML hash to the original live app to verify the snapshot is byte-identical. Open the scientific UI and confirm the real API health and both workbench tabs, without starting unsolicited scientific jobs.

## Website icon

The owner-provided avatar is the site icon. `tools/home/favicon.png` is the reusable 512px transparent asset; SVG (embedded PNG), ICO and Apple touch variants retain alpha. The white face stays filled and only the exterior background is transparent. The homepage uses versioned icon URLs to avoid the old C mark being reused from browser cache. The shared root icon routes and an exact icon-only allowlist resolve to current home assets without authentication so Safari can fetch them independently; all other assets and pages retain the owner gate. Login/account pages declare the same icons. See `OWNER_AUTH.md` for the complete public icon allowlist.

The master was prepared with the built-in imagegen tool using: “Remove only the exterior white background to actual transparent alpha; preserve the white face and ear interiors, eye highlights, expression, black contours and pink cheeks; center the complete head on a square canvas.” Native macOS sips exports the delivery sizes without flattening alpha.
