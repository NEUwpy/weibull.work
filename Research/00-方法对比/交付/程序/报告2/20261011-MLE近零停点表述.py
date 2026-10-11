"""将MLE第37组的停止、筛选和返回过程写清楚；apply修订，verify复核。"""
from pathlib import Path
import argparse
import hashlib
import importlib.util
import inspect
import json
import re
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from 共用 import ROOT, RESULT, write_atomic

REPORT = ROOT / '报告2：小样本情况下的明显异常估计.md'
QA = Path(__file__).with_suffix('.json')
AUDIT = RESULT / '报告2/数据/20261010-异常各情形过程核验.json'
BEFORE = ('Nelder–Mead按搜索点间的参数距离和目标值差异停止。零位置起点仅推进到约0.0001，'
          '其余四个起点在搜索结束后因β<1被剔除，程序直接接受了剩余候选。'
          '固定真位置γ=3000、重估β和η后，得到似然更高的合格候选。'
          '这说明原候选还能改善，偏差形成于搜索停止和候选接受环节。')
AFTER = ('程序从五个起点分别搜索，再从β≥1的合格返回结果中选取似然最高者。'
         '第37组从γ=0出发的搜索停在γ≈0.0001，另四个结果因β<1被剔除，最后只剩这个近零候选。\n\n'
         'γ=0起点在位置方向的初始搜索间隔仅0.00025。搜索点在近零位置聚拢，彼此的参数距离和似然差达到停止标准，'
         '优化器便报告收敛，程序随后返回了这一候选。\n\n'
         '但该点的对数似然为−50.3247；固定γ=3000、重新估计β和η，可得β≈2.17、η≈725.20，'
         '对数似然升至−49.9405。因此，这里的问题是数值搜索过早停止，而程序直接接受了这个候选。')


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def text_digest(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def module(stem):
    name = 'mle_wording_' + stem
    spec = importlib.util.spec_from_file_location(name, HERE / (stem + '.py'))
    obj = importlib.util.module_from_spec(spec)
    sys.modules[name] = obj
    spec.loader.exec_module(obj)
    return obj


def correct(text):
    assert text.count(BEFORE) + text.count(AFTER) == 1
    return text.replace(BEFORE, AFTER)


def restore(text):
    return text.replace(AFTER, BEFORE)


def approved_outside_hash(expected):
    if not QA.exists():
        return expected
    record = load(QA)
    assert expected in (record['outside_before_sha256'], record['outside_after_sha256'])
    return module('20261011-MMLE三参数流程图').approved_outside_hash(record['outside_after_sha256'])


def evidence():
    import numpy as np
    import scipy
    from scipy.optimize._optimize import _minimize_neldermead
    pair = module('20261011-MDM近真值对照')
    _, matrix, snapshot = pair.source_inputs()
    source = snapshot / 'methods/mle.py'
    audit = load(AUDIT)['cases']['MLE_stop']['solver_audit']
    assert digest(source) == audit['frozen_estimator_sha256']
    assert audit['archived_return_reproduced']
    x = np.array(next(s['values'] for s in matrix['samples'] if s['n'] == 7 and s['id'] == 37))
    starts = audit['starts']
    kept = [s for s in starts if s['accepted_shape'] and s['optimizer_success']]
    assert len(starts) == 5 and len(kept) == 1 and kept[0]['initial'][2] == 0
    assert all(s['beta'] < 1 for s in starts if not s['accepted_shape'])
    saved = next(r for r in matrix['results'] if r['n'] == 7 and r['id'] == 37 and r['method_id'] == 'mle')
    assert all(abs(kept[0][k] - saved[k + '_hat']) < 1e-8 for k in ('beta', 'eta', 'gamma'))
    def ll(beta, eta, gamma):
        z = (x - gamma) / eta
        return float(len(x) * np.log(beta) - len(x) * np.log(eta)
                     + (beta - 1) * np.log(z).sum() - (z ** beta).sum())
    original = ll(kept[0]['beta'], kept[0]['eta'], kept[0]['gamma'])
    higher = audit['higher_feasible_true_location_candidate']
    candidate = ll(higher['beta'], higher['eta'], 3000.)
    assert abs(original - kept[0]['ll']) < 1e-10
    assert abs(candidate - higher['ll']) < 1e-10 and candidate > original
    optimizer = inspect.getsource(_minimize_neldermead)
    assert 'zdelt = 0.00025' in optimizer
    assert 'np.max(np.abs(fsim[0] - fsim[1:])) <= fatol' in optimizer
    return dict(frozen_estimator_sha256=digest(source), audit_sha256=digest(AUDIT),
                sample=x.tolist(), accepted=kept[0], rejected=[s for s in starts if not s['accepted_shape']],
                higher_candidate=dict(gamma=3000., **higher), original_ll=original, higher_ll=candidate,
                scipy_version=scipy.__version__, optimizer_sha256=text_digest(optimizer),
                zero_initial_simplex_step=.00025)


def write_json(record):
    write_atomic(QA, (json.dumps(record, ensure_ascii=False, indent=2, allow_nan=False) + '\n').encode('utf-8'))


def apply():
    pair = module('20261011-MDM近真值对照')
    old = REPORT.read_text(encoding='utf-8')
    new = correct(old)
    if new == old:
        verify()
        return
    proof = evidence()
    record = dict(before_normalized_text_sha256=text_digest(old), before=BEFORE, after=AFTER,
                  outside_before_sha256=text_digest(pair.block(old)[1]),
                  outside_after_sha256=text_digest(pair.block(new)[1]),
                  protected_sha256=module('20261011-MDM回退程序归因').protected(), evidence=proof)
    pair.write_text(REPORT, new)
    write_json(record)
    previous = load(pair.QA)
    assert previous['outside_block_sha256'] == record['outside_before_sha256']
    previous.update(outside_block_sha256=record['outside_after_sha256'],
                    mle_wording_revision=dict(record=QA.name, before=record['outside_before_sha256'],
                                             after=record['outside_after_sha256']))
    pair.write_json(pair.QA, previous)
    readme = ROOT / 'README.md'
    text = readme.read_text(encoding='utf-8')
    note = ('报告2的MLE第37组按“搜索停止—候选筛选—返回结果”说明近零高估原因。'
            '[表述与核验脚本](交付/程序/报告2/20261011-MLE近零停点表述.py)支持`apply`、`verify`，'
            '核验记录保存在程序目录。')
    if note not in text:
        pair.write_text(readme, text.rstrip() + '\n\n' + note + '\n')
    verify()


def verify():
    record = load(QA)
    text = REPORT.read_text(encoding='utf-8')
    mmle = module('20261011-MMLE三参数流程图')
    if mmle.QA.exists():
        text = mmle.restore(text)
    assert correct(text) == text
    assert text_digest(restore(text)) == record['before_normalized_text_sha256']
    assert module('20261011-MDM回退程序归因').protected() == record['protected_sha256']
    assert evidence() == record['evidence']
    assert re.findall(r'\\tag\{(\d+)\}', text) == [str(i) for i in range(1, 31)]
    pair = module('20261011-MDM近真值对照')
    assert pair.tables(text) == pair.tables(restore(text))
    assert text_digest(pair.block(text)[1]) == record['outside_after_sha256']
    record.update(script_sha256=digest(__file__), after_report_sha256=digest(REPORT), validation='passed')
    write_json(record)
    print('PASS: MLE group37 stopping, rejection, return and higher likelihood verified; original outputs unchanged.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', nargs='?', default='verify', choices=['apply', 'verify'])
    globals()[parser.parse_args().action]()
