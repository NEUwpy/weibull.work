import json
import os

def migrate():
    with open('src/data/cases.json', 'r', encoding='utf-8') as f:
        cases = json.load(f)

    if not os.path.exists('src/content/cases'):
        os.makedirs('src/content/cases')

    for case in cases:
        # Skip c1 as I already created it manually
        if case['id'] == 'c1': continue
        
        file_path = f'src/content/cases/{case["id"]}.md'
        content = f'''---
id: "{case['id']}"
title: "{case['name']}"
industry: "{case.get('industry', '其他')}"
type: "{case.get('type', '未知')}"
size: "{case.get('size', '未知')}"
tags: {json.dumps(case.get('tags', []), ensure_ascii=False)}
created_at: "{case.get('created_at', '2024-01-01')}"
data_raw: |
  {case['dataRaw'].replace('\n', '\n  ')}
---

# 案例描述

{case.get('description', '无描述')}
'''
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
    print("Migration finished.")

if __name__ == "__main__":
    migrate()
