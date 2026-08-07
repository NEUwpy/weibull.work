"""Study02 S5A 审计脚本：正文引用 ↔ 参考文献零 orphan 检查。

用法（Study02 根目录）：
    python 16-audit-zero-orphan.py

检查项：
  1. 从 `14-PQ-论文初稿.md` 正文（参考文献之前的全部文本）提取所有 [n] 引用；
  2. 从参考文献段提取 `^[n] ` 条目编号；
  3. 输出双向差集：orphan（正文引用但无条目）与 unused（条目但正文从未引用）。
    两者均为空 => 通过（0 orphan / 0 多余）。
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

PAPER = Path(__file__).resolve().parent / "14-PQ-论文初稿.md"
REF_MARKER = "## 参考文献"


def main() -> int:
    text = PAPER.read_text(encoding="utf-8")
    if REF_MARKER not in text:
        print(f"ERROR: '{REF_MARKER}' section not found in {PAPER.name}", file=sys.stderr)
        return 2
    body = text.split(REF_MARKER)[0]
    refs_section = text.split(REF_MARKER)[1]

    # 正文所有括号组内的纯整数 token（排除 CI 区间、小数、负数、非引用括号）
    cited: set[int] = set()
    for grp in re.findall(r"\[([^\]]*)\]", body):
        for tok in re.findall(r"(?<![.\d])(\d{1,2})(?![.\d])", grp):
            cited.add(int(tok))

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
