# -*- coding: utf-8 -*-
import re

# 翻译文件处理
frontmatter_trans = '''---
title: "使用威布尔分布：可靠性、建模与推断"
title_en: "Using the Weibull Distribution: Reliability, Modeling, and Inference"
author: "John I. McCool"
affiliation: "Penn State University"
publication: "John Wiley & Sons, Inc."
short_publication: "Wiley 2012"
type: "书籍"
year: 2012
tags: ["威布尔分布", "参数估计", "MLE", "可靠性", "回归分析"]
summary: "本书系统介绍了威布尔分布的性质、参数估计方法（MLE、图形法等）、假设检验、回归分析以及在可靠性工程中的应用，包含完整的概率论基础和实用软件程序。"
related_method_id: "mle"

---

'''

# 读取翻译文件
with open(r'C:\Web\Weibull\src\content\421-003-pdf翻译.md', 'r', encoding='utf-8') as f:
    content = f.read()

# 修复图片路径
content = re.sub(r'!\[(.*?)\]\(images/', r'![\1](/421-003-图片/images/', content)

# 格式化图题：去掉加粗、去掉空行
content = re.sub(
    r'!\[(.*?)\]\((.*?)\)\s*\n\s*\*\*(图\d+\.|Fig\.\d+)\s+(.*?)\*\*',
    r'![\1](\2)\n\3 \4',
    content
)

# 写入frontmatter + 处理后的内容
with open(r'C:\Web\Weibull\src\content\421-003-pdf翻译.md', 'w', encoding='utf-8') as f:
    f.write(frontmatter_trans + content)

print("翻译文件处理完成")

# 原文文件处理
frontmatter_orig = '''---
title: "Using the Weibull Distribution: Reliability, Modeling, and Inference"
author: "John I. McCool"
affiliation: "Penn State University"
publication: "John Wiley & Sons, Inc."
short_publication: "Wiley 2012"
type: "书籍"
year: 2012
tags: ["Weibull Distribution", "Parameter Estimation", "MLE", "Reliability", "Regression"]
summary: "A comprehensive guide to Weibull distribution properties, parameter estimation methods (MLE, graphical), hypothesis testing, regression analysis, and applications in reliability engineering, with complete probability theory foundations and practical software programs."
related_method_id: "mle"

---

'''

# 读取原文文件
with open(r'C:\Web\Weibull\src\content\421-003-pdf原文.md', 'r', encoding='utf-8') as f:
    content = f.read()

# 修复图片路径
content = re.sub(r'!\[(.*?)\]\(images/', r'![\1](/421-003-图片/images/', content)

# 格式化图题：去掉加粗、去掉空行
content = re.sub(
    r'!\[(.*?)\]\((.*?)\)\s*\n\s*\*\*(图\d+\.|Fig\.\d+)\s+(.*?)\*\*',
    r'![\1](\2)\n\3 \4',
    content
)

# 写入frontmatter + 处理后的内容
with open(r'C:\Web\Weibull\src\content\421-003-pdf原文.md', 'w', encoding='utf-8') as f:
    f.write(frontmatter_orig + content)

print("原文文件处理完成")
