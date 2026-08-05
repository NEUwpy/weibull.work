"""主蒙特卡洛运行器：生成估计结果并缓存。"""
import numpy as np, time, warnings, json
warnings.filterwarnings('ignore')
from scipy import stats
from weibull_lib import fit_weibull3

def run_config(beta, eta, gamma, n, N, seed):
    rng = np.random.default_rng(seed)
    est = np.empty((N, 3))
    for i in range(N):
        x = stats.weibull_min.rvs(beta, loc=gamma, scale=eta, size=n, random_state=rng)
        est[i] = fit_weibull3(x, ngrid=60)
    return est

if __name__ == '__main__':
    N = 2500
    results = {}
    jobs = [
        # name, beta, eta, gamma, n, seed
        ('A_n20',  2.5, 1000.0, 100.0, 20,  101),
        ('A_n50',  2.5, 1000.0, 100.0, 50,  102),
        ('A_n100', 2.5, 1000.0, 100.0, 100, 103),
        ('B_n50',  2.5, 1000.0,   0.0, 50,  202),  # gamma=0 退化件
    ]
    meta = {}
    for name, b, e, g, n, sd in jobs:
        t0 = time.time()
        est = run_config(b, e, g, n, N, sd)
        results[name] = est
        meta[name] = dict(beta=b, eta=e, gamma=g, n=n, N=N)
        print(f'{name}: n={n} N={N} done in {time.time()-t0:.1f}s | '
              f'beta_hat~{est[:,0].mean():.2f} eta_hat~{est[:,1].mean():.0f} '
              f'gamma_hat~{est[:,2].mean():.0f}')
    np.savez('/home/claude/mc_results.npz', **results)
    with open('/home/claude/mc_meta.json', 'w') as f:
        json.dump(meta, f, indent=2)
    print('saved mc_results.npz and mc_meta.json')
