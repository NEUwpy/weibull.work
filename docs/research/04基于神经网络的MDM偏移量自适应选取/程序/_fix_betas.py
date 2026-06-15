import os, re, glob

d = r"D:/weibull/docs/research/04基于神经网络的MDM偏移量自适应选取/程序"
pattern = re.compile(r'\[2\.0,\s*2\.5,\s*4\.0\]')
count = 0
for f in glob.glob(os.path.join(d, '*.py')):
    with open(f, 'r', encoding='utf-8') as fh:
        content = fh.read()
    new_content, n = pattern.subn('[1.5, 2.0, 2.5, 4.0, 5.0]', content)
    if n > 0:
        with open(f, 'w', encoding='utf-8', newline='') as fh:
            fh.write(new_content)
        count += n
        print(f'{os.path.basename(f)}: {n} replacements')

print(f'Total: {count} replacements')
