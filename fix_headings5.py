# -*- coding: utf-8 -*-
import re

def fix_file(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # 规则1: ## 第x章 → # 第x章 (章节标题从2级升为1级)
    content = re.sub(r'^## (第\d+章)', r'# \1', content, flags=re.MULTILINE)

    # 规则2: ## 附录X → # 附录X (附录标题从2级升为1级)
    content = re.sub(r'^## (附录[ABCDEFHIJKLMNOPQRSTUVWXYZ])', r'# \1', content, flags=re.MULTILINE)

    # 规则3: ### x.x → ## x.x (小节标题从3级升为2级)
    content = re.sub(r'^### (\d+\.\d+)', r'## \1', content, flags=re.MULTILINE)

    # 规则4: #### x.x.x → ### x.x.x (子小节从4级升为3级)
    content = re.sub(r'^#### (\d+\.\d+\.\d+)', r'### \1', content, flags=re.MULTILINE)

    # 规则5: ### X.x (附录小节) → ## X.x (附录小节从3级升为2级)
    content = re.sub(r'^### ([A-Z]\.\d+)', r'## \1', content, flags=re.MULTILINE)

    # 规则6: ### 参考文献 → ## 参考文献 (参考文献从3级升为2级)
    content = re.sub(r'^### 参考文献\s*$', r'## 参考文献', content, flags=re.MULTILINE)

    # 规则7: ### 索引 → ## 索引 (索引从3级升为2级)
    content = re.sub(r'^### 索引\s*$', r'## 索引', content, flags=re.MULTILINE)

    # 规则8: ### M.x → ## M.x (附录M小节)
    content = re.sub(r'^### (M\.\d+)', r'## \1', content, flags=re.MULTILINE)

    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)

# 处理翻译文件
print("Processing translation file...")
fix_file(r'C:\Web\Weibull\src\content\421-001-pdf翻译.md')
print("Translation file updated")

# 处理原文文件
print("Processing original file...")
with open(r'C:\Web\Weibull\src\content\421-001-pdf原文.md', 'r', encoding='utf-8') as f:
    content = f.read()

# 英文版本
content = re.sub(r'^## (Chapter \d+)', r'# \1', content, flags=re.MULTILINE)
content = re.sub(r'^## (Appendix [A-Z])', r'# \1', content, flags=re.MULTILINE)
content = re.sub(r'^### (\d+\.\d+)', r'## \1', content, flags=re.MULTILINE)
content = re.sub(r'^#### (\d+\.\d+\.\d+)', r'### \1', content, flags=re.MULTILINE)
content = re.sub(r'^### ([A-Z]\.\d+)', r'## \1', content, flags=re.MULTILINE)
content = re.sub(r'^### References\s*$', r'## References', content, flags=re.MULTILINE)
content = re.sub(r'^### Index\s*$', r'## Index', content, flags=re.MULTILINE)

with open(r'C:\Web\Weibull\src\content\421-001-pdf原文.md', 'w', encoding='utf-8') as f:
    f.write(content)

print("Original file updated")
print("\nAll heading levels fixed!")
