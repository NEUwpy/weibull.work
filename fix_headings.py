import re

def fix_heading_level(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    original_content = content

    # 规则1: # 第x章 → ## 第x章 (章节标题从1级降为2级)
    content = re.sub(
        r'^# (第\d+章)',
        r'## \1',
        content,
        flags=re.MULTILINE
    )

    # 规则2: # x.x.x → #### x.x.x (1级三级小节标题降为4级)
    content = re.sub(
        r'^# (\d+\.\d+\.\d+)',
        r'#### \1',
        content,
        flags=re.MULTILINE
    )

    # 规则3: ### x.x.x → #### x.x.x (3级三级小节标题降为4级)
    content = re.sub(
        r'^### (\d+\.\d+\.\d+)',
        r'#### \1',
        content,
        flags=re.MULTILINE
    )

    # 规则4: # x.x → ### x.x (1级二级小节标题降为3级)
    content = re.sub(
        r'^# (\d+\.\d+)',
        r'### \1',
        content,
        flags=re.MULTILINE
    )

    # 规则5: ## x.x → ### x.x (2级二级小节标题降为3级)
    content = re.sub(
        r'^## (\d+\.\d+)',
        r'### \1',
        content,
        flags=re.MULTILINE
    )

    # 规则6: # 附录X → ## 附录X (附录标题从1级降为2级)
    content = re.sub(
        r'^# (附录[ABCDEFGHIJKLMNOPQRSTUVWXYZ]:?)',
        r'## \1',
        content,
        flags=re.MULTILINE
    )

    # 规则7: ## X.x (附录小节) → ### X.x (附录小节从2级降为3级)
    content = re.sub(
        r'^## ([ABCDEFGHIJKLMNOPQRSTUVWXYZ]\.\d+)',
        r'### \1',
        content,
        flags=re.MULTILINE
    )

    # 规则8: ## 参考文献 → # 参考文献 (参考文献从2级升为1级)
    content = re.sub(
        r'^## 参考文献\s*$',
        r'# 参考文献',
        content,
        flags=re.MULTILINE
    )

    # 规则9: ## 索引 → # 索引 (索引从2级升为1级)
    content = re.sub(
        r'^## 索引\s*$',
        r'# 索引',
        content,
        flags=re.MULTILINE
    )

    changes = content != original_content

    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)

    return changes

# 处理翻译文件
translation_file = r'C:\Web\Weibull\src\content\421-001-pdf翻译.md'
print(f"Processing translation file...")
if fix_heading_level(translation_file):
    print("Translation file updated")
else:
    print("No changes in translation file")

# 处理原文文件
original_file = r'C:\Web\Weibull\src\content\421-001-pdf原文.md'
print(f"Processing original file...")

with open(original_file, 'r', encoding='utf-8') as f:
    content = f.read()

# 英文版本的处理
# 规则1: # Chapter X → ## Chapter X
content = re.sub(
    r'^# (Chapter \d+)',
    r'## \1',
    content,
    flags=re.MULTILINE
)

# 规则2: # x.x.x → #### x.x.x
content = re.sub(
    r'^# (\d+\.\d+\.\d+)',
    r'#### \1',
    content,
    flags=re.MULTILINE
)

# 规则3: ### x.x.x → #### x.x.x
content = re.sub(
    r'^### (\d+\.\d+\.\d+)',
    r'#### \1',
    content,
    flags=re.MULTILINE
)

# 规则4: # x.x → ### x.x
content = re.sub(
    r'^# (\d+\.\d+)',
    r'### \1',
    content,
    flags=re.MULTILINE
)

# 规则5: ## x.x → ### x.x
content = re.sub(
    r'^## (\d+\.\d+)',
    r'### \1',
    content,
    flags=re.MULTILINE
)

# 规则6: # Appendix X → ## Appendix X
content = re.sub(
    r'^# (Appendix [ABCDEFGHIJKLMNOPQRSTUVWXYZ])',
    r'## \1',
    content,
    flags=re.MULTILINE
)

# 规则7: ## X.x → ### X.x
content = re.sub(
    r'^## ([ABCDEFGHIJKLMNOPQRSTUVWXYZ]\.\d+)',
    r'### \1',
    content,
    flags=re.MULTILINE
)

# 规则8: ## References → # References
content = re.sub(
    r'^## References\s*$',
    r'# References',
    content,
    flags=re.MULTILINE
)

# 规则9: ## Index → # Index
content = re.sub(
    r'^## Index\s*$',
    r'# Index',
    content,
    flags=re.MULTILINE
)

with open(original_file, 'w', encoding='utf-8') as f:
    f.write(content)

print("Original file updated")
print("\nHeading level fix completed!")
