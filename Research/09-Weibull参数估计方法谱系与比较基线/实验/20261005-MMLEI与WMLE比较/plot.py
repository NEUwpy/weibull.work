"""Render static research figures from audited CSVs; no estimator calls.

Use the project Python venv, with matplotlib installed.
"""
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
FONT = FontProperties(fname='C:/Windows/Fonts/msyh.ttc')
plt.rcParams.update({'font.family':FONT.get_name(),'axes.unicode_minus':False,
                     'svg.fonttype':'none','pdf.fonttype':42,'font.size':10})
LABELS = {'cw_i_nonnegative':'修正极大似然（MMLE-I，非负位置）',
          'wmle_checked':'加权极大似然（WMLE，含漏解复核）',
          'cw_i_paper_domain':'MMLE-I（原文参数域）'}
COLORS = {'cw_i_nonnegative':'#2365a4','wmle_checked':'#c65a20','cw_i_paper_domain':'#3f7d5e'}
N = [7,10,15,20,50]


def save(fig, name):
    for extension in ['png','svg','pdf']:
        fig.savefig(HERE/f'{name}.{extension}',dpi=180,bbox_inches='tight')
    plt.close(fig)


def accuracy(file, methods, name):
    data = pd.read_csv(HERE/file)
    fig, axes = plt.subplots(2,2,figsize=(10.2,7.5),layout='constrained')
    for ax, column, ylabel in zip(axes.flat,
        ['beta_norm_rmse','eta_norm_rmse','gamma_norm_rmse','J1_valid'],
        ['形状 β：归一化 RMSE','尺度 η：归一化 RMSE','位置 γ：按尺度归一化 RMSE','联合误差 J1']):
        for method in methods:
            part=data[data.method_variant.eq(method)].sort_values('n')
            ax.plot(range(5),part[column],marker='o',color=COLORS[method],label=LABELS[method],lw=1.8)
        ax.set_xticks(range(5),N)
        ax.set_xlabel('样本量 n')
        ax.set_ylabel(ylabel)
        ax.set_ylim(bottom=0)
        ax.grid(alpha=.22)
    axes[0,0].legend(fontsize=8,loc='best')
    save(fig,name)


def main():
    accuracy('by_n_common.csv',['cw_i_nonnegative','wmle_checked'],'共同成功样本精度')
    accuracy('by_n_paper_common.csv',['cw_i_paper_domain','wmle_checked'],'原文参数域敏感性精度')
    own = pd.read_csv(HERE/'by_n_own_valid.csv')
    by_beta = pd.read_csv(HERE/'by_beta_n.csv')
    fig,axes=plt.subplots(1,3,figsize=(14.2,4.4),layout='constrained')
    for method in LABELS:
        part=own[own.method_variant.eq(method)].sort_values('n')
        axes[0].plot(range(5),part.failure_rate*100,marker='o',color=COLORS[method],
                     linestyle='--' if method=='cw_i_paper_domain' else '-',label=LABELS[method])
    axes[0].set_xticks(range(5),N)
    axes[0].set_ylabel('未得到可接受估计的比例（%）')
    axes[0].set_xlabel('样本量 n')
    axes[0].set_ylim(0,100)
    axes[0].grid(alpha=.22)
    axes[0].legend(fontsize=7.7)
    for ax, method in zip(axes[1:],['cw_i_nonnegative','wmle_checked']):
        matrix=by_beta[by_beta.method_variant.eq(method)].pivot(index='beta',columns='n',values='failure_rate')
        matrix=matrix[N]*100
        ax.imshow(matrix,vmin=0,vmax=100,cmap='YlOrRd',aspect='auto')
        ax.set_xticks(range(5),N)
        ax.set_yticks(range(4),matrix.index)
        ax.set_xlabel('样本量 n')
        ax.set_ylabel('真形状参数 β')
        ax.set_title('MMLE-I（非负位置）' if method.startswith('cw') else 'WMLE（含漏解复核）',fontsize=11)
        for i in range(4):
            for j in range(5):
                value=matrix.iloc[i,j]
                ax.text(j,i,f'{value:.1f}',ha='center',va='center',
                        color='white' if value>65 else '#222222',fontsize=9)
    save(fig,'失败率与形状条件')


if __name__=='__main__':main()
