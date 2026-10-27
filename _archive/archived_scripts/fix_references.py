# -*- coding: utf-8 -*-
import re

# 读取翻译文件
with open(r'C:\Web\Weibull\src\content\421-003-pdf翻译.md', 'r', encoding='utf-8') as f:
    content = f.read()

# 处理章末参考文献，添加序号
# 模式：找到 ## 参考文献 或 # 参考文献，然后给后续的文献条目添加序号

def add_reference_numbers(content):
    """为章末参考文献添加序号"""
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
        if line.strip() in ['## 参考文献', '# 参考文献']:
            in_references = True
            # 如果是第一个参考文献块，添加章节标记
            if ref_counter == 1 and chapter_marker:
                result.append('')
                result.append('# 参考文献')
                result.append('')
                result.append(chapter_marker)
            result.append('')  # 空行
            continue

        # 检查是否离开参考文献部分（遇到练习或下一个章节）
        if in_references and (line.startswith('练习') or line.startswith('## ') or line.startswith('# 练习') or re.match(r'^# \d+\.', line)):
            in_references = False
            result.append(line)
            continue

        # 在参考文献部分，给文献条目添加序号
        if in_references:
            stripped = line.strip()
            # 如果是空行，保留
            if not stripped:
                result.append(line)
            # 如果是作者名开头（英文大写字母或中文），添加序号
            elif re.match(r'^[A-Z][a-z]+,|^[\u4e00-\u9fa5]', stripped):
                result.append(f'[{ref_counter}] {line}')
                ref_counter += 1
            else:
                result.append(line)
        else:
            result.append(line)

    return '\n'.join(result)

# 处理翻译文件
content_processed = add_reference_numbers(content)

# 写回文件
with open(r'C:\Web\Weibull\src\content\421-003-pdf翻译.md', 'w', encoding='utf-8') as f:
    f.write(content_processed)

print("翻译文件参考文献序号添加完成")

# 处理原文文件
with open(r'C:\Web\Weibull\src\content\421-003-pdf原文.md', 'r', encoding='utf-8') as f:
    content = f.read()

content_processed = add_reference_numbers(content)

with open(r'C:\Web\Weibull\src\content\421-003-pdf原文.md', 'w', encoding='utf-8') as f:
    f.write(content_processed)

print("原文文件参考文献序号添加完成")
