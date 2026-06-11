"""实验 1-3：参数尺度混合 / gamma 除零 / 参数视角 vs 工程分位点视角（非冗余）。
输出图片到 figs/，并打印所有数值结果。"""
import numpy as np, json, os, warnings
warnings.filterwarnings('ignore')
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
from weibull_lib import param_metrics, quantile_xR

# ---------- 字体与样式 ----------
font_manager.fontManager.addfont('/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc')
plt.rcParams.update({
    'font.sans-serif': ['Noto Sans CJK JP', 'WenQuanYi Zen Hei', 'DejaVu Sans'],
    'axes.unicode_minus': False, 'figure.dpi': 150, 'savefig.dpi': 150,
    'axes.spines.top': False, 'axes.spines.right': False,
    'axes.grid': True, 'grid.alpha': 0.25, 'grid.linewidth': 0.6,
    'font.size': 11, 'axes.titlesize': 12, 'axes.titleweight': 'bold',
    'figure.facecolor': 'white', 'axes.facecolor': 'white',
})
INK='#1a1a2e'; PRI='#2E5E8C'; GOOD='#2E8B57'; WARN='#E07A3F'; BAD='#C23B3B'; GRY='#9AA0A6'
os.makedirs('/home/claude/figs', exist_ok=True)

D = np.load('/home/claude/mc_results.npz')
meta = json.load(open('/home/claude/mc_meta.json'))
LABELS = [r'$\beta$ 形状', r'$\eta$ 尺度', r'$\gamma$ 位置']
R_LIST = [0.999, 0.995, 0.990, 0.950, 0.900, 0.500]
out = {}  # 汇总数值

def true_of(name): m=meta[name]; return np.array([m['beta'], m['eta'], m['gamma']])

# ==========================================================================
# 实验 1：为什么不能把三个参数的 MSE 直接相加
# ==========================================================================
print('='*70); print('实验 1：参数尺度/量纲混合问题'); print('='*70)
est = D['A_n50']; true = true_of('A_n50')
pm = param_metrics(est, true)
raw_mse = pm['mse']                       # [beta, eta, gamma]
naive_total = raw_mse.sum()
contrib = raw_mse / naive_total * 100
print(f'真值 beta={true[0]}, eta={true[1]}, gamma={true[2]}, n=50, N={est.shape[0]}')
for i,l in enumerate(['beta','eta ','gamma']):
    print(f'  {l}: MSE={raw_mse[i]:12.4f}  RMSE={pm["rmse"][i]:8.3f}  '
          f'RRMSE={pm["rrmse"][i]*100 if not np.isnan(pm["rrmse"][i]) else float("nan"):6.2f}%  '
          f'占朴素总MSE {contrib[i]:6.3f}%')
print(f'  朴素 total MSE = {naive_total:.2f}  -> eta 占 {contrib[1]:.3f}%')

# 单位改变不变性：把 eta,gamma 改用“千小时”(÷1000)，beta 不变
sc = np.array([1.0, 1/1000., 1/1000.])
est_k = est*sc; true_k = true*sc
pm_k = param_metrics(est_k, true_k)
raw_mse_k = pm_k['mse']; contrib_k = raw_mse_k/raw_mse_k.sum()*100
print('\n  改用“千小时”后（仅换单位，物理事实不变）：')
print(f'    朴素总MSE各参数占比 beta/eta/gamma = '
      f'{contrib_k[0]:.2f}% / {contrib_k[1]:.2f}% / {contrib_k[2]:.2f}%  <- 占比完全翻转!')
print(f'    RRMSE 不变: {pm["rrmse"][0]*100:.2f}% vs {pm_k["rrmse"][0]*100:.2f}% (beta)')

# 退化测试：分别把 beta / eta 的误差放大 3 倍，看朴素总MSE 与 平均RRMSE 的反应
def degrade(col):
    e2 = est.copy(); e2[:,col] = true[col] + 3.0*(est[:,col]-true[col]); return e2
base_rrmse = np.nanmean(pm['rrmse'])
res_deg = {}
for nm,col in [('β恶化',0),('η恶化',1)]:
    e2 = degrade(col); p2 = param_metrics(e2,true)
    res_deg[nm] = (p2['mse'].sum()/naive_total, np.nanmean(p2['rrmse'])/base_rrmse)
print('\n  把单个参数误差放大3倍后的相对变化（相对基线）：')
print(f'    {"":8s}  朴素总MSE倍数   平均RRMSE倍数')
for nm,(a,b) in res_deg.items():
    print(f'    {nm:8s}  {a:8.2f}x        {b:8.2f}x')
