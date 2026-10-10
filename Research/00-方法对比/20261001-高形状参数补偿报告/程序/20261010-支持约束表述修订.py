"""Replace conversational support/fit wording with precise academic prose."""
import importlib.util
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location(
    'prose_revision', HERE / '20261010-最小值约束与同样本拟合.py')
revision = importlib.util.module_from_spec(spec)
spec.loader.exec_module(revision)
revision.RECORD = Path(__file__).with_suffix('.json')
revision.REPLACEMENTS = [
    (
        '图2显示，固定η和γ时，β=5的最小观测通常比β=2更远离真实γ，尤其在小n下。因此，γ即使明显高于真值，也可能仍低于最小观测，未被样本排除。随n增大，最小观测总体向真实γ靠近，对γ上移的限制增强。',
        '图2显示，固定η和γ时，β=5的最小观测通常比β=2更远离真实γ，尤其在小n下。因此，偏高的γ仍可能满足样本支持条件γ<t₁。随n增大，最小观测总体向真实γ靠近，对γ上移的限制增强。',
    ),
    (
        'γ未被最小观测排除，只说明它可行。偏移组合要能拟合样本，还需η和β补偿。γ升高时，观测到起点的距离tᵢ−γ缩短。由F(Q(p))=p，得到寿命分位点：',
        '样本支持条件γ<t₁限定了位置参数的取值范围；参数组合的拟合程度则取决于β、η和γ的共同作用。γ上移使观测到起点的距离tᵢ−γ缩短，η和β的调整可使中部分位点保持接近。由F(Q(p))=p，得到寿命分位点：',
    ),
    (
        '图3中，来自W(5,1000,500)的7个观测也能贴近W(2,500,1000)的中部曲线。样本最小值约1167，使γ=1000仍可行；对照分布接近该组MDM估计，说明γ上移、η和β下降后仍可能拟合同一样本。黑点的累计概率由样本排序近似，反映抽样波动。',
        '图3中，来自W(5,1000,500)的7个观测也能贴近W(2,500,1000)的中部曲线。样本最小值约1167，γ=1000满足支持条件γ<t₁；对照分布接近该组MDM估计，说明γ上移、η和β下降后仍可能拟合同一样本。黑点的累计概率由样本排序近似，反映抽样波动。',
    ),
    (
        '以上说明了偏移组合为何仍可行且能拟合样本。它是否被选中，取决于各方法的梯度阈值、回归匹配、校准方程或似然。下面逐法分析这些判据为何会选择偏移组合。MDM按梯度交点定位γ；WMLE、MLE联合估计，其γ条件曲线用于分析联合准则。',
        '样本支持约束与分位补偿说明，偏移组合仍可能保持中部拟合。各方法的估计结果进一步取决于其梯度阈值、回归匹配、校准方程或似然。下面逐法分析这些判据对参数偏移的影响。MDM按梯度交点定位γ；WMLE、MLE联合估计，其γ条件曲线用于分析联合准则。',
    ),
]


def main():
    revision.main()
    record = json.loads(revision.RECORD.read_text(encoding='utf-8'))
    record['task'] = '2026-10-10: precise academic wording of sample support and fit'
    record['reused_revision_entry'] = '程序/20261010-最小值约束与同样本拟合.py'
    revision.RECORD.write_text(json.dumps(record, ensure_ascii=False, indent=2) + '\n',
                               encoding='utf-8', newline='\n')


if __name__ == '__main__':
    main()
