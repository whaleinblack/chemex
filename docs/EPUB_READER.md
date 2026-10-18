# EPUB Reader

The independent reader lives at `https://chemex.space/epubreader/`. It recreates the reference's bookshelf and quiet reading layout under ChemEx branding. It has no account, cloud synchronization, converter, or dependency on the reference website.

## Source and local use

- `public/epubreader/`: buildless HTML, CSS, JavaScript and vendored EPUB.js 0.3.93 / JSZip 3.10.1, with their licenses.
- `npm run build` copies the reader into `dist/epubreader/`.
- Vite development: `/epubreader/`; the Flask server also redirects `/epubreader` to the trailing-slash route and serves the same files.
- `python -m unittest backend.test_epubreader` verifies route isolation, trailing-slash handling, asset serving and missing files.

## Behavior

- Local `.epub` import and drag/drop, 150 MiB input limit, duplicate detection, and a generated three-chapter example EPUB.
- IndexedDB `chemex-epubreader` v2 stores file payloads separately from small progress/notes records. Reading settings use `chemex-reader-settings` in localStorage. Books and notes do not sync across browsers or devices; clearing browser storage removes them.
- Paginated and chapter-scroll modes, table of contents, whole-book text search (first 100 matches), reading progress, bookmarks, highlights, notes, Markdown note export, font/line spacing, three paper themes, and focus mode.
- In page mode, downward wheel events go forward and upward wheel events go backward. Events inside EPUB iframes are handled too. A 45-pixel accumulation threshold and 450-ms minimum interval reduce trackpad over-triggering. Ctrl/Meta/Alt/Shift wheel gestures, tools panels and chapter-scroll mode retain native behavior.
- Keyboard arrows / Page Up / Page Down / Space and horizontal touch swipes also navigate.
- DRM is unsupported. EPUB scripted content is disabled; active elements, event handlers, remote resource references and script URLs are removed before rendering. A page CSP blocks external network resources. Reflowable books are the primary target; complex fixed-layout books may differ from publisher formatting.

## Production deployment

Do not replace the existing server checkout or its frontend bundle; it contains independent local changes. Reader-only deployments use versioned releases:

```text
/srv/chemex/epubreader/releases/<commit>/
/srv/chemex/epubreader/current -> releases/<commit>
```

Only the `chemex.space` TLS server block receives these locations:

```nginx
location = /epubreader {
    return 308 /epubreader/;
}
location ^~ /epubreader/ {
    alias /srv/chemex/epubreader/current/;
    index index.html;
}
```

Back up `/etc/nginx/sites-available/chemex-space.conf`, validate `nginx -t`, and reload Nginx. No scientific service restart is necessary. For rollback, repoint `current` to the previous release; for first installation, restore the backed-up Nginx config and reload after validation. Keep the shared map application and other ChemEx routes unchanged.

## Verification

Browser QA covers example import, wheel navigation in both directions, bookmarks, whole-book search and navigation to results, saved notes, return to shelf, refresh and reading-position restoration. Production smoke checks include `/`, `/api/health`, `/epubreader`, the reader HTML and all vendored assets. Live wheel navigation must be checked after publication.
