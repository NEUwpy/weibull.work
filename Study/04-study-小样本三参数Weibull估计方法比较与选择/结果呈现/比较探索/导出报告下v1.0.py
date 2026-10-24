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
        expression = ''.join(node.itertext()).replace('\u2009', '').replace('\u2061', '')
        formulas = {
            'x(1)': r'x_{(1)}',
            'x(1)−γ': r'x_{(1)}-\gamma',
            '0<d<η': r'0<d<\eta',
            'Pr(x(1)>γ+d)=[1−F(γ+d)]n=exp[−n(dη)β],d>0.': r'\Pr\left(x_{(1)}>\gamma+d\right)=[1-F(\gamma+d)]^n=\exp\left[-n\left(\frac{d}{\eta}\right)^\beta\right],\qquad d>0.',
            'E(γ^−γ)=ηΓ(1+1/β)n−1/β.': r'\operatorname{E}(\hat{\gamma}-\gamma)=\eta\,\Gamma(1+1/\beta)\,n^{-1/\beta}.',
            'RMSE(γ^)=ηn−1/βΓ(1+2/β).': r'\operatorname{RMSE}(\hat{\gamma})=\eta n^{-1/\beta}\sqrt{\Gamma(1+2/\beta)}.',
            'T=γ+ηexp(Z/β)': r'T=\gamma+\eta\exp(Z/\beta)',
            'Z=lnE': r'Z=\ln E',
            'E∼Exp(1)': r'E\sim\operatorname{Exp}(1)',
            'T≈(γ+η)+ηβZ.': r'T\approx(\gamma+\eta)+(\eta/\beta)Z.',
            'RMSE2=Bias2+VR,VR=R−1RSD2.': r'\operatorname{RMSE}^2=\operatorname{Bias}^2+V_R,\qquad V_R=\frac{R-1}{R}\operatorname{SD}^2.',
            'ΔRMSE2=ΔBias2+ΔVR.': r'\Delta\operatorname{RMSE}^2=\Delta\operatorname{Bias}^2+\Delta V_R.',
            'gn(γ)': r'g_n(\gamma)',
            'γ^=x(1)': r'\hat\gamma=x_{(1)}',
            'Δγ^≈−Δgn(γ^)/gn′(γ^)': r"\Delta\hat\gamma\approx-\Delta g_n(\hat\gamma)/g_n'(\hat\gamma)",
            '1−R2': r'1-R^2',
            'm': r'm',
            'θ=(β,η,γ)': r'\theta=(\beta,\eta,\gamma)',
            'q=Fθ(m)=∫γmfθ(t),dt.': r'q=F_\theta(m)=\int_\gamma^m f_\theta(t)\,\mathrm{d}t.',
            'm=1226.9': r'm=1226.9',
            'q': r'q',
            'Pθ(X(1)≥m)=[1−Fθ(m)]n=(1−q)n.': r'P_\theta(X_{(1)}\geq m)=[1-F_\theta(m)]^n=(1-q)^n.',
            '(R−1)SD2/R': r'(R-1)\operatorname{SD}^2/R',
            'κ=η0Sn′′(γ^)': r"\kappa=\eta_0S_n''(\hat\gamma)",
            'κ=η02[−ℓp′′(γ^)]': r"\kappa=\eta_0^2[-\ell_p''(\hat\gamma)]",
            'η0=1000': r'\eta_0=1000',
            'RMSE2': r'\mathrm{RMSE}^2',
            'Bias2': r'\mathrm{Bias}^2',
            'VR=(R−1)SD2/R': r'V_R=(R-1)\mathrm{SD}^2/R',
            'ΔMSE=ΔBias2+ΔVR': r'\Delta\mathrm{MSE}=\Delta\mathrm{Bias}^2+\Delta V_R',
        }
        if expression not in formulas:
            raise ValueError(f'请核对新增公式的Markdown表达：{expression}')
        tex = formulas[expression]
        return ('\n\n$$\n' + tex + '\n$$\n\n') if node.get('display') == 'block' else '$' + tex + '$'
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
        if 'href' not in node.attrib:
            return ('<a id="' + node.attrib['id'] + '"></a>' + text) if 'id' in node.attrib else text
        return '[' + text + '](' + local_link(node.attrib['href']) + ')'
    if tag == 'br':
        return '  \n'
    if tag in ('h2', 'h3', 'h4', 'h5'):
        return '\n\n' + '#' * int(tag[1]) + ' ' + text + '\n\n'
    if tag in ('sup', 'sub'):
        return '<' + tag + '>' + text + '</' + tag + '>'
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
    parser.add_argument('--draft-option', help='草稿暂按同名候选排版，HTML中的候选仍保持未选')
    args = parser.parse_args()
    if args.draft_option and not args.draft:
        parser.error('--draft-option只能与--draft一起使用')
    board = json.loads((REVIEW / 'board.json').read_text(encoding='utf-8'))
    if not (board.get('archive_pending') or board.get('review_complete') or args.draft):
        raise SystemExit('请先在HTML中确认存档。')
    target_value = board.get('archive_targets', {}).get('output') or board.get('source_document', '../../报告下（方法对比）-v1.0.md')
    target = (REVIEW / target_value).resolve()
    if not target.is_relative_to(STUDY):
        raise ValueError('成果路径须位于Study04内。')
    version = board.get('manuscript_version', '1.0')
    lines = ['# ' + board['title'], '', f'**报告下（方法对比）v{version}｜{board.get("manuscript_date", "2026-10-21")}**', '']
    if args.draft and any(u.get('mode') == 'choices' for u in board['units']):
        note = (f'此稿暂按各处“{args.draft_option}”候选排版，尚未审定；修改前后对照保留在原HTML任务中。'
                if args.draft_option else '包含尚未审定的局部候选，请在原HTML任务中继续审阅。')
        lines.extend(['> 待审稿：' + note, ''])
    image_count = 0
    for unit in board['units']:
        if unit.get('mode') != 'content' and not (args.draft and unit.get('mode') == 'choices'):
            raise ValueError(f'仍有未审定候选：{unit["id"]}')
        if unit['id'] != 'manuscript-outline' and not unit.get('inline'):
            level = 3 if re.match(r'^\d+\.\d+', unit['title']) else 2
            lines.extend(['#' * level + ' ' + unit['title'], ''])
        if unit.get('mode') == 'choices' and unit.get('context'):
            lines.extend(['*' + unit['context'] + '*', ''])
        options = unit['options']
        if unit.get('mode') == 'choices' and args.draft_option:
            options = [option for option in options if option['label'] == args.draft_option]
            if len(options) != 1:
                raise ValueError(f'候选名称不唯一或不存在：{unit["id"]} / {args.draft_option}')
        for option in options:
            if unit.get('mode') == 'choices' and not args.draft_option:
                lines.extend(['#### ' + option['label'], ''])
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
