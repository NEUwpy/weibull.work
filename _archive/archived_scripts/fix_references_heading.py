# -*- coding: utf-8 -*-
import re

# 处理原文文件 - 修复 # REFERENCES
with open(r'C:\Web\Weibull\src\content\421-003-pdf原文.md', 'r', encoding='utf-8') as f:
    content = f.read()

# 修复 # REFERENCES → References (包括所有大小写组合)
content = re.sub(r'^# REFERENCES$', 'References', content, flags=re.MULTILINE)
content = re.sub(r'^## REFERENCES$', 'References', content, flags=re.MULTILINE)

# 写回文件
with open(r'C:\Web\Weibull\src\content\421-003-pdf原文.md', 'w', encoding='utf-8') as f:
    f.write(content)

print("原文文件 # REFERENCES 修复完成")
