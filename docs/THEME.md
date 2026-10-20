# Shared ChemEx theme

`tools/theme/site-theme.css` is the shared presentation layer for the home, film, EPUB reader and owner-account pages, matching the existing COF/Survival blue-gray visual language. COF/research and Survival are explicitly excluded from injection and receive no code, asset or style changes. The light palette is cool gray (`#f4f6fa`), white cards, slate text and blue (`#3567d6`); dark modes use navy/slate surfaces and a lighter blue. Root typography, borders, focus rings, card radii and controls are consistent. The homepage uses four transparent illustrated links without entry frames and retains its transparent favicon.

The theme is applied after application styles using a versioned stylesheet link. Nginx adds `data-chemex-page` to the HTML body to scope page-specific adjustments. The existing Survival bootstrap, styles and light/dark choice are untouched. Research results/status colors, video/cover content, per-book typography, book positions, app storage and API contracts are unchanged. EPUB paper modes offer cool white, light gray, optional cream (米黄), and dark. Existing `sepia` preferences remain light gray; the new `cream` identifier is saved independently for each book. The homepage stays blue-gray.

## Deployment

Commit/push first. Upload `tools/theme/site-theme.css` and `scripts/deploy-theme.py`, then run `sudo python3 deploy-theme.py <full-commit> <css-file>` on the ChemEx host. It installs `/srv/chemex/theme/releases/<commit>/site-theme.css`, switches `current`, backs up Nginx, updates only the managed shared-theme resource block and adds scoped filters inside the home, film, EPUB and auth locations, validates and reloads Nginx. Other applications' source trees and services are preserved.

The exact `/site-theme.css` resource is public presentation content; app routes and other assets keep their owner gate. Login/account CSP permits same-origin CSS. Publish the small authentication CSP change through `deploy-auth.py`. Add the optional cream-paper delta to the current live reader with `sudo python3 deploy-reader-cream.py <full-commit>`; the helper copies the current release and preserves every other byte, including existing server repairs; book data stays in the browser at the same URL. The homepage meta-color change uses `deploy-home.py` and preserves the live scientific frontend snapshot.

Subsequent theme publishes use a new stylesheet version in the deployment helper to invalidate browser caches. Do not change the research/Survival locations or duplicate the injected stylesheet. Run this helper last after any home, film, EPUB or auth publication, because those helpers can replace their own location blocks.

Rollback: restore the matching Nginx backup under `/srv/chemex/theme/backups/<timestamp>/` and the previous `current` target (if present), validate and reload Nginx. On first install, removing the managed filters and restoring the previous app releases returns the prior styles. Retain the owner access gate throughout.

## Validation

Run the route-filter tests and auth regression suite. Verify desktop and mobile home, login, film/library and reader controls; check dark reader mode and EPUB import/read navigation. Confirm anonymous theme/icon requests return 200 while app routes, APIs and private styles/fonts require login. Verify service health and that independent research and Survival source files keep their original hashes.
