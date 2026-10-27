# -*- coding: utf-8 -*-
import re

# 处理翻译文件
with open(r'C:\Web\Weibull\src\content\421-003-pdf翻译.md', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. 删除参考文献的层级：# 参考文献 → 参考文献（包括## References等）
content = re.sub(r'^# 参考文献$', '参考文献', content, flags=re.MULTILINE)
content = re.sub(r'^## 参考文献$', '参考文献', content, flags=re.MULTILINE)

# 2. 删除示例的层级
content = re.sub(r'^## 示例$', '示例', content, flags=re.MULTILINE)
content = re.sub(r'^# 示例 (\d+)$', r'示例 \1', content, flags=re.MULTILINE)

# 写回文件
with open(r'C:\Web\Weibull\src\content\421-003-pdf翻译.md', 'w', encoding='utf-8') as f:
    f.write(content)

print("翻译文件修复完成")

# 处理原文文件
with open(r'C:\Web\Weibull\src\content\421-003-pdf原文.md', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. 删除References的层级
content = re.sub(r'^# References$', 'References', content, flags=re.MULTILINE)
content = re.sub(r'^## References$', 'References', content, flags=re.MULTILINE)

# 2. 删除Examples的层级
content = re.sub(r'^## Examples$', 'Examples', content, flags=re.MULTILINE)
content = re.sub(r'^# Example (\d+)$', r'Example \1', content, flags=re.MULTILINE)

# 写回文件
with open(r'C:\Web\Weibull\src\content\421-003-pdf原文.md', 'w', encoding='utf-8') as f:
    f.write(content)

print("原文文件修复完成")
