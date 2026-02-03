# -*- coding: utf-8 -*-
import re

def fix_original_headings(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # 修复章节标题：Chapter X → # Chapter X
    # 匹配行首的Chapter X（可能带空格），添加#
    content = re.sub(
        r'^(Chapter \d+[^#\n]*)$',
        r'# \1',
        content,
        flags=re.MULTILINE
    )

    # 修复小节标题：X.x → ## X.x
    content = re.sub(
        r'^(\d+\.\d+\s+[^\n#]+)$',
        r'## \1',
        content,
        flags=re.MULTILINE
    )

    # 修复子小节标题：X.x.x → ### X.x.x
    content = re.sub(
        r'^(\d+\.\d+\.\d+\s+[^\n#]+)$',
        r'### \1',
        content,
        flags=re.MULTILINE
    )

    # 修复附录标题：Appendix X → # Appendix X
    content = re.sub(
        r'^(Appendix [A-Z][^\n#]*)$',
        r'# \1',
        content,
        flags=re.MULTILINE
    )

    # 修复附录小节：X.x → ## X.x（附录小节）
    content = re.sub(
        r'^([A-Z]\.\d+\s+[^\n#]+)$',
        r'## \1',
        content,
        flags=re.MULTILINE
    )

    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)

    print(f"Fixed headings in {file_path}")

# 处理原文文件
fix_original_headings(r'C:\Web\Weibull\src\content\421-001-pdf原文.md')
print("\nOriginal file headings fixed!")
