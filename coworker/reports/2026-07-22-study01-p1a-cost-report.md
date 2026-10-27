# Study01 P1a execution report: E4 cost report subset merge

> Date: 2026-07-22
> Branch: `study01xu`
> Scope: P1a only; executor did not commit or run a formal E4 experiment.
> Review status: first pass received `REVISE`; the empty-file and track-ownership
> findings are addressed in this revision.

## Outcome

Fixed the shared `cost_report.csv` writer in
`Study/01-study-MDM最小偏移量优化研究/code/run_E4_formal_validation.py`.
An E4 subset run now replaces rows owned by its requested track(s), preserves
rows for every other track, and does not accumulate duplicate rows when the
same subset is run again.

The writer validates ownership before reading or modifying the shared file:
every non-empty new row must name a non-blank track, and normalized new tracks
must be a subset of the requested tracks. Invalid input raises `ValueError`
without changing the existing report. A zero-row report is written with a
`track` header, and a pre-existing truly empty CSV can be recovered.

The full-run behavior remains consistent with a complete rewrite because a
full run requests all four tracks and therefore replaces all prior track rows.

## Changes

- Added `write_merged_cost_report(cost_path, new_rows, requested_tracks)`.
- The helper reads an existing report, filters old rows belonging to the
  requested tracks case-insensitively, appends the current rows, and writes the
  merged table.
- Added fail-closed validation preventing missing, blank, null, or unrequested
  tracks from reaching the shared report.
- Added a stable empty-report schema (`track` header) and compatibility with
  a pre-existing zero-byte CSV (`pandas.errors.EmptyDataError`).
- Routed the existing cost-report output block through the helper.
- Added `python/tests/test_study01_e4_cost_report.py` with independent regression
  coverage for boundary/off-grid subset updates, idempotence, preservation of
  other tracks, first empty write and recovery, a pre-existing empty CSV,
  rejected track ownership violations, and simultaneous multi-track updates.

## Verification

Commands run from `C:\Web\Weibull`:

```powershell
python -m pytest python/tests/test_study01_e4_cost_report.py -q
python -m py_compile `
  'Study/01-study-MDM最小偏移量优化研究/code/run_E4_formal_validation.py' `
  'python/tests/test_study01_e4_cost_report.py'
git diff --check
```

Results:

- New regression suite: `10 passed in 1.34s`.
- Python compilation: passed.
- Diff whitespace check: passed (Git emitted only the repository's existing
  CRLF/LF normalization warning for the E4 script).

## Checks attempted but not counted as passing

```powershell
python -m pytest python/tests/test_study01_e4_failclosed.py -q
```

Result: `15 failed, 2 passed`. All 15 failures are import-path setup failures
from the pre-existing hard-coded `PROJECT_ROOT = r"D:\weibull"`; this machine
has no `D:\weibull`. The failures occur before exercising the E4 functions and
are unrelated to this diff. The path defect was not changed because P1a is
strictly limited to cost-report merging.

## Deliberately not run

- No boundary/off-grid formal experiment rerun; P1a changes report persistence,
  and the regression tests exercise it with isolated temporary CSV files.
- No repository-wide test suite; the bounded test and compile checks cover this
  isolated writer change.

## Scope deviations

None. The task did not modify `R_MAIN`, 500-repeat handling, feature-table
construction, E4d training/evaluation contracts, formal artifacts, or Study01
status claims. No Git commit was created by the executor.
