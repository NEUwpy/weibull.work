const fs = require('node:fs');
const path = require('node:path');
const { pathToFileURL } = require('node:url');
const { createRequire } = require('node:module');
const req = createRequire('D:/weibull/package.json');
const root = 'D:/weibull/Study/01-study-MDM最小偏移量优化研究/manuscript';
(async () => {
 const {unified}=await import(pathToFileURL(req.resolve('unified')));
 const {default:parse}=await import(pathToFileURL(req.resolve('remark-parse')));
 const {default:math}=await import(pathToFileURL(req.resolve('remark-math')));
 const {default:gfm}=await import(pathToFileURL(req.resolve('remark-gfm')));
 const {default:rehype}=await import(pathToFileURL(req.resolve('remark-rehype')));
 const katex=req('katex');
 const parser=unified().use(parse).use(math).use(gfm);
 const escape=s=>String(s).replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;');
 function html(n){
  if(n.type==='root')return n.children.map(html).join('');
  if(n.type==='raw')return n.value;
  if(n.type==='text')return escape(n.value);
  if(n.type==='element'){
   const attrs=Object.entries(n.properties||{}).map(([k,v])=>' '+(k==='className'?'class':k)+'="'+escape(Array.isArray(v)?v.join(' '):v)+'"').join('');
   return '<'+n.tagName+attrs+'>'+(n.children||[]).map(html).join('')+(new Set(['img','br','hr','input']).has(n.tagName)?'':'</'+n.tagName+'>');
  }
  return '';
 }
 const out=path.join(root,'preview');fs.mkdirSync(out,{recursive:true});
 let css=fs.readFileSync(req.resolve('katex/dist/katex.min.css'),'utf8');
 const dist=path.dirname(req.resolve('katex/dist/katex.min.css'));
 css=css.replace(/url\(([^)]+)\)/g,(_,p)=>'url("'+pathToFileURL(path.join(dist,p.replace(/["']/g,''))).href+'")');
 const reports=[];
 for(const name of ['Study01论文初稿-v1.9.md','Study01论文附录-v1.8.md']){
  const source=fs.readFileSync(path.join(root,name),'utf8');
  const tree=parser.parse(source);let inline=0,block=0;const errors=[],ranges=[],long=[];
  function visit(n){
   if(n.type==='inlineMath'||n.type==='math'){
    const display=n.type==='math';display?block++:inline++;
    ranges.push([n.position.start.offset,n.position.end.offset]);
    if(!display && n.value.length>100)long.push(n.position.start.line);
    try{const rendered=katex.renderToString(n.value,{displayMode:display,throwOnError:true,strict:'error'});n.type='html';n.value=rendered;delete n.data;}
    catch(e){errors.push({line:n.position.start.line,error:e.message});}
   }else if(n.children)n.children.forEach(visit);
  }visit(tree);
  let outside=source;for(const [a,b] of ranges.sort((x,y)=>y[0]-x[0]))outside=outside.slice(0,a)+' '.repeat(b-a)+outside.slice(b);
  const residual=[];
  for(const [i,line] of outside.split('\n').entries())if(/(?<!\\)\$|\\(?:beta|eta|gamma|frac|mathrm|%|_)/.test(line))residual.push(i+1);
  if(errors.length||residual.length)throw Error(JSON.stringify({name,errors,residual}));
  const hast=await unified().use(rehype,{allowDangerousHtml:true}).run(tree);
  let body=html(hast);
  body=body.replace(/<img([^>]*?)src="([^"]+\.png)"([^>]*?)>/g,(all,a,src,b)=>{
   const svg=path.join(root,src.replace(/\.png$/,'.svg'));
   if(!fs.existsSync(svg))return all;
   const match=fs.readFileSync(svg,'utf8').match(/<svg[^>]*width="([0-9.]+)pt"/s);
   return match?'<img'+a+'src="'+src+'"'+b+' style="width:'+(Number(match[1])*25.4/72).toFixed(2)+'mm">':all;
  });const output=path.join(out,name.replace('.md','.html'));
  fs.writeFileSync(output,'<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><base href="'+pathToFileURL(root+'/').href+'"><title>'+escape(name)+'</title><style>'+css+'\nbody{margin:24px auto;padding:0 10mm;width:190mm;max-width:calc(100vw - 24mm);font:11pt/1.85 "Microsoft YaHei",sans-serif;color:#18232f}h1{font-size:18pt}h2{font-size:14pt;margin-top:28px}h3{font-size:12pt;margin-top:22px}p{text-align:justify}img{display:block;max-width:100%;height:auto;margin:16px auto}table{border-collapse:collapse;width:100%;font-size:9pt;line-height:1.6;border-top:1.2pt solid #26323e;border-bottom:1.2pt solid #26323e;font-variant-numeric:tabular-nums}td,th{padding:5px 6px;border:0;overflow-wrap:anywhere}thead{border-bottom:.6pt solid #26323e}th{font-weight:600}td[align=right],th[align=right]{text-align:right}code{overflow-wrap:anywhere;font-size:.9em}blockquote{color:#586471;border-left:3px solid #c8d0d8;padding-left:16px}.katex-display{margin:22px 0}.katex{font-size:1.08em}@media print{@page{size:A4;margin:10mm}body{margin:0;padding:0;max-width:none}thead{display:table-header-group}tr,img{break-inside:avoid}h1,h2,h3{break-after:avoid}}</style></head><body>'+body+'</body></html>');
  reports.push({file:name,inline_math:inline,display_math:block,katex_errors:errors,residual_delimiters_or_commands:residual,long_inline_lines:long,preview:path.relative(root,output)});
 }
 const {chromium}=require('C:/Users/36089/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
 const browser=await chromium.launch({headless:true,executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe'});
 const page=await browser.newPage({viewport:{width:1200,height:1000},deviceScaleFactor:1});
 for(const report of reports){
  await page.goto(pathToFileURL(path.join(root,report.preview)).href);
  await page.evaluate(()=>document.fonts.ready);
  report.rendered_math=await page.locator('.katex').count();
  report.rendered_errors=await page.locator('.katex-error').count();
  report.broken_images=await page.locator('img').evaluateAll(imgs=>imgs.filter(i=>!i.complete||i.naturalWidth===0).length);
  report.overflow=await page.evaluate(()=>Array.from(document.querySelectorAll('.katex-display,td,th')).filter(e=>e.scrollWidth>e.clientWidth+3).map(e=>e.textContent.slice(0,70)));
  if(report.rendered_math!==report.inline_math+report.display_math||report.rendered_errors||report.broken_images||report.overflow.length)throw Error(JSON.stringify(report));
  const stem=report.file.includes('初稿')?'main':'appendix';
  await page.screenshot({path:path.join(out,stem+'-top.png')});
  if(stem==='main')await page.getByRole('heading',{name:'2.2 偏移量的评价准则与选择参照'}).scrollIntoViewIfNeeded();
  else await page.getByRole('heading',{name:'B.5 逐参数误差的补充分布'}).scrollIntoViewIfNeeded();
  await page.screenshot({path:path.join(out,stem+'-equations.png')});
 }
 await browser.close();
 fs.writeFileSync(path.join(out,'math-render-check.json'),JSON.stringify({date:'2026-09-05',renderer:'remark-math + KaTeX; Chromium actual layout',reports},null,2)+'\n');
 console.log(JSON.stringify(reports,null,2));
})().catch(e=>{console.error(e);process.exitCode=1});
