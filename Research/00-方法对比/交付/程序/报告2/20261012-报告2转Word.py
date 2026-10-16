"""Export Report 2 with the Report 1 template and native MathType workflow."""
import argparse
import importlib.util
from pathlib import Path

HERE = Path(__file__).resolve().parent
mother = HERE.parent/'报告1/20261012-报告1转Word.py'
spec = importlib.util.spec_from_file_location('report_word', mother)
workflow = importlib.util.module_from_spec(spec)
spec.loader.exec_module(workflow)
workflow.REPORT_ID = 2
workflow.REPORT_TITLE = '小样本情况下的明显异常估计'
workflow.SOURCE = workflow.BASE/'报告2：小样本情况下的明显异常估计.md'
workflow.OUTPUT = workflow.SOURCE.with_suffix('.docx')
workflow.QA = workflow.BASE.parents[1]/'tmp/report2-word-20261012'
workflow.EXPECTED_IMAGES = 20
workflow.EXPECTED_FORMULAS = 30
# Presentation line breaks only; all terms and equation numbers are preserved.
workflow.WRAPPED_FORMULAS = {
    4: r'\begin{array}{l}\sigma_{\eta,\min}(\gamma)=\min_\beta\sigma_\eta(\gamma,\beta),\\\hat\beta(\gamma)=\underset{\beta}{\arg\min}\,\sigma_\eta(\gamma,\beta).\end{array}',
    17: r'\begin{array}{rl}T_1(\beta,\gamma)={}&\frac{J_2(n)}{\beta}+\frac1n\sum_i\ln (x_{(i)}-\gamma)\\&-\frac{\sum_i (x_{(i)}-\gamma)^\beta\ln (x_{(i)}-\gamma)}{\sum_i (x_{(i)}-\gamma)^\beta}.\end{array}',
    20: r'\begin{array}{l}\frac1n\sum_i\left(\frac{x_{(i)}-\hat\gamma}{\eta}\right)^{\hat\beta}=J_1(n)\\\Longrightarrow\quad\hat\eta=\left[\frac{\sum_i(x_{(i)}-\hat\gamma)^{\hat\beta}}{nJ_1(n)}\right]^{1/\hat\beta}.\end{array}',
    21: r'\begin{array}{rl}\ell(\beta,\eta,\gamma)={}&n\ln\beta-n\beta\ln\eta\\&+(\beta-1)\sum_i\ln (x_{(i)}-\gamma)-\sum_i((x_{(i)}-\gamma)/\eta)^\beta.\end{array}',
    22: r'\begin{array}{l}\frac{\partial\ell}{\partial\eta}=-\frac{n\beta}{\eta}+\frac{\beta}{\eta^{\beta+1}}\sum_i (x_{(i)}-\gamma)^\beta=0\\\Longrightarrow\quad\hat\eta(\beta,\gamma)=\left[\frac1n\sum_i (x_{(i)}-\gamma)^\beta\right]^{1/\beta}.\end{array}',
    29: r'\begin{array}{rl}\Pr\{X_{(1)}>\gamma+a\eta\}={}&[1-F_X(\gamma+a\eta)]^n\\&=\exp(-na^\beta),\qquad 0<a<1.\end{array}',
}

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepare-only', action='store_true')
    parser.add_argument('--verify', action='store_true')
    args = parser.parse_args()
    workflow.verify() if args.verify else workflow.run(args.prepare_only)
