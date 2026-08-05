"""
Study/01 E6b — 正式产物 manifest 封存收口（post-hoc provenance 修订）

复核后收口（REVISE 第 4 点 + 第 2 轮第 4 点）：
  - 将 manifest 的留出划分改为准确描述：按 n 的 γ/η 水平留出
    （对每个 n，每折留出一个完整 γ/η 水平，测试集覆盖全部 8 个 β；
    未检验未见 β）。
  - 补充 provenance 块：实现提交 d9ea4a35、产物提交 7eda7b32、
    封存准备提交 seal_preparation_commit=54470f67（包含 finalize 脚本与
    文档，不含最终 manifest/SHA256SUMS）、运行期 HEAD（1c8b47f9）、
    LF-normalized 哈希口径。
  - 最终封存包所在提交（包含本 manifest 与 SHA256SUMS 的提交）不写入
    manifest 自身（manifest 被纳入自身哈希会形成自引用），而记录在执行
    报告 / 状态文档中。
  - Normalized-RAW 候选对照绑定来源分支/提交（4233856c）及其汇总文件哈希。
  - 重建 SHA256SUMS（仅不可变科学产物，LF-normalized 口径）。

不改训练代码（run_E6b 保持 d9ea4a35 原样，折模型 code_sha256 与其一致，
无需重训）；只补 manifest 与封存清单。运行后需提交。

用法：python finalize_e6_manifest.py
"""

import sys
import os
import json
import hashlib
import subprocess

STUDY_CODE_DIR = os.path.dirname(os.path.abspath(__file__))
STUDY_ROOT = os.path.dirname(STUDY_CODE_DIR)
PROJECT_ROOT = os.path.dirname(os.path.dirname(STUDY_ROOT))
sys.path.insert(0, STUDY_CODE_DIR)

import dim_raw_config as CFG
import run_E6b_dimensional_raw_specialist as E6

IMPLEMENTATION_COMMIT = "d9ea4a35"
ARTIFACT_COMMIT = "7eda7b32"
# 封存准备提交：包含 finalize 脚本与文档，不含最终 manifest/SHA256SUMS。
# 最终封存包所在提交记录在执行报告/状态文档（不写入 manifest 以避免自引用）。
SEAL_PREPARATION_COMMIT = "54470f67"
NORMALIZED_RAW_BRANCH = "study01-normalized-raw-specialist"
NORMALIZED_RAW_COMMIT = "4233856c"
NORMALIZED_RAW_SUMMARY_SHA = "83aa3604cf840665816d36862b866e5b3137366cf0f10d3c58a639042c94f640"
NORMALIZED_RAW_COMPARISON_SHA = "87bbe58cbe196a653e049053a126da42d621fe747bb1e7d55a596e714a4b041a"

ACCURATE_SPLIT_DESC = (
    "per-n gamma/eta-level holdout: for each n, each fold holds out one complete "
    "gamma/eta level (test covers all 8 betas; train contains all betas under the "
    "other gamma/eta levels). Does NOT test unseen betas."
)


def sha256_file_lf(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        prev = b''
        while True:
            block = f.read(1 << 20)
            if not block:
                break
            data = prev + block
            data = data.replace(b'\r\n', b'\n')
            prev = data[-1:] if data.endswith(b'\r') else b''
            h.update(data[:-1] if prev else data)
        if prev:
            h.update(prev)
    return h.hexdigest()


def git_short(ref):
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", ref],
            cwd=PROJECT_ROOT, stderr=subprocess.DEVNULL).decode().strip()
    except Exception:
        return ref


def main():
    mpath = os.path.join(CFG.SPECIALIST_DIR, 'manifest.json')
    with open(mpath, encoding='utf-8') as f:
        manifest = json.load(f)

    # 1) accurate split description
    manifest['split_contract']['folds'] = ACCURATE_SPLIT_DESC
    manifest['split_contract']['note'] = (
        "The combo enumeration order makes this a per-n gamma/eta-level holdout, "
        "not a general arbitrary-combo holdout; unseen-beta generalization is not "
        "evaluated by this split."
    )

    # 2) provenance block
    manifest['provenance'] = {
        'implementation_code_commit': IMPLEMENTATION_COMMIT,
        'artifact_commit': ARTIFACT_COMMIT,
        'seal_preparation_commit': SEAL_PREPARATION_COMMIT,
        'provenance_parent_commit': SEAL_PREPARATION_COMMIT,
        'runtime_head_commit': manifest.get('git_commit', ''),
        'runtime_workspace_dirty': manifest.get('workspace_dirty', None),
        'hash_basis': 'LF-normalized bytes (CRLF->LF normalized before hashing; '
                      'fingerprints independent of checkout line endings)',
        'hash_note': ('data_sha256sums.txt/SHA256SUMS fingerprints are computed '
                      'over LF-normalized bytes; they match across checkouts but '
                      'are NOT byte-identical to the current Windows files. '
                      'The commit containing this manifest and SHA256SUMS itself '
                      'is recorded in the execution report / status doc, not here, '
                      'to avoid self-reference.'),
        'no_retrain': ('Fold-model code_sha256 matches the committed implementation '
                       'commit d9ea4a35; manifest provenance is post-hoc, models '
                       'were not retrained.'),
        'normalized_raw_control': {
            'role': 'candidate control, not main evidence',
            'branch': NORMALIZED_RAW_BRANCH,
            'commit': NORMALIZED_RAW_COMMIT,
            'results_file': 'artifacts/formal/E5_normalized_raw/specialist/'
                            'raw_specialist_results.csv',
            'summary_file': 'artifacts/formal/E5_normalized_raw/specialist/summary.json',
            'summary_sha256_lf': NORMALIZED_RAW_SUMMARY_SHA,
            'model_comparison_sha256_lf': NORMALIZED_RAW_COMPARISON_SHA,
        },
    }

    with open(mpath, 'w', encoding='utf-8', newline='\n') as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False, default=str)

    # 3) rebuild seal (immutable artifacts only, LF-normalized)
    E6.lf_normalize_tree(CFG.SPECIALIST_DIR)
    n = E6.write_sha256sums(CFG.SPECIALIST_DIR, PROJECT_ROOT)
    print(f"Manifest updated (split description + provenance), "
          f"seal_preparation_commit={SEAL_PREPARATION_COMMIT}")
    print(f"SHA256SUMS rebuilt: {n} entries (immutable artifacts only, "
          f"LF-normalized)")


if __name__ == "__main__":
    main()
