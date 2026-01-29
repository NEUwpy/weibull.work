# -*- coding: utf-8 -*-
import re

# 处理翻译文件
with open(r'C:\Web\Weibull\src\content\421-003-pdf翻译.md', 'r', encoding='utf-8') as f:
    content = f.read()

# 删除所有层级的示例标题
content = re.sub(r'^#+ 示例$', '示例', content, flags=re.MULTILINE)
content = re.sub(r'^#+ 示例 (\d+)$', r'示例 \1', content, flags=re.MULTILINE)

# 删除所有层级的参考文献标题
content = re.sub(r'^#+ 参考文献$', '参考文献', content, flags=re.MULTILINE)

# 写回文件
with open(r'C:\Web\Weibull\src\content\421-003-pdf翻译.md', 'w', encoding='utf-8') as f:
    f.write(content)

print("翻译文件修复完成")

# 处理原文文件
with open(r'C:\Web\Weibull\src\content\421-003-pdf原文.md', 'r', encoding='utf-8') as f:
    content = f.read()

# 删除所有层级的Example标题
content = re.sub(r'^#+ Example (\d+)$', r'Example \1', content, flags=re.MULTILINE)
content = re.sub(r'^#+ Example$', 'Example', content, flags=re.MULTILINE)

# 删除所有层级的Examples标题
content = re.sub(r'^#+ Examples$', 'Examples', content, flags=re.MULTILINE)

# 删除所有层级的EXERCISES标题
content = re.sub(r'^#+ EXERCISES$', 'Exercises', content, flags=re.MULTILINE)

# 删除所有层级的References标题
content = re.sub(r'^#+ References$', 'References', content, flags=re.MULTILINE)

# 写回文件
with open(r'C:\Web\Weibull\src\content\421-003-pdf原文.md', 'w', encoding='utf-8') as f:
    f.write(content)

print("原文文件修复完成")
