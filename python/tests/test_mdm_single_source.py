from pathlib import Path
import os


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_mdm_has_no_legacy_branch_implementations():
    methods_dir = PROJECT_ROOT / "python" / "methods"
    legacy_files = {
        "mdm_case6.py",
        "mdm_case7.py",
        "mdm_case8.py",
        "mdm_fine.py",
        "mdm_variants.py",
        "mdm_paper.py",
        "mdm_engineering.py",
    }

    existing = {path.name for path in methods_dir.glob("mdm*.py")}

    assert existing == {"mdm.py"}
    assert existing.isdisjoint(legacy_files)


def test_source_does_not_import_legacy_mdm_branches():
    module_prefix = "methods." + "mdm"
    forbidden = tuple(
        module_prefix + suffix
        for suffix in (
            "_case6",
            "_case7",
            "_case8",
            "_fine",
            "_variants",
            "_paper",
            "_engineering",
        )
    )
    roots = [PROJECT_ROOT / "python", PROJECT_ROOT / "src"]
    offenders = []

    for root in roots:
        for directory, directories, files in os.walk(root):
            directories[:] = [name for name in directories
                              if name not in {".venv", "__pycache__", "_archive", "node_modules"}]
            for name in files:
                path = Path(directory) / name
                if path == Path(__file__).resolve():
                    continue
                if path.suffix not in {".py", ".ts", ".tsx", ".js", ".jsx"}:
                    continue
                text = path.read_text(encoding="utf-8")
                for token in forbidden:
                    if token in text:
                        offenders.append(f"{path.relative_to(PROJECT_ROOT)}: {token}")

    assert offenders == []
