# ChemEx owner access

The canonical `chemex.space` TLS vhost uses an Nginx `auth_request` gate for **all** app pages, static resources and APIs. Only the authentication endpoints are exempt at Nginx; the account, logout and Survival bridge endpoints also verify their own session. HTTP and www continue to canonical HTTPS; ACME certificate validation remains public. Shared hosts are unchanged.

## Identity and persistence

Owner authorization selects the existing Survival **MX player** account. During first install, `tools/auth/init_survival.py` extracts only that account from the current Survival bundle **on the server**, immediately derives a salted scrypt hash, and saves it to `/var/lib/chemex-auth/account.json` (0600, directory 0700, ubuntu owner). It never prints or transfers the credential, creates a replacement password, imports JY/admin accounts, or changes Survival's source/data. Later installs retain the managed account file. Future Survival credential changes require an explicit re-import/rotation and session revocation; they are not automatically synchronized.

The legacy Survival UI used client-side account checks. The new **security boundary is the server gate**, not localStorage. On an authenticated `/survival/` page only, Nginx injects `/auth/survival-session.js`, which sets existing `mxsg-role=player` and `mxsg-user=mx` before the Vue module runs. This avoids a second login. It carries no password, and the bridge returns 401 without a valid session. Other Survival state is preserved. Existing previously public bundles or passwords are not made retroactively secret; any suspected prior disclosure should be handled by an owner-authorized credential rotation.

Login issues a random 256-bit session token in `__Host-chemex_session` with Secure, HttpOnly, SameSite=Lax, Path=/, no Domain, and Max-Age=2592000 (30 days). Only token SHA256 hashes are saved in SQLite, with an absolute expiration and credential fingerprint. Sessions survive service/browser restarts, but expire at 30 days, become invalid after a credential change, and can be revoked from `/auth/account`. Clearing site data/private browsing or browser cookie policies can also remove the device login.

The login form uses a host-scoped HttpOnly CSRF nonce cookie plus same-origin checking. Logout is POST-only with a per-session CSRF token. Login attempts are limited to 8/IP/15 minutes and 40 total/15 minutes; limiter state persists in SQLite. Credentials and cookies are not logged. Redirect targets are restricted to local paths. Login/account HTML is escaped and served with a restrictive CSP and no-store. A failed auth backend denies access rather than falling back to public content.

## Operations

Auth service: `chemex-auth.service`, Gunicorn on **127.0.0.1:4197**, separate versioned source under `/srv/chemex/auth/releases/<commit>` and private StateDirectory `/var/lib/chemex-auth` with UMask 0077. Never commit state files, credentials, hashes, session cookies, or Survival's legacy account list. The repository's test account is an original throwaway fixture.

Commit/push first. Tar only `server.py` and `init_survival.py` from `tools/auth/`; upload it with `scripts/deploy-auth.py`, then invoke `sudo python3 deploy-auth.py <full-commit> <tar>`. The helper imports the selected account once, verifies the auth service, adds a marked guard and authenticated Survival bootstrap to the canonical TLS vhost, validates/reloads Nginx and retains config/service backups. Main scientific, Survival, EPUB and film services are not restarted. A failed install restores its prior config/service/symlink.

Run `python -m unittest discover -s tools/auth -p test_auth.py`. Tests cover valid/invalid login, secure persistent cookies, token hashing, CSRF/origin protection, attempt throttling, restart/expiration behavior, logout/current and all-device revocation, credential changes, local-only redirects and protected Survival bootstrap.

After deploy, confirm anonymous access to `/`, `/research/`, `/pachong/`, `/epubreader/`, `/survival/`, their assets and API endpoints is denied/redirected; internal auth endpoint returns 404 externally. Verify valid MX credentials over HTTPS without printing them, remembered cookies, authenticated routes, Survival bootstrap and logout. Only reuse local browser previews or owner-authorized sessions for visual QA; do not add a public bootstrap bypass.

Rollback: restore the previous auth source/service if available and retain a functioning gate. Restoring a pre-auth Nginx backup removes protection and must be intentional; do not do that merely to bypass a login problem after a successful delivery. SSH remains available for recovery.
