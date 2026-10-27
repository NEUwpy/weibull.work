# Stage A Codex Re-review

VERDICT: APPROVE

## Scope Check

- Baseline: `8350f29`.
- Stage A implementation: `f8b6761`, `d7e3ac7`.
- Revision: `f95bb9c`.
- Executor report: `da8d8c7`.
- The revision changes only the method-status generator, validation library and tests; the report commit changes only the executor report.
- `Study/01` working-tree edits and `docs/history/260717.md` remain outside the reviewed commits.
- `src/data/method-status.generated.json` is unchanged by the revision.

## Resolution of Previous Findings

### Repository-relative paths

RESOLVED. `assertRepositoryPath()` now rejects absolute paths and candidates resolving outside the repository root. The same validation covers `classification_source` and evidence paths.

Fresh probes rejected both `..` and `../outside`.

### Catalog identity and status metadata

RESOLVED. `flattenCatalogLeaves()` rejects duplicate category and leaf IDs. The generator supplies catalog leaves to `validateStatusDocument()`, which rejects status `name` or `family` values that disagree with `src/data/methods.json`.

Fresh probes rejected duplicate leaf IDs, duplicate category IDs and name/family drift.

## Independent Verification

Run from the repository root on 2026-07-17:

```text
npm run test:method-status
18 tests, 18 passed, 0 failed

npm run check:method-status
method-status: cache is up to date (22 methods).

git diff --check 8350f29..da8d8c7
pass

git show --check f95bb9c da8d8c7
pass
```

Read-only adversarial probes:

```text
path_escape: REJECTED
classification_source_escape: REJECTED
name_family_drift: REJECTED
duplicate_catalog_ids: REJECTED
duplicate_category_ids: REJECTED
```

No new actionable findings were identified.

## Conclusion

Stage A satisfies the foundation plan and the Codex acceptance contract. The single-source Markdown status document, strict validation boundary and generated 22-method cache are ready for downstream integration.

Stage B is authorized. The three recorded `PAPER_NEEDED` items remain method-level research blockers and must not be marked complete without the requested papers, but they do not block the Stage B infrastructure work already allowed by the plan.
