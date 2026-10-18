# EPUB Reader

The independent reader lives at `https://chemex.space/epubreader/`. It recreates the reference's bookshelf and quiet reading layout under ChemEx branding. It has no account, cloud synchronization, converter, or dependency on the reference website.

## Source and local use

- `public/epubreader/`: buildless HTML, CSS, JavaScript and vendored EPUB.js 0.3.93 / JSZip 3.10.1, with their licenses.
- `npm run build` copies the reader into `dist/epubreader/`.
- Vite development: `/epubreader/`; the Flask server also redirects `/epubreader` to the trailing-slash route and serves the same files.
- `python -m unittest backend.test_epubreader` verifies route isolation, trailing-slash handling, asset serving and missing files.

## Behavior

- Local `.epub` import and drag/drop, 150 MiB input limit, duplicate detection, and a generated three-chapter example EPUB.
- IndexedDB `chemex-epubreader` v3 stores file payloads separately from small progress/notes records. Each book's metadata owns its `preferences` (font, line ratio, theme, flow and wheel behavior). The legacy localStorage key `chemex-reader-settings` supplies the bookshelf appearance and a one-time migration snapshot for books without preferences; later changes never propagate between books. New imports start at 21 px / 1.9 regardless of the previously open book. Books and notes do not sync across browsers or devices; clearing browser storage removes them.
- Paginated and chapter-scroll modes, table of contents, whole-book text search (first 100 matches), reading progress, bookmarks, highlights, notes, Markdown note export, font/line spacing, three paper themes, and focus mode.
- In page mode, downward wheel events go forward and upward wheel events go backward. Events inside EPUB iframes are handled too. A 45-pixel accumulation threshold and 450-ms minimum interval reduce trackpad over-triggering. Ctrl/Meta/Alt/Shift wheel gestures, tools panels and chapter-scroll mode retain native behavior.
- Keyboard arrows / Page Up / Page Down / Space and horizontal touch swipes also navigate.
- DRM is unsupported. EPUB scripted content is disabled; active elements, event handlers, remote resource references and script URLs are removed before rendering. A page CSP blocks external network resources. Fixed-layout books preserve their viewport and page geometry; font/line-spacing controls are disabled for those pages.

## Compatibility and typography fixes

- Wait for `book.opened` (resource preparation), not only `book.ready` (package parsing). Metadata import no longer opens and immediately destroys a second renderer while resource promises are still pending.
- Normalize navigation and internal link paths against their own document location. Resolve archived chapter media types from the manifest, including percent-encoded and nonstandard filename extensions. Fall back to an empty navigation model when optional navigation is missing.
- Resolve chapter images and styles from the archive before rendering. Expand nested CSS imports and rebase their asset URLs, retaining Japanese vertical writing and embedded illustrations. Missing optional resources keep their URL-array positions instead of shifting later assets.
- Ordinary body text uses absolute pixel sizes and a shared serif font stack, independent of publisher fonts, nested relative sizes and inline/class overrides. At the minimum setting, ordinary text is 14 px with an 18.2 px line height and a 10.5 px paragraph gap. Headings, small text, superscripts and ruby annotations use defined semantic scales; picture books retain their page geometry. Reapplying a theme replaces a single stylesheet instead of appending unbounded CSS rules.
- Reflow preserves a captured reading position and ignores transient location events. Bookmarks are recognized anywhere within the current visible page after a font change.
- Cache generated character locations. Collections over 100 spine items and fixed-layout books use immediate chapter-based navigation rather than loading every chapter before enabling progress. Estimated progress has a tooltip and does not report completion until the actual last page.
- Loading can be cancelled with the back button; stale selection state is cleared when changing books. Keyboard activation of buttons is no longer intercepted as a page turn.

Regression fixtures can be generated with `python scripts/make-epubreader-fixtures.py <output-directory>`. They contain original test text/artwork and cover nested navigation/CSS, inline fixed font sizes, encoded chapter names and fixed-layout images. Real-book browser QA also covers Chinese/English prose, Japanese vertical text with illustrations, a collection with over 1,000 chapters, and an illustrated fixed-layout EPUB. User books are not included in the repository or deployment.

Run `node --test scripts/test-reader-preferences.cjs` for preference isolation, serialized restoration, legacy snapshots, body metrics and bounds validation. Browser QA additionally switches between books with different settings, refreshes and reopens them, checks identical minimum body metrics in two real books, and confirms a new import uses defaults rather than the last book's values. Database v3 closes old-version connections before metadata migration, preventing a stale v2 tab from writing older metadata over per-book preferences.

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
