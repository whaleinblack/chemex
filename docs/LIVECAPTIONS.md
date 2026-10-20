# ChemEx LiveCaptions

ChemEx integrates a pinned Web/PWA build of Realtime Translator as a Japanese microphone-caption tool under `/livecaptions/`. At the time of this document update, the Web type check, production build and all 104 core tests have passed. Local Chrome QA with injected Japanese speech also confirmed the fresh-profile Japanese/ReazonSpeech selection, on-demand model download, automatic recording start and live partial text without a page error. Production deployment and post-deployment verification are still in progress.

## Source and product boundary

- Upstream: `https://github.com/baijunjie/realtime-translator`
- Pinned upstream commit: `fa2ab2de94145389448e729551a26dc866cf1282`
- Pinned Git submodule: `tools/livecaptions/upstream/`
- ChemEx customization: `tools/livecaptions/chemex.patch` (applied by the build helper)
- Build output: `tools/livecaptions/upstream/apps/web/dist/`

The ChemEx variant sets the Web base path to `/livecaptions/`, uses “ChemEx LiveCaptions” as the installed PWA name and “ChemEx · 日语实时字幕” as the document title. A browser profile without saved settings starts with Japanese recognition using `zipformer-ja-reazonspeech`; valid existing settings remain authoritative. Translation starts disabled.

The Web application accepts microphone audio only. Recognition runs in the browser, and recognition or local-translation models are downloaded on demand after user confirmation. The macOS and iOS applications and the shared cross-platform behavior retain their upstream logic.

## Reproducible build

The workspace pins `pnpm@10.33.0`. Initialize the pinned submodule and apply `tools/livecaptions/chemex.patch` with `scripts/build-livecaptions.sh` before rebuilding. From `tools/livecaptions/upstream/`, install only the Web package and its workspace dependencies without running dependency lifecycle scripts, then build with the production subpath:

```bash
corepack pnpm@10.33.0 install --frozen-lockfile --filter '@rt/web...' --ignore-scripts
corepack pnpm@10.33.0 --filter @rt/web type-check
BASE_PATH=/livecaptions/ corepack pnpm@10.33.0 --filter @rt/web build
```

`scripts/build-livecaptions.sh` runs the same install, type-check and build flow using the version pinned by the workspace. Package the contents of `apps/web/dist/`, rather than the `dist` directory itself, so `index.html` is at the archive root.

## Deployment layout and owner access

The LiveCaptions deployment is isolated from the shared ChemEx checkout and services:

```text
/srv/chemex/livecaptions/releases/<full ChemEx commit>/
/srv/chemex/livecaptions/current -> releases/<full ChemEx commit>
```

The ChemEx TLS server block serves the selected release through this Nginx alias once deployment completes:

```nginx
location = /livecaptions {
    return 308 /livecaptions/$is_args$args;
}

location ^~ /livecaptions/ {
    alias /srv/chemex/livecaptions/current/;
    index index.html;
}
```

This location inherits the existing domain-level owner gate. The deployment helper refuses to proceed if the expected `auth_request /_chemex_auth;` gate is absent; it does not create another account or password.

Build a tar archive from `apps/web/dist/`, transfer it together with the helper, and run on the ChemEx host:

```bash
sudo python3 scripts/deploy-livecaptions.py <full-ChemEx-commit> <livecaptions.tar>
```

The commit argument identifies the complete ChemEx delivery, so it must be the full 40-character ChemEx commit rather than the pinned upstream commit. The helper rejects unsafe or incomplete archives and validates the PWA scope and start URL before switching the release.

Release directories, backups and rollback follow the EPUB reader deployment model. The helper writes Nginx backups and release metadata under `/srv/chemex/livecaptions/backups/`, switches `current` atomically, runs `nginx -t`, and reloads Nginx. A failed validation or reload restores the previous symlink and Nginx configuration automatically. For a later manual rollback, repoint `current` to the prior release recorded in the matching release metadata, restore its Nginx backup if needed, validate, and reload. For a first-install rollback, restore the saved Nginx configuration and reload it after validation.

## Portal entry and verification

`tools/home/index.html` contains the “日语实时字幕 / LiveCaptions” entry in the Life section and links to `/livecaptions/`. Publishing that entry uses the existing home deployment flow.

Before declaring the integration deployed, verify the unauthenticated owner-gate behavior, the `/livecaptions` redirect, the authenticated page title and PWA manifest scope, microphone transcription with the Japanese default model, retained settings in an existing browser profile, and model download on demand. Also smoke-test the homepage and existing ChemEx tool routes to confirm that the isolated Nginx location did not alter them.