print('  -> β 恶化3倍, 朴素总MSE 几乎不动(被 η 淹没); 平均RRMSE 如实反映')
out['exp1'] = dict(raw_mse=raw_mse.tolist(), contrib=contrib.tolist(),
                   rrmse_pct=(pm['rrmse']*100).tolist(),
                   contrib_kilo=contrib_k.tolist(),
                   degrade={k:list(v) for k,v in res_deg.items()})

# ---- 图1 ----
fig, axes = plt.subplots(1, 2, figsize=(10.2, 4.0))
x = np.arange(3); cols=[PRI, BAD, WARN]
ax=axes[0]
bars=ax.bar(x, raw_mse, color=cols, width=0.62, edgecolor='white')
ax.set_yscale('log'); ax.set_ylabel('原始 MSE（对数轴）')
ax.set_title('(a) 原始 MSE 量纲悬殊 → 不可直接相加')
ax.set_xticks(x); ax.set_xticklabels(LABELS)
for i,b in enumerate(bars):
    ax.text(b.get_x()+b.get_width()/2, b.get_height()*1.25,
            f'占总和\n{contrib[i]:.2f}%', ha='center', va='bottom', fontsize=9.5,
            color=cols[i], fontweight='bold')
ax.set_ylim(raw_mse.min()*0.25, raw_mse.max()*6)
ax.text(0.02,0.62,'β 仅占总和 0.001%\n→ 形状误差被完全淹没',
        transform=ax.transAxes, va='top', fontsize=9, color=INK,
        bbox=dict(boxstyle='round,pad=0.4', fc='#FFF3E0', ec=WARN, lw=0.8))

ax=axes[1]
rr = pm['rrmse']*100
bars=ax.bar(x, rr, color=cols, width=0.62, edgecolor='white')
ax.set_ylabel('RRMSE = RMSE / 真值 (%)')
ax.set_title('(b) 相对化(RRMSE)后量级可比、可公平比较')
ax.set_xticks(x); ax.set_xticklabels(LABELS)
for i,b in enumerate(bars):
    ax.text(b.get_x()+b.get_width()/2, b.get_height()+0.6,
            f'{rr[i]:.1f}%', ha='center', va='bottom', fontsize=10, fontweight='bold', color=cols[i])
ax.set_ylim(0, rr.max()*1.25)
fig.suptitle('实验1  参数尺度混合：原始 MSE 不可加，须用无量纲 RRMSE（β、η）',
             fontsize=12.5, fontweight='bold', y=1.02)
fig.tight_layout(); fig.savefig('/home/claude/figs/fig1_scale.png', bbox_inches='tight'); plt.close(fig)
print('  saved figs/fig1_scale.png')

# ==========================================================================
# 实验 2：gamma 可能为 0 → 相对误差除零/不稳定
# ==========================================================================
print('\n'+'='*70); print('实验 2：gamma 除零与相对误差不稳定'); print('='*70)
estB = D['B_n50']; trueB = true_of('B_n50')      # gamma=0
estA = D['A_n50']; trueA = true_of('A_n50')      # gamma=100
g_hatB = estB[:,2]; g_hatA = estA[:,2]
rmse_gB = np.sqrt(((g_hatB-0.0)**2).mean()); rmse_gA = np.sqrt(((g_hatA-100.0)**2).mean())
n_pos = int((g_hatB>1e-9).sum()); n_zero = int((g_hatB<=1e-9).sum())
print(f'  [gamma=0] 共 {len(g_hatB)} 次: gamma_hat>0 有 {n_pos} 次, =0 有 {n_zero} 次')
print(f'           相对误差 (gamma_hat-0)/0: {n_pos} 次为 ±inf, {n_zero} 次为 0/0=nan -> 全部无意义')
print(f'           绝对 RMSE_gamma = {rmse_gB:.2f} h (有限、可用)')
print(f'           η归一 RMSE_gamma/η = {rmse_gB/1000:.4f} (有限、可用)')
relA = (g_hatA-100.0)/100.0*100      # gamma=100 时的相对误差(%)
print(f'  [gamma=100] 相对误差分位 5/50/95: {np.percentile(relA,[5,50,95]).round(1)} %')
print(f'             在 -100% 处堆积比例(gamma_hat≈0): {(g_hatA<1.0).mean()*100:.1f}%; 右尾最大 {relA.max():.0f}%')
print(f'             绝对 RMSE_gamma={rmse_gA:.2f}h, η归一 RMSE/η={rmse_gA/1000:.4f}')
out['exp2'] = dict(rmse_gamma_g0=rmse_gB, norm_g0=rmse_gB/1000,
                   rmse_gamma_g100=rmse_gA, rel_g100_pct=np.percentile(relA,[5,50,95]).tolist())

