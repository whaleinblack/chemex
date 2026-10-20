# ChemEx personal homepage

The root `https://chemex.space/` is the owner's personal portal. `tools/home/` contains its buildless HTML/CSS, local Rajdhani font and license, and original SVG/CSS artwork. The page makes no requests to external APIs and has no analytics dependency. Its account gate is implemented by the separate owner-auth service.

The homepage uses four unframed transparent illustration links with short captions. Both desktop and mobile keep all four entrances in one row with equal image boxes. Image heights are explicit so intrinsic PNG dimensions cannot create excess vertical space. The mapping is: character behind black jail bars → COF, glasses/cup/laptop → Miying, sleeping character on pillow → Survival, reading character/book/lamp → EPUB. No card background or entry borders are used. The header's account link opens `/auth/account` for logout/device revocation. The whole domain is now protected using the existing Survival MX credentials, with a remembered 30-day device session; see `OWNER_AUTH.md`. No new account/password is created.

## Navigation

| Section | Tool | URL |
| --- | --- | --- |
| 科研 / Research | Existing COF workbench | `/research/` |
| 娱乐 / Leisure | Film discovery/player | `/miying/` |
| 娱乐 / Leisure | Local EPUB reader | `/epubreader/` |
| 生活 / Everyday | Existing survival app | `/survival/` |

The root is a navigation page; each existing application keeps its own state, service and API behavior. In particular, `/epubreader/` stays on its original URL so local browser books/preferences remain accessible. Film and survival URLs also stay unchanged.

## Deploy without replacing live scientific changes

Commit and push first. Tar exactly `index.html`, `style.css`, `favicon.svg`, `favicon.png`, `favicon.ico`, `apple-touch-icon.png`, `rajdhani-600.woff2`, `FONT-LICENSE`, `return-home.png`, `return-home.js`, and the four `entrances/*.png` files from `tools/home/`. Upload this archive with `scripts/deploy-home.py`, and run `sudo python3 deploy-home.py <full-commit> <tar>`.

The helper installs `/srv/chemex/home/releases/<commit>`, with home assets under `assets/`, and copies the **current server's** `/srv/chemex/app/dist` into that release's `research/` directory. This snapshot stays on the server; do not commit independent live modifications or private runtime fonts. The original server checkout, backend, calculation data and app services are not overwritten/restarted. On later research frontend changes, refresh the research snapshot through a new home release after verifying the changed workbench.

Nginx gains only a marked block: exact `/` serves the new home; `/home-assets/` serves its assets; `/research` redirects to `/research/`; `/research/` serves the captured frontend; `/research/api/` maps to the existing `/api/` backend routes on port 4180. The existing root `/api/`, `/assets/`, `/miying/`, `/epubreader/`, `/survival/` and unrelated host routes remain intact. Relative frontend module assets and all relative API endpoints resolve within the research prefix. No Vite rebuild of the old scientific app is part of this portal-only deployment.

The helper backs up Nginx, atomically switches `current`, validates and reloads Nginx, and restores config/symlink on failure. Manual rollback for an established home: restore the previous `current` and saved Nginx config, validate and reload. For the first home deployment, restore the original config. Backups are under `/srv/chemex/home/backups/<UTC timestamp>/`.

Verify root title and all four tool links, desktop/mobile layout, the research JS/CSS/font assets, `/research/api/health`, `/research/api/zeopp/status`, `/api/health`, all existing tool routes and service health. Compare the research HTML hash to the original live app to verify the snapshot is byte-identical. Open the scientific UI and confirm the real API health and both workbench tabs, without starting unsolicited scientific jobs.

## Website icon

The owner-provided avatar is the site icon. `tools/home/favicon.png` is the reusable 512px transparent asset; SVG (embedded PNG), ICO and Apple touch variants retain alpha. The white face stays filled and only the exterior background is transparent. The homepage uses versioned icon URLs to avoid the old C mark being reused from browser cache. The shared root icon routes and an exact icon-only allowlist resolve to current home assets without authentication so Safari can fetch them independently; all other assets and pages retain the owner gate. Login/account pages declare the same icons. See `OWNER_AUTH.md` for the complete public icon allowlist.

The master was prepared with the built-in imagegen tool using: “Remove only the exterior white background to actual transparent alpha; preserve the white face and ear interiors, eye highlights, expression, black contours and pink cheeks; center the complete head on a square canvas.” Native macOS sips exports the delivery sizes without flattening alpha.

The entrance images were extracted from owner-provided illustrations using built-in imagegen. Only exterior backgrounds are transparent; white character bodies and props remain filled. See `tools/home/entrances/ARTWORK.json` for the per-image prompts and mapping.

COF uses the owner-provided jail-bar illustration with transparent exterior and gaps. EPUB retains its original purple outlines. The asset-only deploy-home-artwork.py helper copies the live home release, replaces only the COF PNG and versions its URL, verifies other resources, then atomically switches current. The previous release remains available for rollback; no service or Nginx changes are needed.

The Survival page includes a 44px transparent character link in the top-left corner back to `/`, named 返回 ChemEx 主页 for accessibility. Its independent script is injected alongside the existing authenticated session bridge; it does not read or change app/account state. deploy-home-navigation.py installs layout and shortcut assets in a new home release and backs up Nginx before adding only that script to the Survival UI filter. Survival app files and APIs stay unchanged.

The homepage omits the research/leisure/life navigation text from the top-right and bottom-right corners, per owner request.
