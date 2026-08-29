"""Study02 S5A 审计脚本：正文引用 ↔ 参考文献零 orphan 检查。

用法（Study02 根目录）：
    python paper/tools/audit_zero_orphan.py

检查项：
  1. 从当前论文正文（参考文献之前的全部文本）提取所有 [n] 引用；
  2. 从参考文献段提取 `^[n] ` 条目编号；
  3. 输出双向差集：orphan（正文引用但无条目）与 unused（条目但正文从未引用）。
    两者均为空 => 通过（0 orphan / 0 多余）。
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

DEFAULT_PAPER = Path(__file__).resolve().parents[1] / "论文初稿-v2.1-正面叙述精简版.md"
REF_MARKER = "## 参考文献"


def main() -> int:
    paper = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else DEFAULT_PAPER
    text = paper.read_text(encoding="utf-8")
    if REF_MARKER not in text:
        print(f"ERROR: '{REF_MARKER}' section not found in {paper.name}", file=sys.stderr)
        return 2
    body = text.split(REF_MARKER)[0]
    refs_section = text.split(REF_MARKER)[1]

    # 只接受整个括号组都是整数引用的形式，例如 [1] 或 [8,9,10]。
    # 这会排除 CI [0.49%,0.88%] 和数学式 max[0, ...]，避免把其中的 0 当文献号。
    cited: set[int] = set()
    for grp in re.findall(r"\[([^\]]*)\]", body):
        if re.fullmatch(r"\s*\d{1,2}(?:\s*,\s*\d{1,2})*\s*", grp):
            cited.update(int(tok) for tok in re.findall(r"\d{1,2}", grp))

    refs: set[int] = set(int(m) for m in re.findall(r"^\[(\d{1,2})\]", refs_section, re.M))

    orphan = sorted(cited - refs)
    unused = sorted(refs - cited)

    print(f"body cited : {sorted(cited)}")
    print(f"refs entry : {sorted(refs)}")
    print(f"orphan     : {orphan}  ({len(orphan)})")
    print(f"unused     : {unused}  ({len(unused)})")

    ok = not orphan and not unused
    print("PASS 0 orphan / 0 unused" if ok else "FAIL: see orphan/unused above")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
