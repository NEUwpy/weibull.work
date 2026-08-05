"""实验 4-6：
  4 工程分位点 x_R 的误差度量比较：MAE vs RMSE(+比值) 及 MAPE 的两个病态
  5 偏差方向的工程安全含义：RMSE 看不出方向，relative bias 能
  6 损失函数恰当性(propriety)：NLL/pinball 在真值最优；中位数匹配无法定尾部
"""
import numpy as np, json, os, warnings
warnings.filterwarnings('ignore')
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
from weibull_lib import quantile_metrics, quantile_xR, param_metrics

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
D = np.load('/home/claude/mc_results.npz'); meta = json.load(open('/home/claude/mc_meta.json'))
out = {}

# ==========================================================================
# 实验 4：x_R 误差度量比较
# ==========================================================================
print('='*70); print('实验 4：分位点 x_R 误差度量 MAE / RMSE / MAPE'); print('='*70)
estA = D['A_n50']; trueA = (2.5,1000.0,100.0)
Rs = [0.999,0.990,0.950,0.900,0.500]
qm = quantile_metrics(estA, trueA, Rs)
print(f'  真值 {trueA}, n=50')
print(f'   R      x_true    MAE     RMSE   RMSE/MAE   MAPE%   relbias%')
for R in Rs:
    d=qm[R]
    print(f'   {R:5.3f}  {d["x_true"]:7.1f}  {d["mae"]:6.1f}  {d["rmse"]:6.1f}   '
          f'{d["rmse_over_mae"]:5.3f}   {d["mape"]:6.1f}  {d["rel_bias"]*100:7.2f}')
out['exp4_metrics'] = {str(R): {k: float(qm[R][k]) for k in
                       ['x_true','mae','rmse','rmse_over_mae','mape','smape','rel_bias']} for R in Rs}

# MAPE 不对称：对真值的 ×2 (高估100%) vs ×0.5 (低估50%)，同为“2倍”严重度
over_mape = 100.0       # |2x-x|/x
under_mape = 50.0       # |0.5x-x|/x
# 从 MC 验证：高估子集与低估子集的 MAPE
R0=0.99; err=qm[0.99]['err']; xh=qm[0.99]['x_hat']; xt=qm[0.99]['x_true']
ape = np.abs(err)/xt*100
mape_over = ape[xh>xt].mean(); mape_under = ape[xh<xt].mean()
print(f'\n  MAPE 不对称: 同为“2倍偏离”, 高估×2 → MAPE={over_mape:.0f}%, 低估×0.5 → MAPE={under_mape:.0f}%')
print(f'    (MC, R=0.99) 高估子集均值APE={mape_over:.1f}% vs 低估子集={mape_under:.1f}%')

# MAPE 近零爆炸：gamma=0 在高 R 时 x_true 很小
estB = D['B_n50']; trueB=(2.5,1000.0,0.0)
Rs_hi=[0.5,0.9,0.99,0.999,0.9999]
mape_g0=[]; mape_g100=[]; rmse_g0_norm=[]
for R in Rs_hi:
    dB = quantile_metrics(estB, trueB, [R])[R]
    dA2= quantile_metrics(estA, trueA, [R])[R]
    mape_g0.append(dB['mape']); mape_g100.append(dA2['mape'])
print(f'\n  MAPE 近零爆炸 (gamma=0 vs gamma=100):')
print(f'   R       x_true(γ=0)  MAPE(γ=0)%   MAPE(γ=100)%')
for i,R in enumerate(Rs_hi):
    xt0=quantile_xR(2.5,1000,0,R)
    print(f'   {R:6.4f}  {xt0:9.2f}   {mape_g0[i]:9.1f}    {mape_g100[i]:9.1f}')
out['exp4_mape'] = dict(over=over_mape, under=under_mape, mape_over_mc=float(mape_over),
                        mape_under_mc=float(mape_under),
                        Rs_hi=Rs_hi, mape_g0=[float(x) for x in mape_g0],
                        mape_g100=[float(x) for x in mape_g100])

fig, axes = plt.subplots(1, 3, figsize=(13.2, 4.0))
# (a) MAE vs RMSE + 比值
ax=axes[0]
labels=[f'{R}' for R in Rs]; xx=np.arange(len(Rs)); w=0.38
mae=[qm[R]['mae'] for R in Rs]; rmse=[qm[R]['rmse'] for R in Rs]; ratio=[qm[R]['rmse_over_mae'] for R in Rs]
ax.bar(xx-w/2, mae, w, color=PRI, label='MAE')
ax.bar(xx+w/2, rmse, w, color=BAD, label='RMSE')
ax.set_xticks(xx); ax.set_xticklabels(labels); ax.set_xlabel('可靠度 R')
ax.set_ylabel('$x_R$ 误差 (小时)'); ax.legend(fontsize=9.5, loc='upper right')
ax.set_title('(a) RMSE≥MAE；尾部比值更大')
ax2=ax.twinx(); ax2.plot(xx, ratio, 'o--', color=GOOD, lw=1.8, ms=6)
ax2.set_ylabel('RMSE/MAE 比值', color=GOOD); ax2.tick_params(axis='y', colors=GOOD)
ax2.grid(False); ax2.set_ylim(1.0, max(ratio)*1.15)
for i,r in enumerate(ratio):
    ax2.text(xx[i], r+0.01, f'{r:.2f}', ha='center', va='bottom', fontsize=8.5, color=GOOD)
