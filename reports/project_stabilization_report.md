# CareGrid Sentinel — Project Stabilization Report

**Investigation date:** 2026-11-10
**Scope:** Freshness-test stabilization, safe Git inspection, and readiness for the next data/model phase. No models were implemented and no datasets or experiment artifacts were changed.

## Executive summary

The two backend failures were caused by assertions that treated a dated report as permanently recent. The freshness implementation correctly follows its documented report-date thresholds. The latest daily IDSP snapshot is dated 2026-11-01; on 2026-11-10 it is nine calendar days old and therefore `historical`, not `verified_recent`.

The production freshness logic was not changed. Tests now exercise all documented age boundaries and derive endpoint expectations from the report date and current UTC date.

## Freshness investigation

The relevant implementation is `src/caregrid/daily_surveillance.py::get_daily_source_status`. It calculates age from the **report date**, not the retrieval date:

| Status | Documented rule | Boundary check |
|---|---|---|
| `verified_recent` | 0–2 calendar days old | 2026-11-03 for a 2026-11-01 report |
| `official_delayed` | 3–7 calendar days old | 2026-11-04 through 2026-11-08 |
| `historical` | More than 7 calendar days old | 2026-11-09 onward |
| `source_unavailable` | Latest refresh attempt failed | Overrides age while retaining the last valid snapshot |

The checked snapshot metadata records:

- Report date: `2026-11-01`
- Official post publication time: `2026-11-02T05:15:09+00:00`
- Snapshot retrieval time: `2026-11-02T12:52:34+00:00`
- Evaluation date: `2026-11-10` UTC
- Age: 9 days; expected status: `historical`

Retrieval on November 2 does not make a November 1 report recent on November 10. The snapshot is explicitly not a live feed. The status sidecar's `last_attempt` metadata refers to a successful July 25 report attempt at `2026-11-02T13:02:21+00:00`; freshness is still based on the latest validated snapshot's report date. The last-attempt metadata should not be read as the timestamp of the November 1 snapshot.

### Resolution

The two original failing assertions expected `verified_recent` despite the now-nine-day-old report. That expectation contradicted both the documented freshness rule and application behavior. The tests now:

1. Cover ages 2, 3, 7, and 8 days using explicit `as_of` dates.
2. Derive API/methodology expectations from the snapshot's report date and current UTC date, avoiding a permanently hard-coded freshness label.
3. Retain the existing test that a failed refresh reports `source_unavailable` while preserving the previous snapshot.

No timestamp was rewritten and no freshness threshold was relaxed.

## Verification

| Check | Result |
|---|---|
| Targeted daily IDSP tests | 32 passed |
| Complete backend suite: `.venv\Scripts\python.exe -m pytest -q` | 73 passed; 1 warning |
| Complete frontend suite: `npm test -- --run` | 3 test files, 8 tests passed |
| Frontend type-check and production build: `npm run build` | Passed; Vite production bundle generated |

The one backend warning is a dependency deprecation warning: Starlette's `TestClient` currently uses `httpx`, and the installed Starlette version recommends `httpx2`. It did not fail tests. No dependencies were installed or changed.

## Git and safe baseline

Inspection was read-only:

- Current branch: `master`
- The branch has no commits; `git log -1` reports that there are no commits on `master`.
- No Git remote or upstream is configured.
- The normal working tree consists of untracked project files; nothing was staged or committed.
- `git show-ref` contains agent/checkpoint refs, but no ordinary branch history suitable as a project baseline.
- `.gitignore` covers `.venv`, bytecode, `dashboard/node_modules`, `dashboard/dist`, selected caches, and generated figures. It does not explicitly exclude `.env` files.
- No `.env` contents were read.

No untracked files were reset, cleaned, moved, or deleted. Nothing was pushed or published.

### Recommended baseline procedure

Before major development:

1. Inventory files and data intended for version control; preserve source PDFs, snapshots, and experiment artifacts without rewriting them.
2. Review for credentials and private data without displaying their values; add appropriate secret-file ignore patterns before staging.
3. Review the license/provenance and repository-size implications of committing raw source PDFs and daily snapshots.
4. Create a deliberate initial commit from a reviewed file list, then tag it as the pre-multi-model baseline.
5. Configure a remote only after confirming its exact URL and intended access. Do not push without explicit authorization.

## Files changed in this task

- `tests/test_daily_idsp.py` — corrected time-sensitive assertions and added deterministic freshness-boundary coverage.
- `reports/project_stabilization_report.md` — this report.
- `reports/historical_data_readiness_report.md` — data inventory and comparability assessment.
- `reports/multi_model_architecture_design.md` — proposed model framework; design only.
