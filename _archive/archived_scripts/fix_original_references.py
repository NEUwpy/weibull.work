# -*- coding: utf-8 -*-
import re

# 读取原文文件
with open(r'C:\Web\Weibull\src\content\421-003-pdf原文.md', 'r', encoding='utf-8') as f:
    content = f.read()

# 处理章末参考文献，添加序号
lines = content.split('\n')
result = []
ref_counter = 1
in_references = False
chapter_marker = None

for i, line in enumerate(lines):
    # 检查是否是章标题（用于标记章节）
    if re.match(r'^# \d+\.', line):
        chapter_marker = line.strip()

    # 检查是否进入参考文献部分
    if line.strip() == '## References':
        in_references = True
        # 如果是第一个参考文献块，添加章节标记
        if ref_counter == 1:
            result.append('')
            result.append('## References')
            result.append('')
            if chapter_marker:
                result.append(chapter_marker)
        result.append('')  # 空行
        continue

    # 检查是否离开参考文献部分（遇到EXERCISES或下一个章节）
    if in_references and (line.startswith('Exercises') or line.startswith('### EXERCISES') or line.startswith('## ') or re.match(r'^# \d+\.', line)):
        in_references = False
        result.append(line)
        continue

    # 在参考文献部分，给文献条目添加序号
    if in_references:
        stripped = line.strip()
        # 如果是空行，保留
        if not stripped:
            result.append(line)
        # 如果是作者名开头（英文大写字母），添加序号
        elif re.match(r'^[A-Z][a-z]+,', stripped):
            result.append(f'[{ref_counter}] {line}')
            ref_counter += 1
        else:
            result.append(line)
    else:
        result.append(line)

content_processed = '\n'.join(result)

# 写回文件
with open(r'C:\Web\Weibull\src\content\421-003-pdf原文.md', 'w', encoding='utf-8') as f:
    f.write(content_processed)

print("原文文件参考文献序号添加完成")