ax.text(0.5,0.82,'比值越大→越多“偶发大误差”\nRMSE 对尾部/安全更敏感', transform=ax.transAxes,
        ha='center', va='top', fontsize=8.4, color=INK,
        bbox=dict(boxstyle='round,pad=0.3', fc='#EAF2EA', ec=GOOD, lw=0.7))
# (b) MAPE 不对称
ax=axes[1]
ax.bar([0,1], [under_mape, over_mape], color=[GOOD,BAD], width=0.55, edgecolor='white')
ax.set_xticks([0,1]); ax.set_xticklabels(['低估 ×0.5\n(寿命偏小)','高估 ×2\n(寿命偏大,危险)'])
ax.set_ylabel('MAPE (%)'); ax.set_title('(b) MAPE 对高/低估不对称')
for i,v in enumerate([under_mape,over_mape]):
    ax.text(i, v+2, f'{v:.0f}%', ha='center', va='bottom', fontsize=11, fontweight='bold',
            color=[GOOD,BAD][i])
ax.set_ylim(0,120)
ax.text(0.04,0.97,'同为“2倍偏离”，惩罚却差一倍\n→ 不对称是副作用,非设计', transform=ax.transAxes,
        ha='left', va='top', fontsize=8.4, color=INK,
        bbox=dict(boxstyle='round,pad=0.3', fc='#FBEAEA', ec=BAD, lw=0.7))
# (c) MAPE 近零爆炸
ax=axes[2]
xfp=[(1-R)*100 for R in Rs_hi]
ax.plot(xfp, mape_g0, 'o-', color=BAD, lw=2, ms=6, label='γ=0 (x_R→0)')
ax.plot(xfp, mape_g100, 's-', color=PRI, lw=2, ms=6, label='γ=100')
ax.set_xscale('log'); ax.set_yscale('log')
ax.set_xlabel('失效概率 1−R (%, 对数)'); ax.set_ylabel('MAPE (%, 对数)')
ax.set_title('(c) 高R时 x_R→0，MAPE 爆炸')
ax.legend(fontsize=9.2, loc='upper right')
ax.text(0.03,0.05,'γ=0 时高可靠度分位点趋近0\nMAPE 失控；绝对RMSE仍可用', transform=ax.transAxes,
        fontsize=8.4, color=INK, bbox=dict(boxstyle='round,pad=0.3', fc='#FBEAEA', ec=BAD, lw=0.7))
fig.suptitle('实验4  分位点误差度量：首选 RMSE(尾部敏感)；MAPE 不对称且近零失控',
             fontsize=12.5, fontweight='bold', y=1.03)
fig.tight_layout(); fig.savefig('/home/claude/figs/fig4_metrics.png', bbox_inches='tight'); plt.close(fig)
print('  saved figs/fig4_metrics.png')

# ==========================================================================
# 实验 5：偏差方向的工程安全含义
# ==========================================================================
print('\n'+'='*70); print('实验 5：偏差方向（系统高估寿命=危险）'); print('='*70)
R0=0.99
relerr={}; bias_vs_n={0.99:[],0.90:[]}; rrmse_vs_n=[]
ns=[20,50,100]; names={20:'A_n20',50:'A_n50',100:'A_n100'}
for n in ns:
    e=D[names[n]]
    for R in [0.99,0.90]:
        d=quantile_metrics(e,trueA,[R])[R]
        bias_vs_n[R].append(d['rel_bias']*100)
    rrmse_vs_n.append(quantile_metrics(e,trueA,[0.99])[0.99]['rrmse']*100)
dd=quantile_metrics(D['A_n50'],trueA,[R0])[R0]
sgn=(dd['x_hat']-dd['x_true'])/dd['x_true']*100
p_over=(dd['x_hat']>dd['x_true']).mean()*100
print(f'  R=0.99, n=50: relative bias={dd["rel_bias"]*100:.2f}%, P(高估寿命)={p_over:.1f}%')
print(f'  RRMSE(R=0.99) vs n: ' + ', '.join(f'n={n}:{v:.1f}%' for n,v in zip(ns,rrmse_vs_n)))
print(f'  relative bias(R=0.99) vs n: ' + ', '.join(f'n={n}:{v:.2f}%' for n,v in zip(ns,bias_vs_n[0.99])))
out['exp5']=dict(rel_bias_n50=float(dd['rel_bias']*100), p_over=float(p_over),
                 rrmse_vs_n=[float(x) for x in rrmse_vs_n],
                 bias99=[float(x) for x in bias_vs_n[0.99]],
                 bias90=[float(x) for x in bias_vs_n[0.90]])

