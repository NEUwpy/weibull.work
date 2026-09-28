import fs from 'node:fs/promises';
import path from 'node:path';
import {createRequire} from 'node:module';
import {pathToFileURL,fileURLToPath} from 'node:url';
const modules=process.env.RUNTIME_NODE_MODULES;
if(!modules)throw new Error('Use bundled runtime modules');
const require=createRequire(path.join(modules,'package.json'));
const {Presentation,PresentationFile,FileBlob}=await import(pathToFileURL(require.resolve('@oai/artifact-tool')));
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const tmp=path.resolve(root,'../../tmp/r09-v21');
await fs.mkdir(tmp,{recursive:true});
const source=path.join(root,'历史/2026-09-28通用决策重构前/260928组会.pptx');
const orig=await PresentationFile.importPptx(await FileBlob.load(source));
const proto=orig.toProto();
const old=proto.slides;
old[1].elements=old[1].elements.filter(e=>e.id!=='29');
const cleaned=s=>{const t=structuredClone(s);t.elements=t.elements.filter(e=>['2','3','4','5'].includes(e.id));return t;};
// Keep original method and genealogy slides. Insert two evidence slides, not a new deck structure.
proto.slides=[...old.slice(0,10),cleaned(old[1]),cleaned(old[1]),cleaned(old[10]),old[11],old[12],cleaned(old[13]),cleaned(old[14]),old[15],cleaned(old[16])];
proto.slides.forEach((s,i)=>{s.id=`r09v21-${i+1}`;s.index=i;});
const p=Presentation.load(proto);
const font='Microsoft YaHei',blue='#2F6096',dark='#182538',muted='#65717A';
function txt(s,text,x,y,w,h,size=24,color=dark,bold=false){const q=s.shapes.add({geometry:'textbox',position:{left:x,top:y,width:w,height:h},fill:'none',line:{fill:'none',width:0}});q.text=text;q.text.style={typeface:font,fontSize:size,color,bold,autoFit:'none'};return q;}
function replace(slide,search,value){let n=0;for(const q of slide.shapes.items){if(String(q.text).includes(search)){q.text.replace(search,value);n++;}}return n;}
function setContains(slide,search,value,size){for(const q of slide.shapes.items){if(String(q.text).includes(search)){q.text=value;if(size)q.text.style={typeface:font,fontSize:size,color:blue,autoFit:'none'};return q;}}throw new Error('Missing '+search);}
function base(n,chapter,title){const s=p.slides.items[n-1];for(const q of s.shapes.items){if(q.id==='5'){q.text=title;q.text.style={typeface:'汉仪文润宋韵 U',fontSize:34,bold:true,color:'#FFFFFF',autoFit:'none'};}if(q.id==='2')q.text=chapter;if(q.id==='4')q.text=n<=12?'02':'03';}return s;}
function lead(s,text){txt(s,text,64,177,1152,45,25,blue);}
function foot(s,text){txt(s,text,64,634,1152,40,19,blue,true);}
function table(s,rows,widths,{y=253,h=346,size=22,x=64,w=1152}={}){const t=s.tables.add({rows:rows.length,columns:rows[0].length,left:x,top:y,width:w,height:h,columnWidths:widths,values:rows});t.borders.assign({fill:'#DAE1E9',width:.6,style:'solid'});if(rows.length<8){t.rows[0].height=55;for(let r=1;r<rows.length;r++)t.rows[r].height=(h-55)/(rows.length-1);}for(let r=0;r<rows.length;r++)for(let c=0;c<rows[0].length;c++){const cell=t.getCell(r,c);cell.fill=r===0?blue:'#FFFFFF';cell.text.style={typeface:font,fontSize:size,color:r===0?'#FFFFFF':dark,bold:r===0,autoFit:'none'};}return t;}
function notes(n,text){p.slides.items[n-1].speakerNotes.textFrame.setText(text);}
// Small corrections to retained v2.0 slides.
for(const q of p.slides.items[0].shapes.items)if(q.id==='64')q.position={left:0,top:420.75,width:1280,height:0};
setContains(p.slides.items[1],'验证一种新的参数估计方法','完整样本、小样本、三参数估计：只与老方法比较是否充分？',24);
setContains(p.slides.items[1],'与哪些方法比较','新方法应与谁比，近年有什么进展，如何形成有依据的比较？',24);
const table3=p.slides.items[2].tables.items[0];table3.getCell(2,2).value='绘图分数、回归方向和位置构造不同';
setContains(p.slides.items[4],'下面比较项目实际采用的版本','LS与LRE同属概率图路线，具体构造由分数、方向与位置规则决定。',23);
const tab5=p.slides.items[4].tables.items[0];tab5.getCell(0,0).value='文献版本示例';tab5.getCell(0,2).value='Park 2017：Proposed+Plot';tab5.getCell(1,2).value='按n分段的绘图概率，经双对数变换';
setContains(p.slides.items[4],'项目LRE不等于','Park保留原绘图位置和位置域；Bernard分数是另一个变体。来源见报告§1.3。',16);
setContains(p.slides.items[7],'库内反复出现','63条定向核查材料显示多种路线并存，尚不能据此判断全领域重心转移。',23);
notes(8,'资料/近期文献范围核查.md：63条定向编码，51条2006年以来、35条2016年以来；标签重叠，样本选择有偏，不作领域占比。HGLM2024与AIMGC-PSO2026仅题录/摘要，待全文。');
setContains(p.slides.items[8],'MDM已在第一章介绍','MDM已见第一章。HGLM 2024、AIMGC-PSO 2026仅核摘要，尚待全文。',22);
notes(9,'原方法来源见报告§2.2；新增HGLM DOI10.1007/s12206-024-0911-5；AIMGC-PSO DOI10.1016/j.probengmech.2026.103978。仅题录/摘要，不作性能判断。');
notes(10,'WMLE在Nagatsuka2013中采用Ng权重代入版本；Safari2025属污染实验。后续采用不直接证明干净小样本优势。Park在ADGBO2026中实际使用；MDM与部分后续工作有作者重合。见报告§2.3和比较习惯核查。');
{
const s=base(11,'近期进展及其检验证据','文献中的优势随参数、样本量与指标改变');
lead(s,'同一论文也会得到不同排序，方法较新或有理论性质都不足以决定胜负');
table(s,[['原论文与设计','原文发现','选型含义'],['Akram–Hayat 2014\nβ=0.5—9，n=10—100','β=3、4时MLE偏差较小\nMoE的RMSE更小','Bias和RMSE可以支持不同选择\n且该文筛选了收敛样本'],['Nagatsuka 2013\nβ=0.5—5，n=10—500','作者整体建议\nn≤20考虑WMLE，n≥100考虑LSPF','LSPF仍有构造与可解性价值\n不能直接认定为小样本最强']],[330,397,425],{y:259,h:309,size:23});
foot(s,'这些是各篇内部的条件结果，不能拼接为跨论文统一排名。');
notes(11,'Akram–Hayat2014 DOI10.1080/15598608.2014.847771，§4.1 L365–415：η100、γ90，每格5000，保留ML收敛且L偏度≥−.1699；β<1省略ML。Nagatsuka2013 DOI10.1016/j.csda.2012.09.005，§3 L173–238，1000次，具体比较对象BL及Ng式WMLE。原文的总体建议有参数和指标例外，详见报告§2.4，不能当作本研究选法规则。');
}
{
const s=base(12,'近期进展及其检验证据','近期小样本与偏差修正证据各有边界');
lead(s,'既要看到改进，也要保留作者实际检验的范围');
table(s,[['工作','已报告的条件结果','仍不能推断'],['SAM 2023\nβ=1.5、2、2.5\nn=5、10、15、20','n≤10的平均MAD优势明显\n随n增大，与MLE差距缩小','未覆盖β<1\n跨参数MAD受单位和尺度影响'],['DMMLE 2025\n3组参数，n=50—1000','偏差有所改善\nRMSE总体相近','尚无n=5—20的直接证据\n偏差降低不等于总体误差降低']],[330,420,402],{y:259,h:309,size:23});
foot(s,'近期对手依据任务匹配与已核结果选择，结论限定到对应指标和条件。');
notes(12,'SAM DOI10.1007/s12206-023-1019-z，L381–498：γ1、η8个值.2至4、10000重复，MAD为三参数绝对误差直接平均；n15/20对MLE占优的参数配置比例87.5%/79.2%，非单次样本胜率。DMMLE DOI10.3390/e27050485，L218–230，原参数(μ,α,σ)=(1,1,1),(1,.5,2),(1,1.5,2)，σ=η^β，1000重复。报告§2.4与literature_performance_boundaries.json。');
}
const audit=JSON.parse(await fs.readFile(path.join(root,'evidence/benchmark_comparison_audit.json'),'utf8'));
const families=['MLE','CC','MM','WMLE','MPS','PWM','MMLE','LS','MDM','BL','CMLE','LM','MMoE'];
const names={'182-030':'MDM 2023','182-047':'迭代LS 2023','182-088':'WMLE 2009','182-091':'修正估计 1982','182-096':'综合比较 2014','182-101':'比较研究 2009','182-111':'DMMLE 2025','182-113':'LSPF 2013','182-117':'PM 2024','183-020':'ANN 2008','184-009':'BPNN 2025','185-005':'SAM 2023','187-001':'ADGBO 2026'};
{
const s=base(13,'对照选择、版本与验证','已核13篇文献的实际比较对象');
lead(s,'完整三参数重复模拟，同篇同类计一次，提出方法不计为自身对手');
const records=audit.records.filter(r=>r.primary_included).sort((a,b)=>a.year-b.year||a.id.localeCompare(b.id));
const rows=[['论文／提出方法',...families],...records.map(r=>[names[r.id],...families.map(f=>r.sim_benchmarks.some(x=>x.family===f)?'●':'')]),['采用篇数',...families.map(f=>String(audit.summary.all.families[f].count))]];
const t=table(s,rows,[258,...families.map(()=>894/13)],{y:233,h:380,size:17});
t.cells.block({row:0,column:0,rowCount:rows.length,columnCount:rows[0].length}).assign({margins:{top:1,bottom:1,left:3,right:3}});
for(let r=1;r<rows.length-1;r++)for(let c=1;c<rows[0].length;c++){const cell=t.getCell(r,c);cell.text.style={typeface:font,fontSize:16,color:blue,alignment:'center'};}
foot(s,'MLE 8篇、CC 5篇。近期7篇中6篇作者网络重合，频次只说明这组文献的实践。');
notes(13,'benchmark_comparison_audit.json。13篇ID依次与names映射；2006+12篇、2016+7篇、含n≤30为11篇。综合比较182-096计参与方法，剔除它后MLE7/12、CC5/12。MM包含传统矩版本，LM/PWM分列，MMoE为修正矩。182-050同名构造有误不合并。3篇MLE+CC共现。数据频次不是性能。');
}
{
const s=p.slides.items[13];
setContains(s,'以下面向完整三参数','完整样本、小样本的起始选择建议，由文献比较习惯和条件结果共同支持。',23);
const t=s.tables.items[0];
t.getCell(4,1).value='优先审查SAM；相关时加入PM';t.getCell(4,2).value='SAM有n=5—20证据；PM的n=5及指标须细辨';
t.getCell(5,0).value='与主张直接相关';t.getCell(5,1).value='母方法或同目标竞争者';t.getCell(5,2).value='继承已有方法时必保留母方法';
setContains(s,'按主张扩展','低形状／可解性关注MPS、LSPF；矩类或偏差修正分别补LM／PWM或DMMLE。',22);
notes(14,'报告§3.2。MLE是通行参照；WMLE有有限样本修正及跨作者采用；概率图有重复使用和不同构造；SAM小样本任务匹配，但三参数平均MAD有尺度限制。PM n5比较非直接统一RMSE。此处为有条件起始建议，不是固定四法或文献共识。LSPF2013自身作者小n总体建议WMLE，故不能仅凭存在性作为小n必选。');
}
{
const s=p.slides.items[14];const t=s.tables.items[0];
t.getCell(1,2).value='原绘图概率、Plot分支和位置域';
t.getCell(3,2).value='J权重版本；区分Ng代入与迭代';
t.getCell(5,2).value='MLE注明局部／受限解，MPS保留端点';
notes(15,'报告§3.3各构造论文。MLE局部/剖面似然为实现说明，不另立Local-ML新方法。WMLE J权重与LSPF比较中的Ng式代入不能混同。LS为Soman–Misra的White扩展分支。所有变体应披露。');
}
{
const s=base(16,'对照选择、版本与验证','Monte Carlo与真实数据的证据分工');
lead(s,'参数真值是否已知，决定能用什么证据评价方法');
txt(s,'Monte Carlo：估计准确性',64,266,550,47,29,blue,true);
txt(s,'共同生成样本，逐参数报告Bias、RMSE、SD。\n13篇主子集分别核到4、7、5篇。\n同时报告有效率与失败分母。',64,330,550,154,24);
txt(s,'真实数据：应用与拟合',676,266,530,47,29,blue,true);
txt(s,'报告参数、寿命量、CDF及K-S／AD。\n未知真值，不能据拟合优胜推断参数更准。\n预测或区间主张需要相应验证。',676,330,530,154,24);
txt(s,'小样本n=5—30为重点，较大n看趋势；参数条件与重复精度依研究范围说明。',64,535,1152,66,25,blue);
foot(s,'三参数结果保留分别评价，联合指标说明归一化；真实数据不替代模拟精度证据。');
notes(16,'报告§3.4，比较习惯核查metric_summary同13篇，相对Bias、联合指标单列。n5—20可追溯SAM/BPNN，n10—30迭代LS，较大n LSPF/综合比较。这里提供有文献依据的评价原则，不冻结参数网格或重复次数。');
}
{
const s=base(17,'对照选择、版本与验证','真实数据在已有论文中承担什么作用');
lead(s,'同一寿命数据可检验拟合与可计算性，反复使用不增加独立证据');
table(s,[['来源与数据','实际评价','支持的结论'],['BPNN：15点疲劳寿命','对CCM、MDM比较K-S、CDF','方法应用与这组数据的拟合'],['LSPF：10点、4点寿命','参数及变换似然，记录MM／BL不收敛','估计行为与困难样本可计算性'],['SAM：10点、4点寿命','K-S、CDF、MTTF和可靠度寿命','应用差异；部分参照为历史结果'],['再抽样或留出（可选）','稳定性、模型条件误差或预测得分','参照与假设决定能证明什么']],[325,440,387],{y:256,h:334,size:22});
foot(s,'Bootstrap不产生原总体真值；未知端点与重复值处理需要另行论证。');
notes(17,'报告§3.4。BPNN184-009，LSPF182-113，SAM185-005。10点/4点寿命数据被多篇重复使用，非独立数据集数。参数bootstrap来自拟合模型；非参数bootstrap有重复值/MPS零间距问题，端点非正则模型的有效性不可默认。可选评价设计不写成所有论文通行惯例。');
}
notes(18,'报告§3.5：182-096筛ML收敛/L偏度样本；182-091限制形状与50次求解，报告未得估计次数；182-030 MLE失败标零仅绘图；182-101剔除形状>5。MLE不受限似然因β<1及γ逼近样本最小值的路径无界，与真实β是否<1不是同一个判断。有效极端值、边界与数值失败分开；各自与共同有效子集皆条件结果。');
{
const s=base(19,'调研结论','对开场问题的回答');
for(const q of s.shapes.items)if(q.id==='4')q.text='04';
lead(s,'比较方案应来自文献证据，并且能够检验新方法声称的改进');
const rows=[['已有方法怎样发展','围绕位置、偏差和估计依据形成多条路线，后来的构造各有改进目标。'],['近年有什么，如何取舍','WMLE、Park、SAM／PM等均有相关进展，性能证据必须附条件。'],['应该和谁比较','优先MLE、WMLE、明确的概率图版本及任务相关近期对手，按主张补充。'],['应该怎样比较','MC报告逐参数误差及有效率，真实数据说明应用；版本与失败规则透明。']];
rows.forEach((r,i)=>{txt(s,r[0],64,266+i*86,280,47,26,'#BE5A10',true);txt(s,r[1],356,266+i*86,856,68,24);});
foot(s,'这是有条件的选型与评价建议；近期候选全文、部分性能条件和失败分母仍需补核。');
notes(19,'研究报告v2.1总结。报告的边界是文献支持的benchmark选择和评价建议，未运行新性能实验。经典基线、近期相关构造与母方法承担不同作用，不按年份或频次推出性能排名。');
}
await fs.writeFile(path.join(tmp,'deck-inspect.ndjson'),(await p.inspect({kind:'slide,textbox,table,chart',maxChars:250000})).ndjson);
await fs.writeFile(path.join(tmp,'requirements.json'),JSON.stringify({requiredNativeTableOwnerSlides:[3,5,9,11,12,13,14,15,17,18],requiredNativeChartOwnerSlides:[]}));
await (await PresentationFile.exportPptx(p)).save(path.join(tmp,'candidate.pptx'));
console.log('Candidate ready: '+tmp);
