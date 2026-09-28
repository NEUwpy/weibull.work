import fs from 'node:fs/promises';
import path from 'node:path';
import crypto from 'node:crypto';
import {pathToFileURL,fileURLToPath} from 'node:url';
import {createRequire} from 'node:module';
// Run with the bundled Node runtime and RUNTIME_NODE_MODULES set to its node_modules.
// Produces a private candidate only; finalize and render before updating the public deck.
const moduleRoot=process.env.RUNTIME_NODE_MODULES;
if(!moduleRoot)throw new Error('Set RUNTIME_NODE_MODULES using load_workspace_dependencies');
const requireRuntime=createRequire(path.join(moduleRoot,'package.json'));
const {Presentation,PresentationFile,FileBlob}=await import(pathToFileURL(requireRuntime.resolve('@oai/artifact-tool')));
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const tmp=process.env.R09_BUILD_DIR??path.resolve(root,'../../tmp/r09-final');
await fs.mkdir(tmp,{recursive:true});
const skill='C:/Users/36089/.codex/plugins/cache/openai-primary-runtime/presentations/26.905.11957/skills/presentations';
const source=path.join(root,'历史/2026-09-28通用决策重构前/260928组会.pptx');
const sourceDeck=await PresentationFile.importPptx(await FileBlob.load(source));
const proto=sourceDeck.toProto();
const cover=proto.slides[0], template=proto.slides[1];
proto.slides=[cover,...Array.from({length:14},(_,i)=>{
  const s=structuredClone(template);s.id=`r09v3-${i+2}`;s.index=i+1;
  s.elements=s.elements.filter(e=>['2','3','4','5'].includes(e.id));
  return s;
})];
const p=Presentation.load(proto);
const blue='#2D609F', orange='#C95016', dark='#182538', muted='#596775';
const font='Microsoft YaHei';
const audit=JSON.parse(await fs.readFile(path.join(root,'evidence/benchmark_comparison_audit.json'),'utf8'));
const direction=JSON.parse(await fs.readFile(path.join(root,'evidence/recent_direction_audit.json'),'utf8'));
const {applyPresentationChartFont}=await import(pathToFileURL(path.join(skill,'container_tools/artifact_tool_utils.mjs')));
function txt(s,text,x,y,w,h,size=25,color=dark,bold=false){
 const q=s.shapes.add({geometry:'textbox',name:text.slice(0,28),position:{left:x,top:y,width:w,height:h},fill:'none',line:{fill:'none',width:0}});
 q.text=text;q.text.style={typeface:font,fontSize:size,color,bold,autoFit:'none'};return q;
}
function base(i,chapter,title,notes){
 const s=p.slides.items[i-1];
 for(const q of s.shapes.items){
  if(q.id==='5'){q.text=title;q.text.style={typeface:'汉仪文润宋韵 U',fontSize:34,bold:true,color:'#FFFFFF',autoFit:'none'};}
  if(q.id==='2'){q.text=chapter;q.text.style={typeface:font,fontSize:23,color:'#111111',autoFit:'none'};}
  if(q.id==='4'){q.text=String(i===2?1:i===3?2:i<=5?3:i<=10?4:5).padStart(2,'0');q.text.style={typeface:font,fontSize:23,color:'#111111',autoFit:'none'};}
 }
 txt(s,`${i} / 15`,1162,663,70,23,15,muted);
 s.speakerNotes.textFrame.setText(notes+'\n本页为Research09独立调研建议或有界文献统计，不是新增性能实验。完整来源与定位见研究报告v3.0和相应核查JSON。');return s;
}
function table(s,rows,widths,{y=220,h=350,size=23}={}){
 const t=s.tables.add({rows:rows.length,columns:rows[0].length,left:64,top:y,width:1152,height:h,columnWidths:widths,values:rows});
 t.borders.assign({fill:'#CBD7E5',width:0.7,style:'solid'});
 for(let r=0;r<rows.length;r++)for(let c=0;c<rows[0].length;c++){
  const cell=t.getCell(r,c);cell.fill=r===0?'#2D609F':r%2?'#F0F5FA':'#FFFFFF';
  cell.text.style={typeface:font,fontSize:size,color:r===0?'#FFFFFF':dark,bold:r===0,autoFit:'none'};
 }
 return t;
}
function foot(s,text){txt(s,text,64,624,1078,38,17,muted);}
function lead(s,text){txt(s,text,64,169,1152,52,27,blue,true);}
function row(s,n,title,body,y){txt(s,n,55,y,84,65,38,orange,true);txt(s,title,145,y,1040,44,28,blue,true);txt(s,body,145,y+48,1040,68,24,dark);}
function chart(s,cats,values,x,y,w,h){const c=s.charts.add('bar',{position:{left:x,top:y,width:w,height:h},categories:cats.toReversed(),series:[{name:'论文数',values:values.toReversed(),fill:blue}],barOptions:{direction:'bar',grouping:'clustered'},hasLegend:false,dataLabels:{showValue:true,position:'outEnd',textStyle:{typeface:font,fontSize:20,fill:dark}},xAxis:{textStyle:{typeface:font,fontSize:20}},yAxis:{textStyle:{typeface:font,fontSize:20}},chartFill:'#FFFFFF',plotAreaFill:'#FFFFFF'});applyPresentationChartFont(c,{fontFamily:font});return c;}
// Preserve the supplied cover artwork and title band.
for(const q of p.slides.items[0].shapes.items){
 if(String(q.text).includes('Weibull')) {q.text='三参数 Weibull 参数估计\n比较对象与评价方案';q.text.style={typeface:'汉仪粗宋简',fontSize:46,bold:true,color:'#FFFFFF',autoFit:'none'};}
 if(q.id==='64') q.position={left:0,top:420.75,width:1280,height:0};
}
p.slides.items[0].speakerNotes.textFrame.setText('研究目的：完整样本、尤其小样本三参数Weibull新估计器应与谁比较，为什么，采用哪版，怎样比较。本轮独立于Study01。推荐属于文献调研决定，尚未完成全部方法复现与新性能实验。');
{
const s=base(2,'研究问题','新方法应该和谁比，为什么，怎样比？','研究报告§1；用户研究意图保存在README。');
row(s,'01','对象：完整样本、小样本、三个未知参数','一般移位 γ∈R；非负起点寿命 γ≥0。两种任务要分别说明。',220);
row(s,'02','证据：方法来源与论文中的实际比较','同一名称不一定同一构造；引用不等于采用；频次不等于性能。',350);
row(s,'03','产物：明确组合、具体版本、评价协议','经典参照＋问题相关竞争者；按创新主张增加母方法或近邻。',480);
}
{
const s=base(3,'方法沿革','沿革决定比较作用，名称不能代替定义','研究报告§2；Cousineau2009 DOI10.1348/000711007X270843；MPS DOI10.1111/j.2517-6161.1983.tb01268.x；LSPF DOI10.1016/j.csda.2012.09.005；Park DOI10.23055/ijietap.2017.24.4.2848。White为后文追溯。');
lead(s,'保留五条与选型直接有关的路线');
table(s,[['路线','代表沿革','比较作用'],['似然与修正','MLE → WMLE 2009 / DMMLE 2025','共同参照、偏差修正'],['概率图','White → Soman–Misra / Park','绘图分数、方向与位置域'],['矩与概率加权','MM → PWM → L矩','矩类创新的直接参照'],['非正则问题的新构造','MPS 1983；LSPF 2013','不同准则，不是直接继承'],['顺序构造与学习','MDM、SAM / PM；ANN / BPNN','按具体创新主张增补']],[240,530,382],{h:356,size:23});
foot(s,'优化器替换、估计方程修改、直接学习映射，需要分开判断。');
}
{
const s=base(4,'近期进展','近期材料同时包含新构造与特殊任务','资料/近期文献范围核查.md；evidence/recent_direction_audit.json。63条有界定向编码，选择偏向任务辨别，不能估计领域份额。图只展示部分重叠标签，完整表见报告。');
const d=direction.counts.recent_2006_2026;
lead(s,`2006年以来已核年份 ${d.n} 条；标签可重叠，分母来自定向核查`);
txt(s,'研究任务',70,226,520,40,27,blue,true);txt(s,'创新内容',671,226,520,40,27,blue,true);
const a=['完整观测子项','删失','二参数','混合结构'];const b=['数值求解','修正或组合构造','新估计构造','贝叶斯'];
chart(s,a,a.map(k=>d.task_counts[k]??0),65,276,540,300);chart(s,b,b.map(k=>d.innovation_counts[k]??0),668,276,540,300);
foot(s,'可确认通用构造仍在出现；该样本不能证明全领域研究重心已发生转移。');
}
{
const s=base(5,'近期进展','直接相关的近期竞争者仍在出现','研究报告§3.2。WMLE、LSPF、Park、SAM、PM、DMMLE原文入口见报告。HGLM：10.1007/s12206-024-0911-5；AIMGC-PSO：10.1016/j.probengmech.2026.103978。后两项仅摘要/元数据，不计采用频次。');
lead(s,'年份只是入口，任务匹配与具体构造决定是否进入实验');
table(s,[['时期／方法','直接相关性','本次取舍'],['2009 WMLE；2013 LSPF','完整三参数、有限样本／非正则','一般主组'],['2017 Park Plot','概率图、非负位置','寿命问题主组'],['2023 MDM / SAM；2024 PM','一致性构造／极小样本顺序更新','按创新主张增补'],['2025 DMMLE；近期BPNN','似然偏差／学习估计','匹配主张时加入'],['2024 HGLM；2026 AIMGC-PSO','小样本组合与智能搜索','全文待补，暂不作性能结论']],[390,430,332],{h:350,size:22});
foot(s,'不能说近年没有新方法，也不能说某个最新方法已经成为统一benchmark。');
}
{
const s=base(6,'实际比较','MLE与概率图路线是主要共同参照','资料/比较习惯核查.md；evidence/benchmark_comparison_audit.json。主集13篇，完整普通三参数、重复抽样、全参数或联合风险。同篇同类只计一次，提出方法不计自身对手；综合比较182-096计参与者。');
lead(s,'13篇严格主子集：同篇同类最多一次，提出方法不计为自身对手');
const cats=['MLE','CC','MM','WMLE','MPS','PWM','MMLE','LS','MDM'];
chart(s,cats,cats.map(k=>audit.summary.all.families[k]?.count??0),67,230,748,365);
txt(s,'8 / 13',892,253,280,70,54,blue,true);txt(s,'使用MLE作参照',864,329,327,50,25);
txt(s,'6 / 13',892,409,280,70,54,blue,true);txt(s,'LS或相关系数路线\n合并仅用于粗分类',864,486,327,90,24);
foot(s,'CC与LS的具体构造不同；频次说明采用实践，不证明哪个估计器性能最好。');
}
{
const s=base(7,'实际比较','常见做法是共同基线加问题相关对手','研究报告§4.1；比较习惯核查。Cousineau182-101明示MLE作常用基线，Nagatsuka182-113依据前序结果选WMLE/BL。182-050的名义BL/LSPF与原构造不符，已排除规范采用计数。');
lead(s,'有反复出现的比较逻辑，尚无证据支持唯一默认组合');
table(s,[['论文／研究','实际比较对象','对选型的启示'],['Cousineau 比较研究','MLE、MPS、WMLE','保留常用参照并比较替代构造'],['Nagatsuka LSPF','WMLE、BL','根据前序证据选较强对手'],['SAM；PM','MLE＋CC或LS＋PWM','共同基线加相关路线'],['BPNN','CC、MDM','学习方法与目标问题近邻比较']],[340,420,392],{h:300,size:23});
txt(s,'三篇共同出现MLE＋CC；部分近期论文作者重合。\n论文数不能当独立团队数，方法引用不能当运行采用。',68,552,1120,69,25,blue);
foot(s,'旧9篇定向矩阵由本轮审核取代；有争议的同名方法不再合并计数。');
}
{
const s=base(8,'评价依据','Monte Carlo直接评价参数误差','研究报告§4.2与§5.4。同一13篇主子集明确核到逐参数RMSE7、SD5、Bias4；相对Bias1，跨参数平均指标另编码。指标建议按作用作出，并非领域统一规范。');
lead(s,'主输出：逐参数Bias、RMSE、SD，加有效率');
table(s,[['要回答什么','采用什么','需要避免什么'],['系统偏差与总误差','每个参数Bias、RMSE','只看估计均值离真值多远'],['抽样波动与可计算性','SD、有效数 / 全部生成数','只列成功样本RMSE排名'],['不同单位如何比较','形状和尺度相对误差\n位置误差除以尺度η','位置γ=0时除以γ'],['特定主张是否成立','寿命误差、覆盖率＋区间长度','把拟合R²当参数准确性']],[325,450,377],{h:330,size:23});
foot(s,'联合指标只作摘要，保留β、η、γ各自结果；极端有效估计不能随意删除。');
}
{
const s=base(9,'评价依据','真实数据展示应用、拟合与算法表现','研究报告§4.3；LSPF182-113、SAM185-005、BPNN184-009、Akram–Hayat182-096。非参数重抽样会产生重复值，普通MPS零间距处理与端点非正则性必须另定义。');
row(s,'01','默认任务：应用与拟合诊断','参数、经验CDF、KS或AD统计量、有效状态和用时。真实参数通常未知。',218);
row(s,'02','需要p值：拟合后重新估参校准','按参数bootstrap校准，说明拟合模型条件；普通KS临界值不能直接套用。',351);
row(s,'03','需要预测或稳定性：另设评价设计','留出数据支撑预测；重抽样须处理重复值及端点问题，不产生新的真值。',484);
}
{
const s=base(10,'评价依据','MLE异常必须进入比较结果','研究报告§4.4、§5.5；MPS1983及DMMLE2025。固定β<1让γ逼近最小观测，可使全域似然无界。不能仅凭有限搜索未找到就证明无局部极大。');
lead(s,'采用有限局部剖面似然参照Local-ML，明确区别于全域最优');
table(s,[['环节','统一要求'],['定义','公开目标、参数域、初始化、预算与验收规则'],['状态','区分搜索到限、未收敛、支持域违反及有效极端值'],['分母','全部生成数、各自有效数、固定主组与成对共同有效数'],['误差','各自与共同有效集均标条件结果；失败不填零或真值'],['解释','没有找到有限局部极大，不等于已证明数学上不存在']],[230,922],{h:350,size:25});
foot(s,'改变对手会改变共同有效集；公开回退流程并单独命名。');
}
{
const s=base(11,'最终选择','一般移位四基准，非负寿命再加Park','研究报告§5.1；资料/通用比较方案核查.md。此为调研推荐，不是文献投票共识，也不代表这些方法已完成共同实验。');
txt(s,'一般移位模型  γ∈R',67,202,1120,49,30,blue,true);
txt(s,'Local-ML     WMLE-J     MPS     LSPF',66,280,1140,70,43,blue,true);
txt(s,'通行似然参照       小样本修正       间距准则       2013年直接相关构造',69,368,1120,45,23);
txt(s,'非负起点寿命  γ≥0',67,457,1120,50,30,blue,true);
txt(s,'四基准 ＋ Park2017 Proposed+Plot',68,523,1120,58,36,orange,true);
foot(s,'Park使用非负信息，其余保留原定义；需要统一非负输出时，另报受限版本敏感性。');
}
{
const s=base(12,'最终选择','每个benchmark固定到可辨认的版本','研究报告§5.2。WMLE构造原文式3–4、LSPF§2与§2.3、Park2017§5、MPS1983。细节及原文链接见附录B与通用方案核查。');
lead(s,'方法简称必须与公式、约束和实际程序对应');
table(s,[['benchmark','固定版本','防止的混淆'],['Local-ML','条件二参数ML＋局部剖面极大','任意得分根≠局部极大'],['WMLE-J','J1、J2、候选β对应J3中位权重','不以真β选权重、不夹表域'],['MPS','含两端的n+1个CDF间距','重复值扩展另命名'],['LSPF','标准化次序统计量形状似然','不能用2P-MLE形状替代积分'],['Park2017 Plot','分段绘图概率＋z对log寿命回归','不是项目Bernard-LRE']],[250,540,362],{h:350,size:22});
foot(s,'统计版本已选择；WMLE权重覆盖、LSPF积分等仍须通过实施前复现验证。');
}
{
const s=base(13,'最终选择','近期方法按新方法的主张增补','研究报告§5.3。SAM/PM算法边界与PM伪代码符号已在资料/通用比较方案核查.md定位。DMMLE选DM2，原模拟n≥50。');
lead(s,'母方法仅在存在继承关系时必加，不预设MDM普遍必选');
table(s,[['新方法的主张','增补对象','必须满足的条件'],['极小样本、顺序更新','SAM2023','非负位置，公开停止／越界规则'],['条件似然或区间','PM2024','修正求根伪代码；验证覆盖率'],['似然偏差修正','DMMLE2025 DM2','小n属于新外推检验'],['矩／伪参数一致性','对应PWM、LM或MDM','原构造和被改动分支清楚'],['学习或智能搜索','BPNN；HGLM/AIMGC等','训练信息可比，相关全文先补齐']],[430,300,422],{h:350,size:22});
foot(s,'加入对手的理由是检验具体主张，不能仅以年份新旧决定去留。');
}
{
const s=base(14,'实施方案','共同模拟与真实应用的推荐安排','研究报告§5.4–5.5。网格与重复次数是本调研设计建议，并非已运行或文献统一标准。主分析n=5/10/20/30/50，n100只作补充。');
table(s,[['设置','推荐方案'],['形状与样本量','β=0.5、0.8、1、1.2、1.5、2、3、5；n=5、10、20、30、50'],['位置与尺度','一般移位η=1、γ=0；非负寿命加γ/η=0.5、2'],['重复与精度','每格先10000次；共享样本，按Monte Carlo误差追加'],['敏感性','负位置适用域、单位缩放、边界、有效极端估计'],['真实数据','完整寿命数据＋公开困难样本；统一拟合与算法诊断'],['实施顺序','先验证原文例子、权重和积分，再执行正式共同模拟']],[240,912],{y:199,h:399,size:23});
foot(s,'任何性能结论均限定于实际检验的参数格子；本轮交付方案，未启动大规模重算。');
}
{
const s=base(15,'研究结论','四个问题已有明确回答','研究报告v3.0。来源范围与剩余全文/复现门槛见研究进度与待办。最终推荐 independent of Study01。');
row(s,'01','和谁比','一般移位：Local-ML、WMLE-J、MPS、LSPF；非负寿命再加Park。',195);
row(s,'02','为什么选，采用哪版','依据任务匹配、实际比较习惯和估计作用；固定到原文分支与约束。',320);
row(s,'03','怎样比','共同Monte Carlo评价真值误差与有效率；真实数据评价应用和拟合。',445);
foot(s,'近期候选全文与算法复现仍有门槛；不宣称已覆盖全领域或验证了方法性能名次。');
}
await fs.writeFile(path.join(tmp,'deck-inspect.ndjson'),(await p.inspect({kind:'slide,textbox,table,chart',maxChars:180000})).ndjson);
const candidate=path.join(tmp,'candidate.pptx');
await (await PresentationFile.exportPptx(p)).save(candidate);
console.log(candidate);
