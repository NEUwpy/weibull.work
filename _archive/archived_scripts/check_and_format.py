# -*- coding: utf-8 -*-
import re

# 读取翻译文件
with open(r'C:\Web\Weibull\src\content\421-001-pdf翻译.md', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. 检查章节结构
chapters_translation = []
for match in re.finditer(r'^# 第(\d+)章[^\n]*', content, re.MULTILINE):
    line_num = content[:match.start()].count('\n') + 1
    chapters_translation.append((line_num, match.group(0)))

print("=" * 60)
print("翻译文件章节结构：")
for line, chapter in chapters_translation:
    print(f"  行{line:5d}: {chapter}")

print(f"\n翻译文件共有 {len(chapters_translation)} 章")

# 2. 格式化表题和图题：居中对齐且加粗
lines = content.split('\n')
new_lines = []

for line in lines:
    # 匹配表题格式：图X.X 或 Figure X.X
    if line.strip().startswith('!') and '图' in line:
        # 查找图片后的描述
        if '图' in line and '- ' in line:
            # 格式：![alt](path)\n描述文字
            # 需要找到描述文字的行
            pass
    elif re.match(r'^图\d', line.strip()) or re.match(r'^Figure \d', line.strip()):
        # 表题行 - 添加加粗
        if not line.strip().startswith('**'):
            line = f"**{line}**"
    # 匹配表题：表X.X 或 Table X.X
    elif re.match(r'^表\d', line.strip()) or re.match(r'^Table \d', line.strip()):
        # 表题行 - 添加加粗
        if not line.strip().startswith('**'):
            line = f"**{line}**"

    new_lines.append(line)

# 写回文件
with open(r'C:\Web\Weibull\src\content\421-001-pdf翻译.md', 'w', encoding='utf-8') as f:
    f.write('\n'.join(new_lines))

print("\n" + "=" * 60)
print("表题和图题已格式化为加粗")

# 3. 现在检查各章节节标题对比
print("\n" + "=" * 60)
print("章节节标题对比：")

# 读取原文
with open(r'C:\Web\Weibull\src\content\421-001-pdf原文.md', 'r', encoding='utf-8') as f:
    original_lines = f.readlines()

# 统计各章的节标题
chapter_sections = {}
current_chapter = None

for i, line in enumerate(original_lines):
    # 检测章节
    if re.match(r'^# Chapter (\d+)', line):
        match = re.match(r'^# Chapter (\d+):?\s*(.+)', line)
        if match:
            current_chapter = f"Chapter {match.group(1)}: {match.group(2).strip()}"
            chapter_sections[current_chapter] = []
    # 检测节标题
    elif current_chapter and re.match(r'^## \d+\.\d+', line):
        chapter_sections[current_chapter].append((i+1, line.strip()))

# 打印统计
print(f"\n原文节标题统计：")
for chapter in sorted(chapter_sections.keys()):
    if chapter.startswith('Chapter 1') or chapter.startswith('Chapter 2'):
        print(f"\n{chapter}:")
        for line_no, title in chapter_sections[chapter][:5]:  # 只显示前5个
            print(f"  行{line_no:5d}: {title}")
        print(f"  ... 共{len(chapter_sections[chapter])}节")
