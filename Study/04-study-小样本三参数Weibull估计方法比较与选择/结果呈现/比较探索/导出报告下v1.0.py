"""将方法对比v1.0审定内容写回正式Markdown；复用任务中的PNG。"""
from pathlib import Path
from urllib.parse import unquote, urlparse
import argparse
import json
import os
import re
import xml.etree.ElementTree as ET

STUDY = Path(__file__).resolve().parents[2]
REVIEW = STUDY / 'reviewbyhtml/方法对比-v1.0'


def local_link(value):
    if value.startswith('file:///'):
        path = Path(unquote(urlparse(value).path).lstrip('/'))
        return Path(os.path.relpath(path, STUDY)).as_posix()
    return value


def content(node):
    return (node.text or '') + ''.join(markdown(child) + (child.tail or '') for child in node)


def markdown(node):
    tag = node.tag.rsplit('}', 1)[-1]
    if tag == 'math':
        # This reviewed formula has no original TeX annotation in the static MathML.
        expression = ''.join(node.itertext()).replace('\u2009', '')
        if expression != 'E(γ^−γ)=ηΓ(1+1/β)n−1/β.':
            raise ValueError(f'请核对新增公式的Markdown表达：{expression}')
        return '\n\n$$\n' + r'\operatorname{E}(\hat{\gamma}-\gamma)=\eta\,\Gamma(1+1/\beta)\,n^{-1/\beta}.' + '\n$$\n\n'
    if tag == 'table':
        rows = [[content(cell).strip().replace('|', r'\|') for cell in row]
                for row in node.iter('tr')]
        lines = ['| ' + ' | '.join(row) + ' |' for row in rows]
        lines.insert(1, '| ' + ' | '.join('---' for _ in rows[0]) + ' |')
        return '\n\n' + '\n'.join(lines) + '\n\n'
    if tag in ('ol', 'ul'):
        lines = []
        for index, item in enumerate(node, 1):
            prefix = f'{index}. ' if tag == 'ol' else '- '
            text = content(item).strip().replace('\n\n', '\n\n   ')
            lines.append(prefix + text)
        return '\n\n' + '\n\n'.join(lines) + '\n\n'
    text = content(node)
    if tag in ('strong', 'b'):
        return '**' + text + '**'
    if tag in ('em', 'i', 'small'):
        return '*' + text + '*'
    if tag == 'a':
        return '[' + text + '](' + local_link(node.attrib['href']) + ')'
    if tag == 'br':
        return '  \n'
    if tag in ('p', 'div'):
        return '\n\n' + text + '\n\n'
    if tag in ('root', 'span', 'mark'):
        return text
    raise ValueError(f'尚未处理的HTML节点：{tag}')


def html_to_markdown(markup):
    return re.sub(r'\n{3,}', '\n\n', markdown(ET.fromstring('<root>' + markup + '</root>'))).strip()


def image(path, alt):
    source = (REVIEW / path).resolve()
    if not source.is_relative_to(REVIEW.resolve()) or not source.is_file():
        raise ValueError(f'图片缺失或路径越界：{path}')
    return f'![{alt}]({source.relative_to(STUDY).as_posix()})'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--draft', action='store_true', help='输出已获修改授权、尚在审阅的修订稿')
    args = parser.parse_args()
    board = json.loads((REVIEW / 'board.json').read_text(encoding='utf-8'))
    if not (board.get('archive_pending') or board.get('review_complete') or args.draft):
        raise SystemExit('请先在HTML中确认存档。')
    target = (REVIEW / board.get('source_document', '../../报告下（方法对比）-v1.0.md')).resolve()
    if not target.is_relative_to(STUDY):
        raise ValueError('成果路径须位于Study04内。')
    version = board.get('manuscript_version', '1.0')
    lines = ['# ' + board['title'], '', f'**报告下（方法对比）v{version}｜2026-10-21**', '']
    image_count = 0
    for unit in board['units']:
        if unit.get('mode') != 'content':
            raise ValueError(f'仍有未审定候选：{unit["id"]}')
        if unit['id'] != 'manuscript-outline' and not unit.get('inline'):
            level = 3 if re.match(r'^\d+\.\d+', unit['title']) else 2
            lines.extend(['#' * level + ' ' + unit['title'], ''])
        for option in unit['options']:
            for block in option['blocks']:
                if block['kind'] == 'gallery':
                    for slide in block['images']:
                        lines.extend(['#### ' + slide['label'], '', image(slide['src'], slide.get('alt', slide['label'])), ''])
                        image_count += 1
                elif block['kind'] == 'image':
                    lines.extend([image(block['src'], block.get('alt', '')), ''])
                    image_count += 1
                else:
                    lines.extend([html_to_markdown(block['html']), ''])
    target.write_text('\n'.join(lines).rstrip() + '\n', encoding='utf-8')
    print(json.dumps({'target': str(target), 'images': image_count,
                      'source_revision': board['revision']}, ensure_ascii=False))


if __name__ == '__main__':
    main()
