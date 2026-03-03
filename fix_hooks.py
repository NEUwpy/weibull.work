"""
修复所有案例组件中的 hooks 顺序问题
将 useCaseList 移到条件返回之前
"""
import re

files_to_fix = [
    'src/components/case-studies/mdm/case5/Case5Viewer.tsx',
    'src/components/case-studies/mdm/case6/Case6Viewer.tsx',
    'src/components/case-studies/mdm/case7/Case7Viewer.tsx',
    'src/components/case-studies/mdm/case8/Case8Viewer.tsx',
    'src/components/case-studies/mdm/case9/Case9Viewer.tsx',
    'src/components/case-studies/mdm/case13/Case13Viewer.tsx',
    'src/components/case-studies/mdm/case14/Case14Viewer.tsx',
    'src/components/case-studies/mdm/case15/Case15Viewer.tsx',
]

for filepath in files_to_fix:
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # 找到 export default function 和第一个 useState 之间的位置
    # 在第一个 useState 之后添加 useCaseList

    # 模式：找到组件函数开头的 useState 声明块
    # 匹配: const [xxx, setXxx] = useState(...)
    pattern = r'(export default function \w+\([^)]*\) \{\s*(?:const \[[^\]]+\] = useState\([^)]*\)\s*)+)'

    def add_hook(match):
        base = match.group(1)
        # 检查是否已经有 useCaseList
        if 'useCaseList' in base:
            return base
        # 在最后一个 useState 之后添加 useCaseList
        return base + '\n  // 获取案例列表\n  const { cases: caseList } = useCaseList()\n'

    new_content = re.sub(pattern, add_hook, content, flags=re.DOTALL)

    # 删除后面重复的 useCaseList 调用
    # 匹配: // 获取案例列表 \n const { cases: caseList } = useCaseList()
    new_content = re.sub(
        r'\n\s*// 获取案例列表\s*\n\s*const \{ cases: caseList \} = useCaseList\(\)',
        '',
        new_content
    )

    if new_content != content:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(new_content)
        print(f"Fixed: {filepath}")
    else:
        print(f"No change: {filepath}")

print("\nDone!")