fig, axes = plt.subplots(1, 2, figsize=(10.8, 4.0))
ax=axes[0]
clip=np.clip(sgn,-60,90)
ax.hist(clip,bins=45,color=PRI,alpha=0.55,edgecolor='white')
ax.axvline(0,color=GRY,lw=1.2,ls='--')
mb=dd['rel_bias']*100
ax.axvline(mb,color=BAD,lw=2)
yl=ax.get_ylim()
ax.axvspan(0,90,color=BAD,alpha=0.07)
ax.text(mb,yl[1]*0.98,f' 均值={mb:.1f}%\n (relative bias)',color=BAD,fontsize=9,va='top')
ax.text(0.97,0.55,f'高估寿命区\nP={p_over:.0f}% 的样本\n落在此(偏乐观→危险)',transform=ax.transAxes,
        ha='right',va='top',fontsize=8.6,color=BAD,
        bbox=dict(boxstyle='round,pad=0.35',fc='#FBEAEA',ec=BAD,lw=0.8))
ax.set_xlabel(r'$x_R$ 带符号相对误差 $(\hat x_R-x_R)/x_R$ (%)')
ax.set_ylabel('频数'); ax.set_title('(a) R=0.99：误差有方向，RMSE 抹掉了它')
ax=axes[1]
ax.plot(ns,bias_vs_n[0.99],'o-',color=BAD,lw=2,ms=7,label='relative bias R=0.99')
ax.plot(ns,bias_vs_n[0.90],'s-',color=WARN,lw=2,ms=7,label='relative bias R=0.90')
ax.axhline(0,color=GRY,lw=1,ls='--')
ax.plot(ns,rrmse_vs_n,'^--',color=PRI,lw=1.8,ms=7,label='RRMSE R=0.99 (仅幅度)')
ax.set_xlabel('样本量 n'); ax.set_ylabel('百分比 (%)'); ax.set_xticks(ns)
ax.set_title('(b) bias 给方向，RRMSE 只给幅度')
ax.legend(fontsize=9, loc='upper right')
ax.text(0.03,0.04,'随 n↑ 偏差趋零(一致)\nbias符号告诉你偏乐观还是保守',transform=ax.transAxes,
        fontsize=8.4,color=INK,bbox=dict(boxstyle='round,pad=0.3',fc='#F4F4F8',ec=GRY,lw=0.7))
fig.suptitle('实验5  偏差方向：工程上高估寿命=危险，须用 relative bias 辅助 RMSE',
             fontsize=12.5, fontweight='bold', y=1.03)
fig.tight_layout(); fig.savefig('/home/claude/figs/fig5_bias.png', bbox_inches='tight'); plt.close(fig)
print('  saved figs/fig5_bias.png')

# ==========================================================================
# 实验 6：损失函数恰当性
# ==========================================================================
print('\n'+'='*70); print('实验 6：损失函数 propriety 与定向'); print('='*70)
rng=np.random.default_rng(2024)
from scipy import stats
bt,et,gt=2.5,1000.0,100.0
M=300000
X=stats.weibull_min.rvs(bt,loc=gt,scale=et,size=M,random_state=rng)
def nll_mean(b,e,g,X):
    z=(X-g)/e; z=np.where(z>0,z,np.nan)
    lp=np.log(b/e)+(b-1)*np.log(z)-z**b
    return -np.nanmean(lp)
# (a) 期望NLL随参数比值变化（β、η 各自），最小在 1.0
ratios=np.linspace(0.6,1.5,40)
nll_b=np.array([nll_mean(bt*r,et,gt,X) for r in ratios])
nll_e=np.array([nll_mean(bt,et*r,gt,X) for r in ratios])
nll_b-=nll_b.min(); nll_e-=nll_e.min()
print(f'  期望NLL最小点: β比值={ratios[np.argmin([nll_mean(bt*r,et,gt,X) for r in ratios])]:.3f}, '
      f'η比值={ratios[np.argmin([nll_mean(bt,et*r,gt,X) for r in ratios])]:.3f} (应≈1.0)')
# (b) 期望 pinball(τ=0.01) 随报告分位点 q，最小在真 1% 分位 = x_{R=0.99}
tau=0.01
x_true_99=quantile_xR(bt,et,gt,0.99)
qs=np.linspace(x_true_99*0.5,x_true_99*1.6,60)
def pinball_mean(q,tau,X):
    e=X-q
    return np.mean(np.where(e>=0, tau*e, (tau-1)*e))
