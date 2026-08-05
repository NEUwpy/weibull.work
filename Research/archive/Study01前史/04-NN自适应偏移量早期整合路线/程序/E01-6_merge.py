"""
E01-6 合并脚本：跑完所有单n后，合并为最终CSV/summary。

用法：
  先逐个运行：
    python E01-6_single_n.py 5 2000
    python E01-6_single_n.py 7 2000
    ...
    python E01-6_single_n.py 50 2000
  然后合并：
    python E01-6_merge.py
"""
import csv, os, json

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUT_DATA = os.path.join(SCRIPT_DIR, '..', '实验数据')

N_LIST = [5, 7, 10, 15, 20, 50]
METHODS = ['mdm', 'mle', 'lse']
HEADER_RAW = ['n', 'rep', 'method', 'beta_hat', 'eta_hat', 'gamma_hat',
              'converged', 'sample_min', 'gamma_zero', 'gamma_near_zero']


def main():
    # --- 合并逐次数据 ---
    all_rows = []
    for n in N_LIST:
        path = os.path.join(OUT_DATA, f'E01-6_n{n}.csv')
        if not os.path.exists(path):
            print(f"MISSING: E01-6_n{n}.csv — 请先运行: python E01-6_single_n.py {n} 2000")
            return
        with open(path, 'r', encoding='utf-8') as f:
            for row in csv.DictReader(f):
                all_rows.append(row)

    merged_path = os.path.join(OUT_DATA, 'E01-6_mc_results.csv')
    with open(merged_path, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=HEADER_RAW)
        w.writeheader()
        w.writerows(all_rows)

    # --- 行数一致性检查 ---
    print("Row count check:")
    ok = True
    for n in N_LIST:
        for m in METHODS:
            cnt = sum(1 for r in all_rows if r['n'] == str(n) and r['method'] == m)
            if cnt != 2000:
                print(f"  n={n} {m}: {cnt} — MISMATCH")
                ok = False
    if ok:
        print("  All 18 cells = 2000 ✓")

    # --- 合并 summary ---
    summary_rows = []
    for n in N_LIST:
        jpath = os.path.join(OUT_DATA, f'E01-6_summary_n{n}.json')
        if not os.path.exists(jpath):
            print(f"MISSING: E01-6_summary_n{n}.json")
            return
        with open(jpath, 'r') as f:
            data = json.load(f)
        for m in METHODS:
            summary_rows.append(data[m])

    sum_path = os.path.join(OUT_DATA, 'E01-6_metrics_summary.csv')
    with open(sum_path, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=list(summary_rows[0].keys()))
        w.writeheader()
        w.writerows(summary_rows)

    # --- 清理中间文件 ---
    for n in N_LIST:
        for ext in [f'E01-6_n{n}.csv', f'E01-6_summary_n{n}.json']:
            p = os.path.join(OUT_DATA, ext)
            if os.path.exists(p):
                os.remove(p)

    # --- 打印汇总 ---
    print(f"\n{'n':>3} {'method':>4} {'valid':>6} {'fail%':>6} {'RMSE_β':>7} {'RMSE_x95':>9} {'gz%':>5} {'gnz%':>5}")
    print("-" * 55)
    for r in summary_rows:
        n, m = r['n'], r['method']
        nv = r['n_valid']
        fr = r['failure_rate']
        rb = r.get('rmse_beta') or 0
        rx = r.get('rmse_x95') or 0
        gz = r['gamma_zero_rate']
        gnz = r['gamma_near_zero_rate']
        print(f"{n:3d} {m:>4s} {nv:6d} {fr:6.1%} {rb:7.3f} {rx:9.1f} {gz:5.1%} {gnz:5.1%}")

    print(f"\nTotal: {len(all_rows)} rows")
    print(f"Merged raw: {merged_path}")
    print(f"Summary: {sum_path}")
    print("Intermediate files cleaned.")


if __name__ == '__main__':
    main()
