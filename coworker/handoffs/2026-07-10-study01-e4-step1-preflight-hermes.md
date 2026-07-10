Role: executor
Plan: `coworker/plans/2026-07-10-study01-e4-staged-execution.md`
Status/Handoff: `Study/01-study-MDM最小偏移量优化研究/E4-validation-suite-状态交接.md`
Report: `coworker/reports/2026-07-10-study01-e4-step1-preflight-hermes.md`

Follow the coworker protocol. This is Step 1 only: preflight / inventory / contract freeze.

Context:

- The previous one-shot formal batch handoff is superseded for execution because the Hermes/GLM API is unstable.
- Current worktree may already contain partial untracked files:
  - `Study/01-study-MDM最小偏移量优化研究/code/run_E4_formal_validation.py`
  - `Study/01-study-MDM最小偏移量优化研究/code/run_E4_mc_generation.py`
  - `Study/artifacts/`
- Do not assume these files are valid or invalid. Inventory them.

Tasks:

1. Read `README.md`, the Study README, the active Status/Handoff file, this plan, and `coworker/reviews/2026-07-10-study01-e4-validation-suite-codex.md`.
2. Run `git status --short`.
3. Inspect the partial untracked files and summarize:
   - paths;
   - purpose inferred from code or filenames;
   - whether they write to the correct Study/01 artifact directory;
   - whether they risk touching sealed artifacts or Ch1-Ch6;
   - whether they can be reused in later steps.
4. Inspect `Study/artifacts/` if present and report whether it is misplaced output.
5. Do not run formal E4, do not run heavy scripts, and do not delete or move partial files.
6. Update `E4-validation-suite-状态交接.md` to staged mode:
   - current stage should indicate Step 1 preflight is complete or blocked;
   - next step should be Step 2 MC generation only, if safe;
   - preserve the resume loop.
7. Write `coworker/reports/2026-07-10-study01-e4-step1-preflight-hermes.md`.

Report must include:

- changed files;
- exact commands run;
- inventory of partial files/artifacts;
- reuse/repair/delete recommendations, but do not perform destructive cleanup;
- whether Step 2 can proceed;
- `APPROVE`, `REVISE`, or `BLOCK` recommendation for Step 2.

Stop after writing the report and updating the status handoff. Do not self-authorize Step 2 execution.