pb=np.array([pinball_mean(q,tau,X) for q in qs])
q_star=qs[np.argmin(pb)]
print(f'  期望pinball(τ=0.01)最小 q*={q_star:.1f}, 真B1寿命 x_(R=0.99)={x_true_99:.1f} (应一致)')
# (c) 同中位数不同尾部
M0=1000.0
betas=[1.0,2.0,4.0]; cols_b=[WARN,PRI,GOOD]
xx=np.linspace(1,3000,1500)
curves=[]; b0995=[]
for b in betas:
    eta=M0/(np.log(2))**(1/b)
    Rx=np.exp(-(xx/eta)**b)
    curves.append(Rx)
    b0995.append(eta*(-np.log(0.995))**(1/b))
print(f'  同中位数 M=1000, β={betas} → B0.995(R=0.995分位)= {[round(v,1) for v in b0995]} (差异巨大)')
out['exp6']=dict(q_star=float(q_star), x_true_99=float(x_true_99),
                 b0995={str(b):float(v) for b,v in zip(betas,b0995)})

fig, axes = plt.subplots(1, 3, figsize=(13.2, 4.0))
ax=axes[0]
ax.plot(ratios,nll_b,'-',color=PRI,lw=2.2,label=r'改变 $\beta$')
ax.plot(ratios,nll_e,'-',color=WARN,lw=2.2,label=r'改变 $\eta$')
ax.axvline(1.0,color=BAD,lw=1.6,ls='--')
ax.set_xlabel('报告参数 / 真值'); ax.set_ylabel('超出最小的期望NLL')
ax.set_title('(a) NLL 在真值处最小 → 恰当(proper)')
ax.legend(fontsize=9.5); ax.text(1.0,ax.get_ylim()[1]*0.9,' 真值',color=BAD,fontsize=9,va='top')
ax.text(0.5,0.06,'真值是唯一最优 → 可放心作训练目标',transform=ax.transAxes,ha='center',
        fontsize=8.5,color=INK,bbox=dict(boxstyle='round,pad=0.3',fc='#E8EEF5',ec=PRI,lw=0.7))
ax=axes[1]
ax.plot(qs,pb,'-',color=GOOD,lw=2.2)
ax.axvline(x_true_99,color=BAD,lw=1.6,ls='--')
ax.axvline(q_star,color=PRI,lw=1.2,ls=':')
ax.set_xlabel('报告分位点 q (小时)'); ax.set_ylabel(r'期望 pinball 损失 ($\tau$=0.01)')
ax.set_title('(b) pinball 精准定位目标分位点')
ax.text(x_true_99,ax.get_ylim()[1]*0.92,f' 真 B1 寿命\n {x_true_99:.0f}h',color=BAD,fontsize=9,va='top')
ax.text(0.5,0.06,'最小点=真 1% 分位\n→ 直接优化工程关心的寿命',transform=ax.transAxes,ha='center',
        fontsize=8.5,color=INK,bbox=dict(boxstyle='round,pad=0.3',fc='#EAF2EA',ec=GOOD,lw=0.7))
ax=axes[2]
for b,Rx,c,bl in zip(betas,curves,cols_b,b0995):
    ax.plot(xx,Rx,'-',color=c,lw=2,label=f'β={b:.0f}, B0.995={bl:.0f}h')
ax.axhline(0.5,color=GRY,ls=':',lw=1); ax.axvline(M0,color=GRY,ls=':',lw=1)
ax.axhline(0.995,color=BAD,ls='--',lw=1)
ax.set_xlim(0,2200); ax.set_xlabel('寿命 x (小时)'); ax.set_ylabel('可靠度 R(x)')
ax.set_title('(c) 同中位数,尾部天差地别')
ax.legend(fontsize=8.6, loc='upper right')
ax.text(M0,0.46,' 中位数相同\n =1000h',color=GRY,fontsize=8.5,va='top')
ax.text(0.03,0.30,'仅匹配中位数的损失\n无法识别尾部(B0.995差40×)\n→ loss 必须“看见”尾部',transform=ax.transAxes,
        fontsize=8.3,color=INK,bbox=dict(boxstyle='round,pad=0.3',fc='#FBEAEA',ec=BAD,lw=0.7))
fig.suptitle('实验6  训练损失：NLL/pinball 恰当且可定向；中位数匹配无法约束尾部',
             fontsize=12.5, fontweight='bold', y=1.03)
fig.tight_layout(); fig.savefig('/home/claude/figs/fig6_loss.png', bbox_inches='tight'); plt.close(fig)
print('  saved figs/fig6_loss.png')

json.dump(out, open('/home/claude/results_456.json','w'), indent=2, default=float)
print('\nsaved results_456.json')
