# -*- coding: utf-8 -*-
import re

# 读取原文和翻译
with open(r'C:\Web\Weibull\src\content\421-001-pdf原文.md', 'r', encoding='utf-8') as f:
    original = f.read()

with open(r'C:\Web\Weibull\src\content\421-001-pdf翻译.md', 'r', encoding='utf-8') as f:
    translation = f.read()

# 分析原文章节结构
original_structure = {
    1: {'start': 484, 'title': 'Chapter 1: AN OVERVIEW OF WEIBULL ANALYSIS', 'sections': []},
    2: {'start': 746, 'title': 'Chapter 2: PLOTTING THE DATA AND INTERPRETING THE PLOT', 'sections': []},
    3: {'start': 1163, 'title': 'CHAPTER 3: DIRTY DATA, "BAD" WEIBULLS, AND UNCERTAINTIES', 'sections': []},
    4: {'start': 1509, 'title': 'CHAPTER 4: FAILURE FORECASTING = RISK ANALYSIS', 'sections': []},
    5: {'start': 2062, 'title': 'CHAPTER 5: MAXIMUM LIKELIHOOD ESTIMATES & OTHER ALTERNATIVE METHODS', 'sections': []},
    6: {'start': 2374, 'title': 'CHAPTER 6. WEIBAYES AND WEIBAYES SUBSTANTIATION TESTING...', 'sections': []},
    7: {'start': 3025, 'title': 'CHAPTER 7. INTERVAL ESTIMATES', 'sections': []},
    8: {'start': 3332, 'title': 'CHAPTER 8. RELATED MATH MODELS', 'sections': []},
    9: {'start': 3874, 'title': 'Chapter 9 - Crow-AMSAA Modeling, Warranty Analysis, & Life Cycle Costs', 'sections': []},
    10: {'start': 4469, 'title': 'CHAPTER 10. SUMMARY', 'sections': []},
    11: {'start': 4739, 'title': 'CHAPTER 11 - CASE STUDIES AND NEW APPLICATIONS', 'sections': []},
}

# 填充原文节标题
for chapter_num in sorted(original_structure.keys()):
    start = original_structure[chapter_num]['start']
    end = list(original_structure.keys())[chapter_num] if chapter_num < 11 else None
    if end is not None:
        end = original_structure[end]['start']

    lines = original.split('\n')
    for i in range(start - 1, end if end else len(lines)):
        line = lines[i]
        # 匹配节标题
        match = re.match(r'^## (\d+\.\d+)', line)
        if match:
            original_structure[chapter_num]['sections'].append((i+1, match.group(1), line.strip()))

# 分析翻译章节结构
translation_structure = {
    1: {'start': 125, 'title': '# 第1章 Weibull分析概述', 'sections': []},
    2: {'start': 447, 'title': '# 第2章：绘制数据和解释图表', 'sections': []},
    3: {'start': 867, 'title': '# 第3章：脏数据、"坏"Weibull和不确定性', 'sections': []},
    4: {'start': 1093, 'title': '# 第4章：故障预测 = 风险分析', 'sections': []},
    5: {'start': 1232, 'title': '# 第5章：最大似然估计和其他替代方法', 'sections': []},
    6: {'start': 1552, 'title': '# 第6章：Weibayes和Weibayes验证测试...', 'sections': []},
    7: {'start': 2194, 'title': '# 第7章. 区间估计', 'sections': []},
    8: {'start': 2501, 'title': '# 第8章. 相关数学模型', 'sections': []},
    9: {'start': 3037, 'title': '# 第9章 - Crow-AMSAA建模、保修分析和生命周期成本', 'sections': []},
    10: {'start': 3632, 'title': '# 第10章 总结', 'sections': []},
    11: {'start': 3901, 'title': '# 第11章 - 案例研究和新应用', 'sections': []},
}

# 填充翻译节标题
for chapter_num in sorted(translation_structure.keys()):
    start = translation_structure[chapter_num]['start']
    end = list(translation_structure.keys())[chapter_num] if chapter_num < 11 else None
    if end is not None:
        end = translation_structure[end]['start']

    lines = translation.split('\n')
    for i in range(start - 1, end if end else len(lines)):
        line = lines[i]
        # 匹配节标题
        match = re.match(r'^## (\d+\.\d+)', line)
        if match:
            translation_structure[chapter_num]['sections'].append((i+1, match.group(1), line.strip()))

# 打印对比结果
print("=" * 80)
print("原文与翻译章节结构对比：")
print("=" * 80)

for chapter_num in sorted(original_structure.keys()):
    orig = original_structure[chapter_num]
    trans = translation_structure.get(chapter_num)

    print(f"\n第{chapter_num}章:")
    print(f"  原文: {len(orig['sections'])}节")
    print(f"  翻译: {len(trans['sections'])}节")

    if abs(len(orig['sections']) - len(trans['sections'])) > 2:
        print(f"  !! 差异较大！")
        print(f"  原文节标题:")
        for _, num, title in orig['sections'][:10]:
            print(f"    {num}: {title[:80]}")
        print(f"  翻译节标题:")
        for _, num, title in trans['sections'][:10]:
            print(f"    {num}: {title[:80]}")
    else:
        print(f"  OK 数量基本一致")

# 检查缺失的附录
print("\n" + "=" * 80)
print("附录检查：")
print("=" * 80)

# 检查原文附录
appendices_original = []
for match in re.finditer(r'^APPENDIX ([A-Z])', original, re.MULTILINE):
    appendices_original.append(match.group(1))

# 检查翻译附录
appendices_translation = []
for match in re.finditer(r'^## 附录 ([A-Z])', translation, re.MULTILINE):
    appendices_translation.append(match.group(1))

print(f"原文附录: {appendices_original}")
print(f"翻译附录: {appendices_translation}")

print("\n检查完成！")
