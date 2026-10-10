"""Connect the minimum-value evidence to compensation and method criteria."""
import importlib.util
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location(
    'compact_intro_revision', HERE / '20261010-导入双论点与图证精简.py')
revision = importlib.util.module_from_spec(spec)
spec.loader.exec_module(revision)
revision.RECORD = Path(__file__).with_suffix('.json')

REPLACEMENTS = [
    (
        '高β、小n下，较弱的位置约束与三参数补偿，使偏移后的参数组合仍可能保持相近的中部拟合。',
        '高β、小n下，样本缺少真实起点附近的信息，对位置上移的约束较弱；尺度与形状的补偿又使偏移后的组合可能保持相近的中部拟合。',
    ),
    (
        '位置参数须满足γ<t₁，其中t₁为最小观测。最小观测与真实γ之间的距离，决定了位置上移所受的上界约束。',
        '所有观测均须大于位置参数γ，因此γ<t₁给出了位置参数的上界，其中t₁为最小观测。若最小观测远离真实γ，样本就缺少起点附近的信息，较高的γ仍可能满足这一支持条件。图2展示了这种约束随β和n的变化。',
    ),
    (
        'γ与η、β的相互补偿，使参数偏移未必造成明显的中部拟合差异（图3）。',
        '在这一较宽的位置取值范围内，γ上移使各观测到起点的距离缩短，η和β的降低可使中部分位点保持接近。图3以W(5,1000,500)、n=7的原第31组样本为例：其最小值约1167，γ=1000满足支持条件；η、β分别降至500和2后，所得分布在中部仍可贴近同一组观测。',
    ),
    (
        '**图3｜同一组W(5,1000,500)观测可同时贴近真分布与W(2,500,1000)的中部曲线。**',
        '**图3｜γ升高、η和β降低后，分布仍可贴近同一组观测。**',
    ),
    (
        '这些结果解释了偏移组合为何仍能与样本相容。下面从各方法的判据出发，分析实际估计为何发生偏移。',
        '因此，起点附近信息不足使较高的γ仍满足样本约束，而η、β的补偿使这一组合保有相近的中部拟合。第一章的共同偏移沿着这一补偿方向；下面进一步分析各方法的判据为何在这样的样本下产生偏移估计。',
    ),
]
for old, new in REPLACEMENTS:
    assert revision.INTRO.count(old) == 1
    revision.INTRO = revision.INTRO.replace(old, new)


def main():
    example = json.loads((HERE / '样本相容绘图数据.json').read_text(encoding='utf-8'))
    assert example['sample_id'] == 31 and example['n'] == 7
    assert round(min(example['observations'])) == 1167
    assert min(example['observations']) > 1000.
    assert example['curves'][0]['parameters_beta_eta_gamma'] == [5., 1000., 500.]
    assert example['curves'][1]['parameters_beta_eta_gamma'] == [2., 500., 1000.]
    revision.main()
    record = json.loads(revision.RECORD.read_text(encoding='utf-8'))
    record.update(task='2026-10-10: connect support evidence to compensated fit and estimator criteria',
                  reused_revision_entry='程序/20261010-导入双论点与图证精简.py',
                  revised_passages=len(REPLACEMENTS), moved_equations=0,
                  example_sample_id=31, example_n=7, example_minimum=min(example['observations']),
                  argument=['Missing observations near the true origin weaken the upper support bound.',
                            'The same archived sample permits gamma=1000 under that bound.',
                            'Eta and beta compensation can preserve the central fit at the higher gamma.',
                            'This motivates method-specific criteria analysis of the returned shifts.'])
    revision.RECORD.write_text(json.dumps(record, ensure_ascii=False, indent=2) + '\n',
                               encoding='utf-8', newline='\n')


if __name__ == '__main__':
    main()
