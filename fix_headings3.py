# -*- coding: utf-8 -*-
import re

file_path = r'C:\Web\Weibull\src\content\421-001-pdf翻译.md'

with open(file_path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

new_lines = []
for line in lines:
    # 保留作为1级标题的（文档主要部分）
    preserve_level1 = [
        "# 新威布尔手册",
        "# 献词",
        "# 前言",
        "# 第五版的新技术特点",
        "# 目录",
    ]

    # 检查是否在保留列表中
    if any(line.startswith(p) for p in preserve_level1):
        new_lines.append(line)
        continue

    # 去掉#的模式（非标题的句子说明）
    removed = False

    # 附录小节：# X.x → ### X.x
    match = re.match(r"^# ([A-Z]\.\d+) (.*)", line)
    if match:
        section_num = match.group(1)
        rest = match.group(2)
        line = f"### {section_num} {rest}\n"
        removed = True

    # 习题类：去掉#
    elif re.match(r"^# (习题|问题)\s*\d", line):
        line = line.replace("# ", "", 1)
        removed = True

    # 其他需要去掉#的模式
    elif re.match(r"^# (典型故障情况|测试具有不同测试时间|示例|来自生产数据|批次线索|批次分析|Crow-AMSAA|由Honda|问题介绍|背景$|统计分析|主分支|分支[ABCDE]|选择寿命数据|WEIBULL纸)", line):
        line = line.replace("# ", "", 1)
        removed = True

    # 剩余的1级标题如果不是章节/附录，去掉#
    elif line.startswith("# ") and not re.search(r"^# 第\d+章", line) and not re.search(r"^# 附录[ABCDEFGHIJKLMNOPQRSTUVWXYZ]", line):
        line = line.replace("# ", "", 1)
        removed = True

    new_lines.append(line)

with open(file_path, 'w', encoding='utf-8') as f:
    f.writelines(new_lines)

print("Level 1 headings cleaned")

# 处理2级标题中非标题的
with open(file_path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

new_lines = []
for line in lines:
    # 去掉##中非标题的
    if line.startswith("## "):
        # 保留章节、附录、参考文献、索引
        if not re.search(r"^## (第\d+章|附录[ABCDEFGHIJKLMNOPQRSTUVWXYZ]|参考文献|索引)", line):
            line = line.replace("## ", "", 1)
    new_lines.append(line)

with open(file_path, 'w', encoding='utf-8') as f:
    f.writelines(new_lines)

print("Level 2 headings cleaned")
print("\nFix completed!")
