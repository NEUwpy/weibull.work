import fs from 'node:fs/promises';
import path from 'node:path';
import crypto from 'node:crypto';
import {createRequire} from 'node:module';
import {pathToFileURL} from 'node:url';
const require=createRequire(new URL('./.build/runtime.cjs',import.meta.url));
const sharp=require('sharp');
const {Presentation,PresentationFile,FileBlob}=await import(pathToFileURL(require.resolve('@oai/artifact-tool')).href);
export const ROOT=path.resolve(import.meta.dirname,'..');
export const TMP=path.join(import.meta.dirname,'.build');
export const TITLE='小样本三参数Weibull参数估计方法的比较与选择';
export const FINAL=path.join(ROOT,TITLE+'.pptx');
const A='reviewbyhtml/方法对比-v1.0/assets/';
const U='方法分类/机制图-v2.2/预览/';
const UP='报告上（方法分类）-v2.3.md',DOWN='报告下（方法对比）-v2.1.md';
const BLACK='#192F40',BLUE='#2D5D97',GRAY='#536575';
const upper=await fs.readFile(path.join(ROOT,UP),'utf8');
const lower=await fs.readFile(path.join(ROOT,DOWN),'utf8');
const sha=s=>crypto.createHash('sha256').update(s).digest('hex');
const strip=s=>s.replace(/!\[[^\]]*\]\([^)]+\)/g,'').replace(/\[([^\]]+)\]\([^)]+\)/g,'$1').replace(/\*\*/g,'');
function section(md,key){const start=md.indexOf(key); if(start<0)return ''; const tail=md.slice(start);const end=tail.slice(key.length).search(/\n##? /);return strip(end<0?tail:tail.slice(0,key.length+end));}
const plan=[];
function add(title,config={}){plan.push({title,part:'方法路线图',source:UP,...config});}
function low(title,config={}){add(title,{part:'性能比较',source:DOWN,...config});}
const fig=(file,caption='',extra={})=>({image:file.startsWith('U:')?U+file.slice(2):A+file,caption,...extra});
add(TITLE,{type:'cover',part:'封面',section:'开场',notes:'各位老师、各位同学，大家好！我是东北大学机械工程与自动化学院的魏鹏宇。今天汇报小样本三参数Weibull参数估计方法的比较与选择。第一部分梳理方法原理及相互联系；第二部分在共同样本上比较代表方法，分析性能现象并解释典型机制。'});
add('方法原理与性能变化共同构成比较依据',{type:'text',section:'研究背景',items:[['研究背景','试验成本与周期限制，使寿命分布参数估计经常面对小样本。'],['方法整理','依据估计机制归纳路线，并区分文献间的沿袭、数学联系与局部借用。'],['统一比较','在共同样本下发现性能变化，解释典型现象，再讨论评价与选择。']],notes:strip(upper.slice(0,upper.indexOf('## 1')))});
add('路线图同时表达估计机制与方法之间的联系',{section:'方法路线图',...fig('U:06-完整机理地图-估计路线与方法关系.svg','浅色区域界定五条路线；实线表示沿袭或修正，虚线表示数学联系，点划线表示借用或组合。'),sectionKey:'## 1'});
add('五条路线依据不同机制将样本信息转为参数',{type:'table',section:'五条估计路线',widths:[245,405,500],rows:[['估计路线','从样本构造什么','据此怎样确定参数'],['似然构造与优化','观测或统计量的联合密度','最大化似然，或按具体构造修正方程'],['分布关系匹配','概率图、概率间距、反推尺度等','指定拟合、一致性或概率结构准则'],['统计特征关系匹配与反演','矩、分位数、次序统计量等特征','匹配理论关系，消元并恢复参数'],['贝叶斯后验推断','似然与先验形成后验分布','按后验决策规则给出估计'],['学习型参数映射','多组带参数标签的训练样本','训练映射，固定后用于新样本']],sectionKey:'## 2'});
add('联合似然同时比较三个参数组成的候选组合',{section:'似然构造与优化',...fig('U:07-似然估计路线-信息处理流程.svg','β、η、γ构成三维参数空间；等值面表示相同相对似然，红线为实际数值迭代，极大点限于图示参数窗。'),sectionKey:'## 3'});
add('似然路线通过数据、方程或目标修改形成具体方法',{section:'似然构造与优化',...fig('U:01-似然估计路线-机制图.svg','上方沿用“构造联合似然→联合最大化”；下方对照删点、权重、辅助关系、区间概率及罚似然。'),sectionKey:'## 3'});
add('分布匹配先明确比较对象，再指定参数准则',{section:'分布关系匹配',...fig('U:08-分布匹配路线-信息处理流程.svg','构造分布表示→定义匹配准则→确定参数；CDF平方差仅为此处示例。'),sectionKey:'## 4'});
add('回归方向、概率间距与尺度一致性形成不同匹配依据',{section:'分布关系匹配',...fig('U:02-分布匹配路线-机制图.svg','各分支沿相同主步骤展开；White与Park分数及回归方向不同，MPS与MDM采用各自准则。'),sectionKey:'## 4'});
add('统计关系方法通过选定特征的理论关系识别参数',{section:'统计特征关系匹配与反演',...fig('U:09-统计关系反演路线-信息处理流程.svg','提取样本特征→建立理论关系→识别与恢复参数；常规矩以偏度、方差和均值示例。'),sectionKey:'## 5'});
add('更换特征、权重与识别关系形成不同的统计构造',{section:'统计特征关系匹配与反演',...fig('U:03-统计关系反演路线-机制图.svg','常规矩、Cran、PWM／L矩／截尾L矩、W／V变换和条件位置MVLUE分别改变相应环节。'),sectionKey:'## 5'});
add('贝叶斯估计由后验分布与决策规则共同决定',{section:'贝叶斯后验推断',...fig('U:10-后验推断路线-信息处理流程.svg','构造后验→后验决策；平方损失对应后验均值，中位数与MAP采用各自规则。'),sectionKey:'## 6'});
add('后验决策与抽样近似分别决定输出和计算路径',{section:'贝叶斯后验推断',...fig('U:04-后验推断路线-机制图.svg','同一后验可按不同规则输出估计；Gibbs、MH与Laplace服务于抽样或近似计算。'),sectionKey:'## 6'});
add('学习型方法先训练映射，再用于新样本',{section:'学习型参数映射',...fig('U:11-学习映射路线-信息处理流程.svg','训练映射→固定映射用于新样本；训练使用标签，应用时不需提供新样本的真实参数。'),sectionKey:'## 7'});
add('直接映射、过程量学习与数值搜索的作用位置不同',{section:'学习型参数映射',...fig('U:05-学习映射路线-机制图.svg','直接预测参数、辅助传统估计器和搜索当前目标分别接入不同环节。'),sectionKey:'## 7'});
add('同一路线并不自动构成方法间的历史沿袭',{type:'table',section:'方法之间的联系',widths:[215,520,415],rows:[['关系类型','代表联系','说明'],['沿袭或扩展','Jacquelin（1993）→ WMLE（2009）→ 形状修正（2024）','有文献依据的延续与修正'],['沿袭或扩展','White（1969）→ LSE（1992）；LSPF（2013）→ LPF（2015）','接入未知位置或保留更多参数信息'],['数学联系','PWM与L矩；同分数、同位置的两种回归','注明关系成立的条件'],['局部借用或组合','Kundu–Raqab与Firth修正 → DMMLE','不同来源的步骤汇合']],sectionKey:'## 8'});
add('七种实现覆盖路线内改动与路线间差异',{type:'table',section:'本轮比较对象',widths:[210,350,590],rows:[['实现','采用的机制','对应构造'],['MLE','原始联合似然','观测密度形成联合似然；另记录边界与失败'],['WMLE','估计方程修正','Cousineau（2009）：估计方程中引入三权重'],['MMLE','最小值定位后进行似然估计','Kundu、Raqab（2009）：删最小观测后估计'],['LSE / LRE','分布关系匹配','Soman、Misra（1992）/ Park（2017）：分数、评分与回归方向不同'],['MDM-0.1','尺度一致性与梯度定位','Xie、Wu、Yang（2023）：伪尺度离散与δ=0.1定位'],['MM','统计关系匹配与反演','Cran（1988）：Weibull矩及矩差显式恢复']],sectionKey:'## 9'});
low('共同样本使性能差异对应方法构造与求解约定',{type:'table',section:'实验设置',widths:[260,890],rows:[['项目','本轮设置'],['总体参数','η=1000，γ=500；β=1.5、2、2.5、3、3.5、4、4.5、5'],['样本量','n=50、20、15、10、7'],['重复抽样','每个条件1200组；七种方法使用相同样本'],['精度图','七法共同有效样本；形状RMSE/β，尺度和位置RMSE/1000'],['分布与返回','分布用各法自身有效结果；有效率按全部1200次尝试统计']],sectionKey:'## 1'});
for(const n of [50,20,15,10,7]) low('样本减少时，各方法的误差增幅不同',{section:`样本量变化　n=${n}`,rose:true,...fig(`RMSE玫瑰图_n${n}_八档β.png`,'蓝：形状；橙：尺度；绿：位置。五页共用线性半径；MM数值见备页。'),sectionKey:'### 2.1',notesExtra:'五页按n=50、20、15、10、7连续切换。观察扇区的长度和相对距离，不逐项报数值。'});
low('较大β下，方法间差距呈现扩大与缩小并存',{section:'样本量与方法差距',...fig('方法差距变化_轨迹与50到7联合图.png','纵向比较相同方法对随n的变化；上：β=1.5，下：β=5。',{crop:[0,0,1,0.635]}),sectionKey:'### 2.1'});
low('误差上升并不意味着方法间距离同步扩大',{section:'方法差距的变化',...fig('方法差距变化_轨迹与50到7联合图.png','颜色为n=7与n=50的方法对距离之差；红色扩大、蓝色缩小，不表示优劣排序。',{crop:[0,0.65,1,1]}),sectionKey:'### 2.1'});
for(const b of [1.5,2,2.5,3,3.5,4,4.5,5]) low('形状条件改变时，估计分布的偏移与形态也改变',{section:`形状条件变化　β=${b}`,...fig(b===5?'修订_估计值分布_两档n.png':`估计值分布_β${b}_两档n.png`,'行：n=50、7；列：形状、尺度、位置。虚线为真值，红点为均值，横线为四分位区间。'),sectionKey:'### 2.2',notesExtra:'八页依β递增连续切换。重点观察分布展宽、参数偏移方向和零边界聚集。不将原图的双峰外观认定为两个内部估计群体。'});
low('样本量减少时，明显异常估计更加常见',{section:'明显异常估计',...fig('07_形状异常频率.png','异常判据：β̂≤β/3或β̂≥3β；频率以各法自身有效结果为分母，失败另计。'),sectionKey:'### 2.3'});
low('误差增长、参数偏移与异常增多需要分别解释',{type:'text',section:'主要现象',items:[['n减小','估计误差总体增大，但各方法的增幅不同。'],['β增大','三个参数出现不同方向的偏移、展宽和边界聚集。'],['明显异常','小样本下更常见，但程度与方向因方法和参数条件而异。']],sectionKey:'### 2.4'});
low('同一组观测减少后，不同方法的三参数误差增幅不同',{section:'机制一：样本减少',...fig('31_删点前后_样本474.png','W(5,1000,500)：从同一组50个观测中随机保留7个；空心点为删点前、实心点为删点后。'),sectionKey:'### 3.1'});
low('下端观测被移除后，三种定位依据的移动程度不同',{section:'机制一：样本减少',...fig('31A_固定形状定位判据_样本474.png','同一删点路径474：最小值、梯度阈值交点与匹配误差最低点向右移动，幅度不同。'),sectionKey:'### 3.1'});
low('定位变化继续传递到形状与尺度的恢复',{section:'机制一：参数恢复',...fig('31_参数恢复过程_样本474.png','MDM的标准差最低点向较低形状移动；LSE回归斜率增大、截距降低，形状与尺度随之降低。'),sectionKey:'### 3.1'});
low('较大β使有限样本的最小观测更远离真实起点',{section:'机制二：形状条件',minimum:true,...fig('R00_图2_样本与真实起点.png','Research00报告1；η=1000、γ=500，β=2与5。上：n=7抽样；下：最小值理论密度。'),sectionKey:'### 3.2'});
low('起点附近缺少观测时，不同参数组合仍可相容',{section:'机制二：形状条件',...fig('R00_图3_参数组合与样本相容.png','两条CDF在样本覆盖区间接近；说明有限样本的参数相容性，不意味着必然选中某一组。'),layout:'side',items:['观测主要覆盖分布中部','位置参数需要从较远处外推','仍需追踪方法准则选择了哪组参数'],sectionKey:'### 3.2'});
low('位置选得偏高可沿恢复关系传递为形状和尺度偏低',{section:'机制二：方向性偏移',...fig('R00_MDM_位置形状尺度传递.png','MDM-0.1：先看梯度交点，再沿同一位置读形状和尺度；此处放大β=5一列。',{crop:[0.50,0,1,1]}),triptych:true,layout:'side',items:['梯度阈值可能在较高位置相交','较高位置改变各点到起点的距离','条件形状与恢复尺度随之降低'],sectionKey:'### 3.2'});
low('匹配准则与位置约束共同形成零边界聚集',{section:'机制二：边界聚集',...fig('R00_报告2_LSE零边界.png','左移位置能改善部分样本的线性匹配；在γ≥0约束下，准则最低点可落于γ=0。'),sectionKey:'### 3.2'});
low('样本点列改变后，更好的线性匹配仍可给出异常参数',{section:'机制三：LSE异常',...fig('R00_报告2_LSE_right.png','Research00报告2：位置右移改善点列匹配，回归斜率增大，取倒数后形状明显降低。'),sectionKey:'### 3.3'});
low('方程残差接近零并不保证参数接近真值',{section:'机制三：WMLE异常',...fig('R00_报告2_WMLE_low.png','异常样本使两条方程的共同交点移向高位置、低形状；返回参数仍满足估计方程。'),sectionKey:'### 3.3'});
low('数值停止与候选接受也可能造成异常返回',{section:'机制三：计算来源',...fig('R00_报告2_MLE_stop.png','历史旧MLE案例：停止点右侧仍可提高似然。本轮已更新求解器，不据此认定新版仍有同一缺陷。'),sectionKey:'### 3.3'});
low('成功结果的精度与全部尝试的有效率应同时评价',{section:'估计风险',...fig('06_有效率.png','有效率的分母为全部1200次尝试。少数极端值可主导RMSE，求解失败另行统计。'),sectionKey:'### 4.1'});
low('评价目标改变后，方法的相对表现也改变',{section:'评价目标与选择',...fig('v04_06_寿命目标及候选差距.png','格内为最低RMSE方法，下行为第二名高出的比例。B10、B1分别为10%、1%失效分位寿命。'),bottomText:'B10的最低RMSE方法随n与β变化；B1在多数条件下为MDM。名次还需结合差距幅度与风险。',sectionKey:'### 4.2'});
low('方法选择取决于目标、已知条件与风险要求',{type:'table',section:'条件性选择依据',widths:[285,865],rows:[['已知条件或使用要求','应优先关注的性能'],['知道n，β范围未知','在给定参考范围内评价整体表现，保留稳健候选'],['知道n及β的大致范围','缩小比较区域，核对优势幅度及其稳定性'],['关心参数或低失效寿命','按具体目标评价，不能直接沿用另一个指标的排序'],['对异常和失败敏感','同时考察极端误差、异常频率与有效返回情况']],sectionKey:'### 4.2'});
low('后续将探索基于样本特征的自适应选择与求解优化',{type:'closing',section:'后续研究与平台',items:[['研究方向','根据可观测样本特征与使用目标选择方法，优化过程量和求解过程。'],['验证要求','在新的样本上检验选择规则的收益。'],['weibull.work','已有部分方法可在线调用，平台仍在建设，欢迎试用与交流。']],sectionKey:'## 5'});
// Uncropped comparison figures and supplementary cases remain available as hidden backup slides.
for(const n of [50,20,15,10,7])low('完整RMSE图保留MM数值与统一半径',{section:`备页：n=${n}`,backup:true,...fig(`RMSE玫瑰图_n${n}_八档β.png`),sectionKey:'### 2.1'});
low('最小值与真实起点的距离同时随n与β变化',{section:'备页：最小观测完整图',backup:true,...fig('R00_图2_样本与真实起点.png'),sectionKey:'### 3.2'});
low('MDM的梯度定位影响形状与尺度的恢复',{section:'备页：MDM完整诊断图',backup:true,...fig('R00_MDM_位置形状尺度传递.png'),sectionKey:'### 3.2'});
low('误差增大可以伴随波动减小与偏差加重',{type:'table',section:'备页：Bias与SD',backup:true,widths:[210,300,300,340],rows:[['WMLE，β=5','形状Bias','形状SD','形状RMSE'],['n=10','−2.263','0.982','2.466'],['n=7','−2.614','0.713','2.710']],bottomText:'七法共同有效结果。SD下降不等于估计更准确；这里负偏差加重，RMSE仍上升。',sectionKey:'### 2.1'});
low('同一总体与样本量仍可能返回差异很大的估计',{type:'table',section:'备页：异常样本示例',backup:true,widths:[460,230,230,230],rows:[['β=5、n=7，LSE','形状','尺度','位置'],['真值','5','1000','500'],['第34组：接近真值的例子','5.55','836.77','681.73'],['第0组：明显低估的例子','1.24','282.98','1205.95']],bottomText:'两例用于展示偏离程度；异常发生频率由1200次重复试验单独统计。',sectionKey:'### 2.3'});

// The institutional header carries the chapter, while the blue band carries the slide's takeaway.
for(const [i,p] of plan.entries()){
 p.chapter=p.backup?'附录　补充结果与案例':p.type==='cover'?'封面':p.section==='研究背景'?'01　研究背景':p.source===UP?'02　参数估计方法的原理与联系':p.sectionKey==='## 1'?'03　比较实验设置':p.sectionKey?.startsWith('### 2.')?'04　估计性能的差异与变化':p.sectionKey?.startsWith('### 3.')?'05　性能变化的机制解释':p.sectionKey?.startsWith('### 4.')?'06　评价目标与方法选择':'07　后续研究与平台';
 p.condition=p.rose?`n=${p.section.match(/n=(\d+)/)?.[1]}`:p.section.startsWith('形状条件变化')?p.section.match(/β=[\d.]+/)?.[0]:null;
}

export async function prepare(){
 await fs.mkdir(path.join(TMP,'assets'),{recursive:true});
 const template=await fs.access(path.join(ROOT,'ppt.pptx')).then(()=>path.join(ROOT,'ppt.pptx')).catch(()=>path.join(ROOT,'其他/历史版本/PPT原始模板-2026-10-23.pptx'));
 const original=await PresentationFile.importPptx(await FileBlob.load(template));
 const proto=original.toProto();
 for (const [idx,name] of [[0,'cover-background.png'],[1,'body-background.png']]) {
  const data=structuredClone(proto);data.slides=[data.slides[idx]];data.slides[0].index=0;
  data.slides[0].elements=idx===1?[]:data.slides[0].elements.filter(e=>!e.paragraphs?.some(p=>p.runs?.some(r=>r.text)));
  const deck=Presentation.load(data);
  const blob=await deck.export({slide:deck.slides.items[0],format:'png',scale:1});
  await fs.writeFile(path.join(TMP,'assets',name),new Uint8Array(await blob.arrayBuffer()));
 }
 for (const file of new Set(plan.filter(p=>p.image).map(p=>p.image))) {
  if(file.endsWith('.svg'))await sharp(path.join(ROOT,file)).png().toFile(path.join(TMP,'assets',path.basename(file).replace('.svg','.png')));
 }
 return {template,templateSha256:sha(await fs.readFile(template))};
}
function textbox(slide,text,box,size=26,color=BLACK,bold=false,align='left'){
 const sh=slide.shapes.add({geometry:'textbox',name:text.slice(0,35),position:box,fill:'none',line:{fill:'none',width:0}});
 sh.text=text; sh.text.style={fontSize:size,typeface:'Microsoft YaHei',color,bold,alignment:align,verticalAlignment:'middle',wrap:'square',autoFit:'none',insets:0};return sh;
}
async function addImage(slide,file,box,crop){
 let img=file.startsWith(TMP)?file:file.endsWith('.svg')?path.join(TMP,'assets',path.basename(file).replace('.svg','.png')):path.join(ROOT,file);
 if(crop){
  const bytes=await fs.readFile(img);const m=await sharp(bytes).metadata();const [x0,y0,x1,y1]=crop;
  const data=await sharp(bytes).extract({left:Math.round(m.width*x0),top:Math.round(m.height*y0),width:Math.round(m.width*(x1-x0)),height:Math.round(m.height*(y1-y0))}).png().toBuffer();
  return slide.images.add({blob:new Uint8Array(data),contentType:'image/png',alt:file+'（局部放大，数据未改变）',position:box,fit:'contain'});
 }
 return slide.images.add({blob:new Uint8Array(await fs.readFile(img)),contentType:'image/png',alt:path.basename(file),position:box,fit:'contain'});
}
function table(slide,rows,widths,top=188,height=420){
 const tb=slide.tables.add({rows:rows.length,columns:rows[0].length,left:65,top,width:1150,height,columnWidths:widths,values:rows});
 const all=tb.cells.block({row:0,column:0,rowCount:rows.length,columnCount:rows[0].length});
 all.assign({fill:'#FFFFFF',textStyle:{fontSize:24,typeface:'Microsoft YaHei',color:BLACK},margins:{left:13,right:13,top:10,bottom:10},anchor:'center'});
 tb.borders.assign({fill:'#C8D1DC',width:0.8,style:'solid'});
 for(let c=0;c<rows[0].length;c++){const ce=tb.getCell(0,c);ce.fill=BLUE;ce.text.style={fontSize:24,bold:true,color:'#FFFFFF',typeface:'Microsoft YaHei'};}
 return tb;
}
export async function populate(presentation,start=0,end=plan.length){
 if(start===0)presentation.slides.keep([]); presentation.theme.defaultFont='Microsoft YaHei';
 for(let i=start;i<Math.min(end,plan.length);i++){
  const p=plan[i];const slide=presentation.slides.add({width:1280,height:720});slide.hidden=!!p.backup;
  await addImage(slide,path.join(TMP,'assets',p.type==='cover'?'cover-background.png':'body-background.png'),{left:0,top:0,width:1280,height:720});
  if(p.type==='cover'){
   textbox(slide,'小样本三参数Weibull参数估计方法\n的比较与选择',{left:70,top:215,width:1140,height:150},48,'#FFFFFF',true,'center');
   textbox(slide,'魏鹏宇　谢里阳　陈鉴朋　孙伟侨',{left:220,top:450,width:840,height:42},29,BLACK,false,'center');
   textbox(slide,'报告人：魏鹏宇',{left:300,top:503,width:680,height:40},28,BLACK,false,'center');
   textbox(slide,'东北大学机械工程与自动化学院',{left:240,top:553,width:800,height:36},24,BLACK,false,'center');
   textbox(slide,'2026年10月25日',{left:380,top:609,width:520,height:36},25,BLACK,false,'center');
  }else{
   textbox(slide,p.chapter,{left:52,top:34,width:920,height:36},23,BLACK);
   textbox(slide,p.title,{left:54,top:90,width:1175,height:48},p.title.length>34?29:32,'#FFFFFF',true);
   if(p.condition)textbox(slide,p.condition,{left:1080,top:90,width:145,height:48},28,'#FFFFFF',true,'right');
   textbox(slide,String(i+1).padStart(2,'0'),{left:1180,top:694,width:60,height:20},15,GRAY,false,'right');
   if(p.type==='table'){
    const h=Math.min(440,p.rows.length*61);table(slide,p.rows,p.widths,185,h);
    if(p.bottomText)textbox(slide,p.bottomText,{left:65,top:185+h+20,width:1150,height:60},23,BLUE);
   }else if(p.type==='text'||p.type==='closing'){
    p.items.forEach(([head,body],j)=>{
     textbox(slide,head,{left:75,top:194+j*143,width:1100,height:38},30,BLUE,true);
     textbox(slide,body,{left:75,top:238+j*143,width:1100,height:65},28,BLACK);
    });
   }else if(p.rose){
    // Remove the repeated numeric MM rows only in the presentation view; the full originals remain in backup slides.
    await addImage(slide,p.image,{left:125,top:152,width:1030,height:245},[0,0.014,1,0.385]);
    await addImage(slide,p.image,{left:125,top:399,width:1030,height:245},[0,0.517,1,0.891]);
   }else if(p.minimum){
    await addImage(slide,p.image,{left:55,top:157,width:1170,height:275},[0,0,1,0.245]);
    await addImage(slide,p.image,{left:55,top:436,width:1170,height:190},[0,0.752,1,1]);
   }else if(p.triptych){
    const edges=[[0.50,0,1,0.333],[0.50,0.333,1,0.666],[0.50,0.666,1,1]];
    for(let j=0;j<3;j++){
     await addImage(slide,p.image,{left:42+j*402,top:185,width:392,height:350},edges[j]);
     textbox(slide,p.items[j],{left:58+j*402,top:550,width:355,height:76},24,j===0?BLUE:BLACK,j===0);
    }
   }else if(p.layout==='side'){
    await addImage(slide,p.image,{left:46,top:157,width:790,height:500},p.crop);
    p.items.forEach((t,j)=>textbox(slide,t,{left:865,top:200+j*125,width:350,height:90},27,j===0?BLUE:BLACK,j===0));
   }else{
    await addImage(slide,p.image,{left:42,top:156,width:1196,height:p.bottomText?420:492},p.crop);
    if(p.bottomText)textbox(slide,p.bottomText,{left:65,top:586,width:1150,height:55},23,BLUE);
   }
   if(p.caption)textbox(slide,p.caption,{left:55,top:650,width:1170,height:32},16,GRAY);
  }
  const md=p.source===UP?upper:lower;
  const notes=p.notes||section(md,p.sectionKey||'## 2');
  slide.speakerNotes.text=[notes,p.notesExtra||'',`来源：${path.join(ROOT,p.source)}${p.sectionKey?'；'+p.sectionKey:''}`,p.image?`图源：${path.join(ROOT,p.image)}`:'',`生成依据：报告上v2.3工作稿（v2.2审定基线） / 报告下v2.1；2026-10-23；演讲日期2026-10-25。`,i===0?'封面姓名依用户2026-10-23本轮指令：报告人魏鹏宇；另列谢里阳、陈鉴朋、孙伟侨。原报告内旧署名不因此改动。':''].filter(Boolean).join('\n\n');
 }
 const manifest={title:TITLE,created:'2026-10-23',talkDate:'2026-10-25',presenter:'魏鹏宇',otherNames:['谢里阳','陈鉴朋','孙伟侨'],sourceReports:[{file:UP,version:'2.3',status:'工作稿',baseline:'2.2',sha256:sha(upper)},{file:DOWN,version:'2.1',sha256:sha(lower)}],output:path.basename(FINAL),slideSize:[1280,720],total:plan.length,main:plan.filter(p=>!p.backup).length,backup:plan.filter(p=>p.backup).length,slides:plan.map((p,i)=>({page:i+1,title:p.title,section:p.section,chapter:p.chapter,condition:p.condition,backup:!!p.backup,source:p.source,sourceSection:p.sectionKey||'',figure:p.image||null,crop:p.crop||null,rose:!!p.rose,minimum:!!p.minimum}))};
 await fs.writeFile(path.join(import.meta.dirname,'版本与页码映射.json'),JSON.stringify(manifest,null,2)+'\n');
 return manifest;
}
export async function exportCandidate(presentation){
 const out=path.join(TMP,'candidate.pptx');await(await PresentationFile.exportPptx(presentation)).save(out);return out;
}
export {plan};
if(process.argv.includes('--build')){
 await prepare();const p=Presentation.create({slideSize:{width:1280,height:720}});const m=await populate(p);await exportCandidate(p);console.log(JSON.stringify({total:m.total,main:m.main,backup:m.backup,candidate:path.join(TMP,'candidate.pptx')}));
 if(process.argv.includes('--render')){
  await fs.mkdir(path.join(TMP,'render'),{recursive:true});
  for(let i=0;i<p.slides.items.length;i++){
   const slide=p.slides.items[i],stem=String(i+1).padStart(2,'0');
   const png=await p.export({slide,format:'png',scale:1});await fs.writeFile(path.join(TMP,'render',stem+'.png'),new Uint8Array(await png.arrayBuffer()));
   const layout=await slide.export({format:'layout'});await fs.writeFile(path.join(TMP,'render',stem+'.json'),new Uint8Array(await layout.arrayBuffer()));
   if((i+1)%10===0)console.log(`rendered ${i+1}/${p.slides.items.length}`);
  }
 }
}
