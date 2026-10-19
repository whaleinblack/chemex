# Pachong / 觅影

URL: `https://chemex.space/pachong/`. Independent film search and in-page HLS player, using the reference site's public metadata and playback listings. This is an original adapter/UI implementation, not the reference site's server source.

## Features and source

`tools/pachong/` contains a buildless HTML/CSS/JS frontend and standard-library Python WSGI service. Run `python tools/pachong/server.py` and open `http://127.0.0.1:4198/pachong/` locally. No Python package installation is required for development. Production uses the server's existing Gunicorn runtime.

- Latest movie/TV home lists, keyword/cast search, movie/TV category filters, ranking list, upstream pagination and film details.
- Same-page native video controls plus HLS.js **1.7.3**, BSD-2-Clause license vendored alongside the fixed distribution. Prefer MediaSource HLS when supported, with native HLS fallback. No CDN dependency for player code.
- Multiple playback lines, episode selection, playback speeds, retry, next episode and automatic advancement within the current line.
- Latest 60 viewed films, line/episode selection and approximate position saved in browser localStorage. Errors/corrupt storage fall back gracefully. Records stay in that browser; no account sync.
- Upstream availability, format, geographic access and third-party CORS determine whether an individual line works. Display errors and allow line switching; never claim all returned lines have been validated. Video bytes stream directly from their sources; ChemEx does not download/store/rehost movies or proxy arbitrary media URLs. Source-embedded ads may still appear in video.

Only the fixed upstream HTTPS host is fetched by the server. Redirects stay on that host. Category, path, film id and query inputs are validated; HTML is reduced to metadata and rendering escapes strings. Source scripts, analytics and ad code are never executed/imported. Playback metadata is decoded using JSON, never `eval`. Responses have a 15-second upstream timeout, 3 MiB limit, 180-second/128-entry cache, serialized cache misses and 80 API requests/minute/IP (one worker). HTTPS media only. Do not expose an arbitrary URL fetch/proxy endpoint.

Poster thumbnails from `img1`–`img9.doubanio.com` use a separate constrained image cache because direct browser loading may fail. Only HTTPS, the default port and recognized poster paths are accepted; no redirects, query strings, credentials, SVG or arbitrary hosts. The cache holds up to 64 images (512 KiB limit each), expires after one hour and uses an 8-second request timeout. Other cover sources load directly and failures show a placeholder. This endpoint never serves movie files.

## Checks

`python -m unittest discover -s tools/pachong -p test_server.py`

`node --check tools/pachong/app.js`

Tests cover metadata/deduplication, unsafe URL rejection, safe episode parsing, route isolation, upstream errors and cache reuse. Real-source checks cover home, search, next-page search, movie details/lines, TV episodes and rankings. Browser QA must also play actual video and observe currentTime progressing, switch line, verify history restoration, and check the mobile layout. Never use merely returning a playlist URL as proof of playback.

## Deployment

Commit/push first. Create a tar of `tools/pachong/` containing only `server.py`, `index.html`, `style.css`, `app.js`, and `vendor/`. Upload it and `scripts/deploy-pachong.py`; invoke `sudo python3 deploy-pachong.py <full-commit> <tar>` on the host.

The helper installs `/srv/chemex/pachong/releases/<commit>` and atomically switches `current`, preserves the existing Nginx config, creates/updates only `chemex-pachong.service`, verifies loopback health, validates and reloads Nginx. The new service listens only on `127.0.0.1:4198` using `/srv/chemex/venv/bin/gunicorn`. `/pachong` redirects to `/pachong/`; the prefix proxies to this dedicated service. Shared ChemEx and EPUB sources/services are not replaced or restarted. Existing unmanaged path/service/port conflicts stop the deployment.

Failed deployment restores the previous symlink, service and Nginx config. Manual rollback: stop the Pachong service, repoint `current` to the previous release and restart it; for first install, also restore the saved Nginx config, validate/reload, disable the new service. Config/service backups are under `pachong/backups/<UTC timestamp>/`.

Verify `/pachong/api/health`, `/pachong/api/home`, `/`, `/api/health`, `/epubreader/`, `chemex-pachong.service`, `chemex.service` and Nginx after deployment; then test search-to-playback in the live browser.