fig, axes = plt.subplots(1, 2, figsize=(10.2, 4.0))
# (a) gamma=100: 相对误差直方图（不稳定）
ax=axes[0]
clip = np.clip(relA, -120, 320)
ax.hist(clip, bins=45, color=PRI, alpha=0.85, edgecolor='white')
ax.axvline(0, color=GRY, lw=1, ls='--')
ax.axvline(-100, color=BAD, lw=1.4, ls='-')
ax.set_xlabel(r'$\gamma$ 相对误差 $(\hat\gamma-\gamma)/\gamma$  (%)')
ax.set_ylabel('频数'); ax.set_title(r'(a) $\gamma=100$：相对误差极不稳定')
ax.text(-100, ax.get_ylim()[1]*0.92, r' $\hat\gamma\!\to\!0$ 处'+'\n -100%硬墙', color=BAD, fontsize=9, va='top')
ax.text(0.97,0.96, '长右尾 + 左侧-100%堆积\n相对误差不可靠', transform=ax.transAxes,
        ha='right', va='top', fontsize=9, color=INK,
        bbox=dict(boxstyle='round,pad=0.4', fc='#E8EEF5', ec=PRI, lw=0.8))
# (b) gamma=0: 绝对分布 + 相对误差未定义
ax=axes[1]
ax.hist(g_hatB, bins=40, color=GOOD, alpha=0.85, edgecolor='white')
ax.axvline(0, color=BAD, lw=1.6)
ax.set_xlabel(r'$\hat\gamma$（绝对值, 小时）；真值 $\gamma=0$')
ax.set_ylabel('频数'); ax.set_title(r'(b) $\gamma=0$：相对误差 = 除零，未定义')
ax.text(0.97,0.96,
        r'真值 $\gamma=0$ → $(\hat\gamma-0)/0=\infty$'+'\n相对误差/RRMSE 失效\n'
        +f'绝对 RMSE={rmse_gB:.0f}h (可用)\n'+f'η归一 ={rmse_gB/1000:.3f} (可用)',
        transform=ax.transAxes, ha='right', va='top', fontsize=9, color=INK,
        bbox=dict(boxstyle='round,pad=0.4', fc='#E9F3EE', ec=GOOD, lw=0.8))
fig.suptitle(r'实验2  位置参数 $\gamma$：相对误差会除零/爆炸，须改用绝对或 η 归一误差',
             fontsize=12.5, fontweight='bold', y=1.02)
fig.tight_layout(); fig.savefig('/home/claude/figs/fig2_gamma.png', bbox_inches='tight'); plt.close(fig)
print('  saved figs/fig2_gamma.png')

# ==========================================================================
# 实验 3：参数视角 ≠ 工程分位点视角
#   (a) 同样 +10% 的参数误差，对 x_R 的影响随 R 不同 → x_R 按后果加权
#   (b) 相同的逐参数 RMSE，但误差相关结构不同 → x_R 的 RMSE 不同（非冗余）
# ==========================================================================
print('\n'+'='*70); print('实验 3：参数视角与工程分位点视角的非冗余性'); print('='*70)
bt,et,gt = 2.5,1000.0,100.0
Rs = np.array([0.999,0.995,0.99,0.95,0.90,0.70,0.50])
def xR(b,e,g,R): return g + e*(-np.log(R))**(1.0/b)
base = xR(bt,et,gt,Rs)
pert = {
    r'$\beta$ +10%': (xR(bt*1.1,et,gt,Rs)-base)/base*100,
    r'$\eta$ +10%':  (xR(bt,et*1.1,gt,Rs)-base)/base*100,
    r'$\gamma$ +10%':(xR(bt,et,gt*1.1,Rs)-base)/base*100,
}
print('  +10% 单参数扰动引起的 x_R 相对变化 (%)：')
print('   R     ' + '  '.join(f'{r:6.3f}' for r in Rs))
for k,v in pert.items():
    print(f'   {k:12s} ' + '  '.join(f'{x:6.2f}' for x in v))
print('  -> η误差在低R(寿命中段)影响大; γ误差在高R(近阈值早期)影响大; β误差在深尾显著')

