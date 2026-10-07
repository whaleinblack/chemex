# Capability audit and regression evidence

Audit date: 2026-10-07 (Asia/Tokyo). Baseline: main `85ad2ff82f1079f08e89d5cf2d0222da10059e30`.

GitHub's complete PR listing returned `[]`; the baseline had no Actions runs,
check runs or commit statuses. There is no remote CI evidence of scientific stability.
This audit checks repository code and local tests, not production deployment.

## Implementation and frontend exposure

`src/App.tsx` imports feature workbenches. The absence of mode strings there does
not indicate missing UI support. `src/lib/api.ts` maps every mode to a relative
endpoint, preserving root/subpath hosting.

| Modes | Backend | Frontend parameters and results | Evidence |
| --- | --- | --- | --- |
| SESAMI BET | 2.9 and legacy 1.0 | Gas/version, fit metrics, plots, region points | Real Argon sample benchmarks |
| BET+ESW | 2.9 | Dedicated tab, fit metrics, plots/region | Real sample benchmark; no ESW minimum can legitimately fail |
| BET-ML | 2.9 | Dedicated tab, predicted area in m²/g | Real sample benchmark; model-version warning remains |
| Compare | Modern results plus available legacy/ML engines | Dedicated tab and comparison cards with warnings | Four counterparts on sample; optional engine exceptions can fail whole job |
| Advanced | Existing BET/BET+ESW options | R² thresholds, DPI, font size, legend | Multipart forwarding regression |
| ZEO++ RES / RESEX | Command and parser | Standard/extended selector; sphere diameters in A | Command contract, RES reference, synthetic extended fixture |
| ZEO++ CHAN | Command and parser | Probe radius; dimensions/channel summary | Command/API contract and vendored reference |
| ZEO++ PSD / SA / VOL | Commands and parsers | Channel/probe radii, sample count; chart or metrics/units, raw export | Command/API contracts and vendored references |
| ZEO++ VOLPO | Command and parser | Sampling parameters; occupiable-volume metrics, raw export | Command/API contract and synthetic fixture only |

The PR corrects Compare's request version after switching from legacy BET,
shows polled worker failures in both workbenches, and keeps exported filenames
attached to the completed result's mode after switching tabs. Existing backend
implementations and the `JOBS` memory model are unchanged.

## Local results

- Frontend: 16 passing integration/request regressions, including all modes,
  parameter forwarding, result units, Compare version, polled failures and export identity.
- Backend: 34 passing tests, including all route dispatches/polling, command
  arguments, reference parsing, non-zero-exit warning/failure contracts and five
  real SESAMI workflows.
- TypeScript and Vite production build pass. In the restricted Windows sandbox,
  Vite's default bundled config loader cannot traverse parent directories;
  `--configLoader runner` works without changing application configuration.
- SESAMI real sample (`vendor/SESAMI_web/example_input/example_loading_data.csv`,
  Argon): BET 2430.910, BET+ESW 2346.735, BET-ML 2099.055 m²/g;
  legacy BET agrees with modern BET on this sample. Compare returns all four.
- Existing vendored SESAMI tests: 10 pass, 1 fails. The old SESAMI_2 runner uses
  integer Series indexing (`test_data.iloc[0][i+1]`) incompatible with pandas 3
  (`KeyError: 1`). This is not ChemEx's modern `SESAMI.predict.betml` path, which
  passes the real benchmark. No vendored scientific code was modified.
- Existing vendored ZEO++ tests: first test fails with missing `network` executable
  (fail-fast run). No compiled binary exists in this checkout. Full real-engine
  validation of all ZEO++ modes remains outstanding; mocked route/process tests
  and reference fixtures do not establish runtime stability.

Scientific warnings remain visible in test output: sample endpoint division/invalid
operations and an upstream Lasso model saved under scikit-learn 0.23.2 loaded
under 1.9.1. Passing one Argon example does not establish compatibility for all
gases, isotherms, input formats, operating systems or dependency combinations.

## Reproduction

Use an isolated Python environment and install `requirements-test.txt`.
These versions were validated on Python 3.14 / Windows, not as a production
dependency migration. Frontend versions are recorded in `package-lock.json`.

```sh
npm ci
npm test
npm run build
python -m pip install -r requirements-test.txt
python -m pytest tests/backend -q
python tests/run_vendor_sesami.py
```

In restricted Windows environments, use `npm test -- --configLoader runner`
and run `npx tsc -b` plus `npx vite build --configLoader runner` for the build.
Set `MPLCONFIGDIR` to a writable local cache directory if needed.

To run vendored ZEO++ tests, provide an actual compatible runtime and run from
`vendor/zeopp-lsmo/tests`:

```sh
ZEOPP_BINARY=/absolute/path/to/network python -m pytest test_zeopp.py -q
```

Follow-up gates: representative real-runtime benchmarks for all ZEO++ modes;
scientific dependency/model compatibility; Compare partial-failure handling;
malformed output/array parsing; input normalization. Job persistence remains a
separate platform task. This PR neither deploys production nor merges itself.
