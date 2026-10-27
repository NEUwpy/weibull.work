# -*- coding: utf-8 -*-
import re

# 处理原文文件
original_file = r'C:\Web\Weibull\src\content\421-001-pdf原文.md'

with open(original_file, 'r', encoding='utf-8') as f:
    lines = f.readlines()

new_lines = []
for line in lines:
    # 保留作为1级标题的
    preserve_level1 = [
        "# The New Weibull Handbook",
        "# Dedication",
        "# Preface",
        "# New Technology for the Fifth Edition",
        "# Table of Contents",
    ]

    if any(line.startswith(p) for p in preserve_level1):
        new_lines.append(line)
        continue

    # 附录小节：# X.x → ### X.x
    match = re.match(r"^# ([A-Z]\.\d+) (.*)", line)
    if match:
        section_num = match.group(1)
        rest = match.group(2)
        line = f"### {section_num} {rest}\n"
    # 习题类：去掉#
    elif re.match(r"^# (Problem|Exercise)\s*\d", line):
        line = line.replace("# ", "", 1)
    # 其他需要去掉#的模式
    elif re.match(r"^# (Typical|Test|Example|Facts from|Batch|Analysis|Crow-AMSAA|Contributed|Introduction|Background|Statistical|Main|Branch|Select|WEIBULL)", line):
        line = line.replace("# ", "", 1)
    # 剩余的1级标题如果不是Chapter/Appendix，去掉#
    elif line.startswith("# ") and not re.search(r"^# Chapter \d+", line) and not re.search(r"^# Appendix [A-Z]", line):
        line = line.replace("# ", "", 1)

    new_lines.append(line)

with open(original_file, 'w', encoding='utf-8') as f:
    f.writelines(new_lines)

print("Original file level 1 headings cleaned")

# 处理2级标题中非标题的
with open(original_file, 'r', encoding='utf-8') as f:
    lines = f.readlines()

new_lines = []
for line in lines:
    if line.startswith("## "):
        # 保留Chapter、Appendix、References、Index
        if not re.search(r"^## (Chapter \d+|Appendix [A-Z]|References|Index)", line):
            line = line.replace("## ", "", 1)
    new_lines.append(line)

with open(original_file, 'w', encoding='utf-8') as f:
    f.writelines(new_lines)

print("Original file level 2 headings cleaned")
print("\nAll files updated!")
