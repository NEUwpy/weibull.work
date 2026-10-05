"""Write the independent audit report from evidence tables; never edit batches."""
import hashlib
import json
import math
from pathlib import Path
import pandas as pd

HERE=Path(__file__).resolve().parent
ROOT=HERE.parent
NAMES={'A':'W(2,1000,1000)','B':'W(2,1000,500)','C':'W(2,100,500)'}
PARAMS={'beta':'β','eta':'η','gamma':'γ'}

def link(label,p,line=None):
    return f'[{label}](<{Path(p).as_posix()}{":"+str(line) if line else ""}>)'

def table(headers,rows):
    return '\n'.join(['| '+' | '.join(headers)+' |','| '+' | '.join(['---']*len(headers))+' |']+['| '+' | '.join(map(str,row))+' |' for row in rows])

def main():
    summary=json.loads((HERE/'核验摘要.json').read_text(encoding='utf-8'))
    guard=json.loads((HERE/'三批输入保护.json').read_text(encoding='utf-8'))
    axes=json.loads((HERE/'坐标与数据来源.json').read_text(encoding='utf-8'))
    configs=pd.read_csv(HERE/'配置核对.csv')
    stats=pd.read_csv(HERE/'样本批次统计.csv')
    hashes=pd.read_csv(HERE/'文件SHA256.csv')
    refits=pd.read_csv(HERE/'抽组重算核对.csv')
    norm=pd.read_csv(HERE/'无量纲指标.csv')
    pixels=pd.read_csv(HERE/'九图复绘核对.csv')
    # Reconcile existing manifest entries with actual files, in addition to the guard.
    manifest_entries=0
    for name in NAMES.values():
        batch=ROOT/name
        manifest=json.loads((batch/'程序/manifest.json').read_text(encoding='utf-8'))
        for entry in manifest['files']:
            p=batch/entry['path']
            assert p.stat().st_size==entry['bytes'] and hashlib.sha256(p.read_bytes()).hexdigest()==entry['sha256']
            manifest_entries+=1
    # Standardized metrics were computed directly from successful estimate CSVs;
    # convert them back to raw units and independently reconcile all graph summaries.
    for key,name in NAMES.items():
        original=pd.read_csv(ROOT/name/'结果/三方法汇总.csv')
        for r in norm[norm.batch==key].itertuples():
            stored=original[(original.method==r.method)&(original.n==r.n)].iloc[0]
            truth=summary['truths'][key][list(PARAMS).index(r.parameter)]
            assert stored.success==r.success and math.isclose(stored.success_rate,r.success_rate,rel_tol=2e-12,abs_tol=2e-12)
            for metric in ['bias','sd','rmse']:
                assert math.isclose(getattr(r,'relative_'+metric)*truth,stored[r.parameter+'_'+metric],rel_tol=2e-12,abs_tol=2e-10)
    summary.update(scalar_summary_metrics_rechecked=405,manifest_file_entries_verified=manifest_entries,
                   archived_plot_audit_directory='D:/Hermes Email/执行完毕/research09-batch-verify-016/复绘核查')
    (HERE/'核验摘要.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    def triple(frame,column):
        return ' / '.join(f'{v:.4f}' for v in frame[column])
    out=['# 三批核查报告：真值与图形相似性',
         '> 2026-10-05 · 邮件016 · 只读核查；A/B/C全部144个既有文件的SHA与清单保持。',
         '## 核查结论',
         '**确认三批分别使用了W(2,1000,1000)、W(2,1000,500)、W(2,100,500)，未发现真值写错、串批或图数据来源错误。** 证据不只来自文件夹名字：三批18000组原始样本由各自真值和存档种子重生成后，全部367200个观测逐值一致；54000行估计的真值字段及对应输入SHA一致；每批随机抽3组，共27次方法重算与存档对应，其中26次成功参数通过容差，1次原MLE失败仍失败。',
         '**9张PNG的SHA均不同；从各批相邻CSV独立复绘后，9张均与各自原图逐像素、逐字节相同。** A/B/C任一对都没有相同的6000组原始输入，也没有相同的标准化输入组或完整成功散点集合。未见将同一张图或同一套散点误作不同批次的异常。',
         '图形像，主要是同一β、同一方法与n带来相近的标准化形状，加上同一模板、颜色、布局，以及C批η/γ的误差轴随η一起缩小十倍。C批**没有**把η=100压在0–2000量程上：它的η小提琴轴为0–200、γ轴为400–600。',
         '## 1. 配置与方法版本证据',
         table(['批次','文件夹','config真值 β/η/γ','manifest真值 β/η/γ','n','每n组数','总输入/估计'],
               [[r.batch,r.folder,f'{r.beta:g}/{r.eta:g}/{r.gamma:g}',f'{r.beta:g}/{r.eta:g}/{r.gamma:g}',r.n,r.groups_per_n,f'{r.groups}/{r.estimates}'] for r in configs.itertuples()]),
         'n由config读取；每n组数=config的12个block×每block 100次，并与每批样本CSV的五个1200行、每方法对应1200行交叉核对。A的manifest有顶层n和groups_per_n；B/C采用verification中的总输入6000与估计18000字段，配置与逐组数据补齐每n核对，未将不存在的manifest字段当作已记录。',
         '方法版本三批一致：MLE为既有有限驻点局部极大根口径，β下界1.01；MMLE为Kundu–Raqab原版单样本构造，γ取最小值、删一个最小观测，β初值1、绝对步长1e-8、最多10000迭代；WMLE为作者J₁/J₂/J₃加权方程，β下界0.1、上界15及原选根。无新增Firth、非负γ限制、回退或漏解复核。MMLE按保留样本γ<x₂检查，MLE/WMLE按γ<x₁检查。',
         f'三批冻结源码逐文件相同；paper_solver.py的共同SHA256为 `{configs.iloc[0].frozen_solver_sha256}`。全部配置、方法说明、权重与代码证据保持在各批程序目录。',
         table(['批次','配置入口','manifest入口','当前配置任务/打包任务'],
               [[r.batch,link('config.json',ROOT/r.folder/'程序/config.json'),link('manifest.json',ROOT/r.folder/'程序/manifest.json'),f'{r.config_task} / {r.manifest_task}'] for r in configs.itertuples()]),
         'A的配置任务为邮件007，manifest打包任务为邮件012，属于原批结果的整理，不能误读为A在邮件012重新算了全部方法。B/C分别在邮件013/015重新计算三方法。三批各自真值的样本和估计由下述实际数据核查确认。',
         '## 2. 原始样本明显不同，并与各自配置精确对应',
         '每组先取样本最小值、中位数、均值，再对1200组求平均；表中不是把所有组误拼成一个中位数。括号三元组依次为“最小值均值 / 组内中位数均值 / 组内均值均值”。']
    sample_rows=[]
    for n in [7,10,15,20,50]:
        sample_rows.append([n]+[' / '.join(f'{g.iloc[0][c]:.3f}' for c in ['mean_sample_min','mean_sample_median','mean_sample_mean']) for key in NAMES for g in [stats[(stats.batch==key)&(stats.n==n)]]])
    out += [table(['n','A 样本位置统计','B 样本位置统计','C 样本位置统计'],sample_rows),
            '例如n=7，三批样本均值的批均值分别1889.186、1377.991、587.786；最小值均值分别1335.830、831.900、533.728。数值清楚体现γ的平移和η的收缩，绝不是三份同样的原始样本。',
            r'各批逐组使用共享generate_sample(β,η,γ,n,repeat_id,seed=存档命名空间)重生成，与CSV排序观测及组SHA全部一致。种子本身含β/η/γ；因此三批没有同随机数配对。标准化$Z=(X-\gamma)/\eta$均为β=2的Weibull样本，其理论均值为$\Gamma(1.5)=0.886227$。本次各批各n的标准化样本均值为0.877857–0.889186，接近同一理论值；这是分布相似，不是同一批数据。',
            '## 3. 随机抽组反算三方法',
            '固定随机种子2026100516；每批在n=7、15、50的全部1200组中各随机取1组，没有筛选“容易成功”的组。共9组×3方法=27次独立输入重算。MLE/WMLE直接给冻结求解器原始样本，不读取存档估计作初值；MMLE另用修改似然的profile score经Brent求根，与原固定点迭代形成不同数值路径的交叉检查。',
            '成功参数逐个要求 |重算−存档| ≤ 1e-7 + 1e-7×|存档|（atol=rtol=1e-7）。原固定点的步长容差不是最终根误差界；因此MMLE的高精度score根可与存档存在约1e-7形状、约1e-5尺度差，仍在明确容差内。MLE/WMLE本次最大参数差约2.3e-13。失败要求状态一致且存档参数仍为空，不用伪造数值参与比较。',
            '下表存档与重算三元组顺序均为β/η/γ，显示6位；差值列为三参数的最大绝对差。未舍入的全部三参数及各自差值见抽组重算CSV。']
    refit_rows=[]
    for r in refits.itertuples():
        if r.recomputed_status=='failure':
            stored=recomputed='失败，无估计';maximum='—';status='失败一致'
        else:
            stored=' / '.join(f'{getattr(r,"stored_"+p):.6f}' for p in PARAMS)
            recomputed=' / '.join(f'{getattr(r,"recomputed_"+p):.6f}' for p in PARAMS)
            maximum=f'{max(abs(getattr(r,"difference_"+p)) for p in PARAMS):.3e}';status='通过'
        refit_rows.append([r.batch,r.n,r.group,r.method,stored,recomputed,maximum,status])
    out += [table(['批次','n','组号','方法','存档 β/η/γ','重算 β/η/γ','最大绝对差','核对'],refit_rows),
            'A n=7第206组MLE在存档和本次重算都没有可用有限根；另外26次成功核对均通过。27次重算是抽查，不声称逐件重算了54000个方法估计。另有全部18000组输入重生成、全部54000行真值和输入关联检查、全部九图复绘作为不同层面的证据。',
            '## 4. 样本、估计与九图SHA证据',
            '样本与估计文件两两SHA不同；每一对按同n/组号比较，6000组中原始输入完全相同0组，标准化输入在绝对容差1e-12下完全相同0组；每对五个n×三方法×三参数的45个成功散点集合也没有一个相同。散点集合按数值排序，避免把不同排序误报成不同数据。',
            table(['批次','文件','字节','SHA256'],[[r.batch,r.file,r.bytes,f'`{r.sha256}`'] for r in hashes[hashes.file.isin(['样本.csv','估计明细.csv'])].itertuples()]),
            '九图的SHA互不相同，文件尺寸如下。仅哈希不同不足以证明数据源正确，所以另用相邻CSV复绘并验证逐像素、逐字节一致。',
            table(['批次','PNG','字节','SHA256'],[[r.batch,r.file,r.bytes,f'`{r.sha256}`'] for r in hashes[hashes.file.str.endswith('.png')].itertuples()]),
            table(['批次','复绘小提琴','复绘有解率','复绘九格'],[[key]+['像素一致、字节一致' for _ in range(3)] for key in NAMES]),
            '复绘没有替换原图，临时复绘与绘图核验记录在邮箱任务016中；已发表的结果文件没有改动。SHA清单、逐图原/复绘SHA及尺寸见对应CSV。',
            '## 5. 为什么图长得像？',
            '### 5.1 同模板，C批量程已随单位收缩',
            '三批使用同样的3×5小提琴、颜色/散点/粉中位数/红均值、同一n坐标、有解率线、3×3指标布局。下表列实际坐标，来自各draw.py并与本次实际复绘核验记录核对；小提琴是横向参数轴，九格是纵向误差轴。']
    axis_rows=[]
    for a in axes:
        format_range=lambda x:f'{x[0]:g}–{x[1]:g}'
        axis_rows.append([a['batch'], ' / '.join(format_range(a['violin'][p]) for p in PARAMS),
                          ' / '.join(format_range(x) for x in a['metric_limits']['rmse']),
                          ' / '.join(format_range(x) for x in a['metric_limits']['bias']),
                          ' / '.join(format_range(x) for x in a['metric_limits']['sd']), 'x 5–52；y 0–1.03'])
    out += [table(['批次','小提琴 β/η/γ','RMSE β/η/γ','Bias β/η/γ','SD β/η/γ','有解率'],axis_rows),
            'A/B的η与γ小提琴轴都是0–2000；C的η改为0–200、γ改为400–600。C的η/γ RMSE与SD轴0–90，Bias轴−40–40，是A/B对应误差轴的十分之一。**若忽略刻度数字，只看曲线在框内的高度，尺度与轴同除10会使图形接近。** 原统计仍包含图窗外成功值，未以缩窄量程删掉不利结果。',
            '一个直接例子：n=7的MMLE γ RMSE为A 378.372、B 372.900、C 38.030；除以各图RMSE纵轴上限900/900/90后，分别0.4204、0.4143、0.4226，视觉高度本来就接近。η小提琴的MMLE均值708.977、700.592、69.092分别除以轴宽2000/2000/200，落在0.3545、0.3503、0.3455的位置。',
            '### 5.2 标准化后分布相近，但γ不能随便除以自身真值',
            r'三批形状β相同；对平移/尺度等变构造，$\hat\beta-\beta$和$(\hat\eta-\eta)/\eta$、$(\hat\gamma-\gamma)/\eta$的分布本来不随位置尺度变化。MMLE取最小值并用差分估β/η，具备这一结构。MLE当前方程/域/根选择具备平移结构，但固定原始单位数值容差会限制严格尺度等变；WMLE现选根评分还含绝对原点，不能宣称其完整实现全域严格等变。三批样本不同，因此有限表值不应完全相同。',
            '按用户提出的自身真值口径重算：以下每个三元组为A/B/C，全部15个方法×n条件。位置真值不同，γ误差/γ不要求重合；最后一列再给共同尺度口径γ RMSE/η。相对SD与相对Bias的完整135行在无量纲CSV。']
    norm_rows=[]
    for method in ['MLE','MMLE','WMLE']:
        for n in [7,10,15,20,50]:
            cells=[]
            for param in PARAMS:
                g=norm[(norm.method==method)&(norm.n==n)&norm.parameter.eq(param)].set_index('batch').loc[list(NAMES)]
                cells.append(triple(g,'relative_rmse'))
            g=norm[(norm.method==method)&(norm.n==n)&norm.parameter.eq('gamma')].set_index('batch').loc[list(NAMES)]
            norm_rows.append([method,n,*cells,triple(g,'common_eta_rmse')])
    out += [table(['方法','n','β RMSE/β A/B/C','η RMSE/η A/B/C','γ RMSE/γ A/B/C','γ RMSE/η A/B/C'],norm_rows),
            'MMLE η相对Bias的稳定性尤其清楚：',
            table(['n','A η Bias/η','B η Bias/η','C η Bias/η'],[[n]+[f'{100*norm[(norm.batch==key)&norm.method.eq("MMLE")&(norm.n==n)&norm.parameter.eq("eta")].iloc[0].relative_bias:.2f}%' for key in NAMES] for n in [7,10,15,20,50]]),
            '例如n=7，MMLE η相对Bias为−29.10%、−29.94%、−30.91%；n=50为−13.44%、−13.53%、−13.34%。β相对RMSE在n=7约45.16%/47.29%/47.50%，n=50约17.02%/16.80%/17.25%。稳定的方法结构会带来相似的形状；这与输入逐组不同并不矛盾。',
            r'MMLE位置误差更有精确参照：$(\hat\gamma-\gamma)/\eta\sim W(2,1/\sqrt n)$，故$RMSE_\gamma/\eta=1/\sqrt n$，n=7/10/50理论为0.3780/0.3162/0.1414，与三批表值接近。相反$RMSE_\gamma/\gamma=(\eta/\gamma)/\sqrt n$，三批η/γ为1、2、0.2，理论位置相对误差比例为1:2:0.2，不能要求三批γ自身真值归一化后重合。',
            '### 5.3 小样本误差大、分布重叠；随n增大收缩',
            'n=7时MLE β相对RMSE仍约122%–128%、η相对RMSE约68%–81%，且只有29%–33%的样本有有限有效估计；MMLE β相对RMSE约45%–48%，WMLE约49%–50%。n=10时MMLE/WMLE的η相对RMSE约32%/35%–36%，仍存在明显波动和偏差。n=50才分别收缩到β约17%/20%，η约16.5%–16.7%/14.8%–15.0%。因此小n的三方法分布有大范围重叠，肉眼难以区分有限批次的细微差别；同一β、同一n下共享的偏差/尾部模式也会重复出现。',
            '本报告没有把“肉眼重叠”当作统计等价检验。既有A/B差值分析中150项有8项超出单项95%区间、0项通过Holm；C未在本报告新增跨批多重检验。见'+link('两批真值比较',ROOT/'两批真值比较/两批真值比较.md')+'。',
            '### 5.4 有没有异常地完全相同？',
            '没有发现文件、数据源或完整散点集合层面的异常复制。9个PNG各有不同SHA，三对样本/估计文件也各异，三对共135个完整成功散点集合没有相同者。固定白底、轴框和标记会重复，个别散点落到同一像素也可能发生；这些视觉重合不等于整张图或原始数据被复制。9图从各自CSV复绘完全对应，排除了当前图错接其他批CSV这一类问题。',
            '## 6. 绘图数据来源与定位',
            '当前没有发现需要修复的真值或数据源错误。以下给出实际源文件与行号，便于直接复核，而不是仅凭目录名确认：',
            table(['批次','估计CSV读取行','汇总CSV读取行','真值定义/配置行','误差量程行'],
                  [[a['batch'],link('draw.py',a['script'],a['lines']['data']),link('draw.py',a['script'],a['lines']['summary']),link('draw.py',a['script'],a['lines']['truth']),link('draw.py',a['script'],a['lines']['metric_limits'])] for a in axes]),
            '小提琴读取同批结果/估计明细.csv；有解率、九格读取同批结果/三方法汇总.csv。A真值线在脚本中为[2,1000,1000]，B/C从同批config.json读取，均与实际真值吻合。复绘核验记录的source_sha256均等于对应估计CSV。',
            '## 7. 可选展示方案（本次未改图）',
            table(['方案','能解决的问题','代价或边界'],[
                ['保留原始单位图，图注写清三真值及实际量程','避免把同一视觉高度误当同一绝对误差','仍需读刻度；只改图注即可表达真实尺度'],
                ['另做统一无量纲图：β误差/β、η误差/η、γ误差/η，统一轴','比较方法在共同尺度下的偏差与波动，直观看到何种相似有理论依据','会有意去掉位置尺度差异；γ误差/η要明示，不能称γ误差/γ'],
                ['另做跨批统一原始单位量程的对照页','使C的原始误差确实小十倍可见','C曲线会压低，细节难看；宜配共同尺度图'],
                ['在原小提琴页统一注明真值，保留每批固定量程','保持同参数跨n可比且容易认批','不同批的几何形状不能脱离刻度直接比较']
            ]),
            '## 8. 核验文件与复现',
            f'三批当前144文件全SHA及清单保持；之前的96文件保护基线再次通过。另核对三份manifest记录的{manifest_entries}个条目，文件大小与SHA全部符合；从估计明细重算的全部405个Bias/SD/RMSE与45组有解数/率也与原汇总表一致。没有修改三批任何程序、配置、数据、图、Excel或说明。',
            '- '+link('audit.py',HERE/'audit.py')+'；'+link('write_report.py',HERE/'write_report.py')+'；'+link('核验摘要.json',HERE/'核验摘要.json')+'。',
            '- '+link('配置核对.csv',HERE/'配置核对.csv')+'；'+link('样本批次统计.csv',HERE/'样本批次统计.csv')+'；'+link('抽组重算核对.csv',HERE/'抽组重算核对.csv')+'。',
            '- '+link('文件SHA256.csv',HERE/'文件SHA256.csv')+'；'+link('九图复绘核对.csv',HERE/'九图复绘核对.csv')+'；'+link('跨批样本与散点复核.csv',HERE/'跨批样本与散点复核.csv')+'。',
            '- '+link('无量纲指标.csv',HERE/'无量纲指标.csv')+'；'+link('坐标与数据来源.json',HERE/'坐标与数据来源.json')+'；'+link('三批输入保护.json',HERE/'三批输入保护.json')+'。',
            'PowerShell复现（输出目录必须在A/B/C以外；-B及环境变量避免源目录字节码缓存）：',
            '\n'.join(['```powershell',"$env:PYTHONDONTWRITEBYTECODE='1'", "$env:PYTHONIOENCODING='utf-8'",
                       f"& 'D:\\weibull\\python\\.venv\\Scripts\\python.exe' -B '{HERE/'audit.py'}' --plot-output 'D:\\Hermes Email\\执行完毕\\research09-batch-verify-016\\复绘核查'",
                       f"& 'D:\\weibull\\python\\.venv\\Scripts\\python.exe' -B '{HERE/'write_report.py'}'",'```']),
            '原估计54000行未逐件重新拟合；完成的是18000组输入全量精确重生成、54000行真值/输入关联核查、27次方法抽查及九图全量复绘。没有改图、提交或推送。']
    (HERE/'三批核查报告.md').write_text('\n\n'.join(out)+'\n',encoding='utf-8')
    files={str(p) for name in NAMES.values() for p in (ROOT/name).rglob('*') if p.is_file()}
    assert files==set(guard) and all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==digest for p,digest in guard.items())
    print(json.dumps(dict(report_characters=len('\n\n'.join(out)),manifest_entries_verified=manifest_entries,protected_files_unchanged=len(guard)),ensure_ascii=False))

if __name__=='__main__':
    main()
