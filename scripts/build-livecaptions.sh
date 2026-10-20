#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
git submodule update --init tools/livecaptions/upstream
cd tools/livecaptions/upstream
if git apply --reverse --check ../chemex.patch 2>/dev/null; then
    : # Already configured for ChemEx.
else
    git apply --check ../chemex.patch
    git apply ../chemex.patch
fi
# Use the version pinned in packageManager; avoid native desktop installers.
[ "$(pnpm --version)" = "10.33.0" ] || { echo 'Use pnpm 10.33.0 (the pinned packageManager version).' >&2; exit 1; }
pnpm install --frozen-lockfile --filter '@rt/web...' --ignore-scripts
pnpm --filter @rt/web type-check
BASE_PATH=/livecaptions/ pnpm --filter @rt/web build