# (b) 相同边际 RMSE、不同相关性
rng = np.random.default_rng(7)
M = 60000
s_b, s_e = 0.45, 130.0     # 与实测量级相近的 beta/eta 误差标准差
R_eval = 0.99
a_eta = (-np.log(R_eval))**(1/bt)                      # ∂x/∂eta
a_beta = et*(-np.log(R_eval))**(1/bt)*np.log(-np.log(R_eval))*(-1/bt**2)  # ∂x/∂beta
print(f'\n  R={R_eval}: ∂x/∂β={a_beta:.2f}, ∂x/∂η={a_eta:.4f} (同号→正相关更糟)')
res_corr = {}
for tag,rho in [('正相关 ρ=+0.8', +0.8), ('零相关 ρ=0', 0.0), ('负相关 ρ=-0.8', -0.8)]:
    cov = np.array([[s_b**2, rho*s_b*s_e],[rho*s_b*s_e, s_e**2]])
    d = rng.multivariate_normal([0,0], cov, size=M)
    b_hat = bt + d[:,0]; e_hat = et + d[:,1]
    b_hat = np.clip(b_hat, 0.2, None)                   # 保持形状为正
    rmse_b = np.sqrt((( b_hat-bt)**2).mean()); rmse_e = np.sqrt(((e_hat-et)**2).mean())
    x_hat = xR(b_hat, e_hat, gt, R_eval); x_t = xR(bt,et,gt,R_eval)
    rmse_x = np.sqrt(((x_hat-x_t)**2).mean())
    res_corr[tag] = (rmse_b, rmse_e, rmse_x)
print('  相同边际σ下三种相关性（逐参数RMSE几乎相同, x_R RMSE 不同）：')
print(f'   {"场景":14s}  RMSE_β   RMSE_η    x_R的RMSE(R=0.99)')
for k,(rb,re,rx) in res_corr.items():
    print(f'   {k:14s}  {rb:5.3f}   {re:6.1f}    {rx:8.1f}')
out['exp3'] = dict(pert={k:v.tolist() for k,v in pert.items()}, Rs=Rs.tolist(),
                   corr={k:list(v) for k,v in res_corr.items()})

fig, axes = plt.subplots(1, 2, figsize=(11.0, 4.1))
ax=axes[0]
pcols={r'$\beta$ +10%':BAD, r'$\eta$ +10%':PRI, r'$\gamma$ +10%':GOOD}
xax = (1-Rs)*100   # 失效概率%
for k,v in pert.items():
    ax.plot(xax, v, 'o-', color=pcols[k], lw=2, ms=5, label=k)
ax.set_xscale('log')
ax.set_xlabel('失效概率 1−R (%, 对数轴)  ← 高可靠度(尾部)在左')
ax.set_ylabel(r'$x_R$ 相对变化 (%)')
ax.set_title('(a) 同为+10%参数误差，对 $x_R$ 影响随 R 而异')
ax.axhline(10, color=GRY, ls=':', lw=1); ax.legend(fontsize=9.5, framealpha=0.9, loc='lower left')

ax=axes[1]
tags=list(res_corr.keys())
rmse_b=[res_corr[t][0] for t in tags]; rmse_e=[res_corr[t][1] for t in tags]
rmse_x=[res_corr[t][2] for t in tags]
xx=np.arange(len(tags)); w=0.26
ax.bar(xx-w, np.array(rmse_b)/rmse_b[0], w, color=PRI, label=r'RMSE$_\beta$ (归一)')
ax.bar(xx,    np.array(rmse_e)/rmse_e[0], w, color=WARN, label=r'RMSE$_\eta$ (归一)')
ax.bar(xx+w, np.array(rmse_x)/rmse_x[1], w, color=BAD, label=r'$x_R$ RMSE (归一)')
ax.set_xticks(xx); ax.set_xticklabels(tags, fontsize=9)
ax.set_ylabel('归一化 RMSE（同色相互比较）')
ax.set_title('(b) 逐参数RMSE相同 → $x_R$ 精度却不同')
ax.legend(fontsize=8.8, framealpha=0.9, loc='upper right', ncol=1)
for i,t in enumerate(tags):
    ax.text(i+w, rmse_x[i]/rmse_x[1]+0.02, f'{rmse_x[i]:.0f}h', ha='center',
            va='bottom', fontsize=8.5, color=BAD, fontweight='bold')
ax.text(0.5,0.02,'逐参数视角无法区分这三种估计器，工程分位点视角能',
        transform=ax.transAxes, ha='center', va='bottom', fontsize=8.6, color=INK,
        bbox=dict(boxstyle='round,pad=0.35', fc='#FBEAEA', ec=BAD, lw=0.8))
fig.suptitle('实验3  参数视角与分位点视角并非冗余：二者评价不同的东西',
             fontsize=12.5, fontweight='bold', y=1.02)
fig.tight_layout(); fig.savefig('/home/claude/figs/fig3_views.png', bbox_inches='tight'); plt.close(fig)
print('  saved figs/fig3_views.png')

json.dump(out, open('/home/claude/results_123.json','w'), indent=2, default=float)
print('\nsaved results_123.json')
