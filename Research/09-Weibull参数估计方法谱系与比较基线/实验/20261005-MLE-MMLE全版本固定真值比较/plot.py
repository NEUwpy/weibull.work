"""One PNG containing every version and separate parameter-domain panels."""
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties
import pandas as pd
from experiment import HERE, METHODS

plt.rcParams.update({'font.family':['Microsoft YaHei','DejaVu Sans'],'axes.unicode_minus':False,
    'font.size':12,'axes.titlesize':14,'axes.labelsize':12,'savefig.facecolor':'white'})
STYLE={'mle_local':('#777777','s','--','MLE（有限局部解）'),
       'wmle_checked':('#111111','D','-','WMLE（含漏解复核）'),
       'mmle_i':('#0072B2','o','-','MMLE-I'), 'mmle_ii':('#E69F00','^','-','MMLE-II'),
       'mmle_iii':('#8B63A8','v','-','MMLE-III'),'mmle_iv':('#009E73','P','-','MMLE-IV'),
       'mmle_v':('#56B4E9','X','-','MMLE-V'),
       'mme_i':('#D55E00','o',':','MME-I'), 'mme_ii':('#8F5640','^',':','MME-II'),
       'mme_iii':('#CC79A7','v',':','MME-III')}

def main():
    data=pd.read_csv(HERE/'by_n_own_valid.csv')
    fig=plt.figure(figsize=(16,13))
    gs=fig.add_gridspec(4,2,height_ratios=[1,.20,1,.15],hspace=.22,wspace=.23)
    axes=[fig.add_subplot(gs[0,0]),fig.add_subplot(gs[0,1]),
          fig.add_subplot(gs[2,0]),fig.add_subplot(gs[2,1])]
    groups=[METHODS[:10],['mle_local','wmle_checked']+[m for m in METHODS if m.endswith('_paper')]]
    for k,group in enumerate(groups):
        handles=[]
        for method in group:
            base=method.removesuffix('_paper');color,marker,linestyle,label=STYLE[base]
            part=data[data.method_variant.eq(method)].sort_values('n')
            for j,column in enumerate(['success_rate','J1_valid']):
                ax=axes[k*2+j]
                values=part[column]*(100 if j==0 else 1)
                line,=ax.plot(part.n,values,label=label,color=color,marker=marker,
                              linestyle=linestyle,linewidth=2,markersize=6,alpha=.95)
                if j==0:handles.append(line)
        legend_ax=fig.add_subplot(gs[k*2+1,:]);legend_ax.axis('off')
        legend_ax.legend(handles=handles,ncol=5 if k==0 else 4,loc='center',frameon=False,
                         columnspacing=1.8,handlelength=2.7,fontsize=11)
        for j in range(2):
            ax=axes[k*2+j];ax.set_xticks([7,10,15,20,50]);ax.set_xlabel('样本量 n')
            ax.grid(alpha=.25);ax.spines[['top','right']].set_visible(False)
            if j==0:ax.set_ylim(-3,103);ax.set_ylabel('有效估计成功率（%）')
            else:ax.set_ylabel('J1：归一化联合 RMSE（越小越好）');ax.set_ylim(bottom=0)
    axes[0].set_title('A  非负位置主比较：成功率',loc='left')
    axes[1].set_title('B  非负位置主比较：成功样本精度',loc='left')
    axes[2].set_title('C  MMLE 原文参数域敏感性：成功率',loc='left')
    axes[3].set_title('D  MMLE 原文参数域敏感性：成功样本精度',loc='left')
    fig.suptitle('固定真值 β=2、η=1000、γ=1000：MLE / MMLE I–V / MME I–III / WMLE',
                 fontsize=18,y=.985)
    fig.text(.5,.952,'每个 n 1200组共享样本（12 × 100）；MMLE 原文域允许负位置，单独展示',
             ha='center',fontsize=12)
    fig.text(.065,.035,r'J1 = $\sqrt{\mathrm{mean}[((\hat\beta-2)/2)^2 + ((\hat\eta-1000)/1000)^2 + ((\hat\gamma-1000)/1000)^2]}$。'+'\n'
             '精度按各方法自己的成功样本计算；失败不计为零误差。成功样本不同，曲线的精度排名不能直接视为同样本优势。\n'
             '共同成功样本比较见 paired_vs_wmle.csv；MME 多根按有效支持域与样本偏度初值选支。',
             fontsize=11,va='bottom')
    fig.subplots_adjust(top=.90,bottom=.13,left=.075,right=.97)
    fig.savefig(HERE/'全版本成功率与精度.png',dpi=180)
    plt.close(fig)
    print(str(HERE/'全版本成功率与精度.png'))

if __name__=='__main__':main()
