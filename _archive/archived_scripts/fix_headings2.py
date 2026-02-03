import re

file_path = r'C:\Web\Weibull\src\content\421-001-pdf翻译.md'

with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# 规则1: # 参考文献 → ## 参考文献
content = re.sub(
    r'^# 参考文献\s*$',
    r'## 参考文献',
    content,
    flags=re.MULTILINE
)

# 规则2: # 索引 → ## 索引
content = re.sub(
    r'^# 索引\s*$',
    r'## 索引',
    content,
    flags=re.MULTILINE
)

# 规则3: 去掉非标题的#标记（步骤、案例研究、最优更换间隔等）
# 这些是1级标题但不是章节或附录标题
patterns_to_fix = [
    r'^# 步骤\d',
    r'^# 最优更换间隔',
    r'^# 成组更换',
    r'^# 案例研究\d+\.\d+\.\d+',
    r'^# William S Gosset',  # 这是图片说明，不是标题
]

for pattern in patterns_to_fix:
    content = re.sub(
        pattern,
        lambda m: m.group(0).replace('# ', ''),
        content,
        flags=re.MULTILINE
    )

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)

print("Translation file updated")

# 处理原文文件
original_file = r'C:\Web\Weibull\src\content\421-001-pdf原文.md'

with open(original_file, 'r', encoding='utf-8') as f:
    content = f.read()

# 规则1: # References → ## References
content = re.sub(
    r'^# References\s*$',
    r'## References',
    content,
    flags=re.MULTILINE
)

# 规则2: # Index → ## Index
content = re.sub(
    r'^# Index\s*$',
    r'## Index',
    content,
    flags=re.MULTILINE
)

# 规则3: 去掉非标题的#标记
patterns_to_fix_en = [
    r'^# Step \d+',
    r'^# Optimum',
    r'^# Block',
    r'^# Case Study',
    r'^# William S Gosset',
]

for pattern in patterns_to_fix_en:
    content = re.sub(
        pattern,
        lambda m: m.group(0).replace('# ', ''),
        content,
        flags=re.MULTILINE
    )

with open(original_file, 'w', encoding='utf-8') as f:
    f.write(content)

print("Original file updated")
print("\nFix completed!")
