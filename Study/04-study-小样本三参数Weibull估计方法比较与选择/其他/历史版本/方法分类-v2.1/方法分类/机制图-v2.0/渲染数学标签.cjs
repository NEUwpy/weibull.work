// LaTeX -> MathML -> Times New Roman -> browser vector PDF.
const fs=require('fs'),path=require('path'),{chromium}=require('playwright'),katex=require('katex');
const input=JSON.parse(fs.readFileSync(process.argv[2],'utf8'));
const escape=s=>s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
const memo=new Map();
function markup(value){
 let out='',cursor=0,count=0;
 const re=/\\\(([\s\S]*?)\\\)|\$\$([\s\S]*?)\$\$|<br\s*\/?>|\r?\n/gi;
 for(const m of value.matchAll(re)){
  out+=escape(value.slice(cursor,m.index));cursor=m.index+m[0].length;
  if(m[1]!==undefined||m[2]!==undefined){
   const source=m[1]??m[2];
   const before=value.slice(0,m.index).split(/<br\s*\/?>|\r?\n/i).pop().trim();
   const after=value.slice(cursor).split(/<br\s*\/?>|\r?\n/i)[0].trim();
   const tex=(!before&&!after?'\\displaystyle ':'')+source;
   if(!memo.has(tex))memo.set(tex,katex.renderToString(tex,{output:'mathml',displayMode:false,throwOnError:true,strict:'error'}));
   out+=memo.get(tex);count++;
  }else out+='<br/>';
 }
 return {html:out+escape(value.slice(cursor)),count};
}

(async()=>{
 let browser;try{browser=await chromium.launch({headless:true});}catch{browser=await chromium.launch({headless:true,channel:'msedge'});}
 const report=[];
 try{
  const page=await browser.newPage();
  for(const task of input){
   const svg=fs.readFileSync(task.input,'utf8');
   const style=`@page{size:${task.width}px ${task.height}px;margin:0}html,body{margin:0;padding:0}svg{display:block}.label-box{box-sizing:border-box;width:100%;height:100%;display:flex;align-items:center;justify-content:center;font-family:"Times New Roman","Microsoft YaHei",serif;line-height:1.16}.label-content{width:100%;min-width:0;overflow-wrap:anywhere}.edge-label .label-content{width:max-content;white-space:nowrap;background:white;padding:1px 3px}math{font-family:"Times New Roman","Cambria Math",serif;font-size:1em}mi,mn,mtext{font-family:"Times New Roman","Microsoft YaHei",serif}`;
   await page.setContent('<!doctype html><meta charset="utf-8"><style>'+style+'</style>'+svg);
   const values=await page.locator('.label-content').evaluateAll(nodes=>nodes.map(n=>({id:n.dataset.cellId,value:n.dataset.source})));
   const compiled=[];let count=0;
   for(const value of values){
    try{const result=markup(value.value);compiled.push(result.html);count+=result.count;}
    catch(e){throw new Error(task.name+' / '+value.id+': '+e.message);}
   }
   const diagnostics=await page.evaluate(async compiled=>{
    const nodes=[...document.querySelectorAll('.label-content')];
    nodes.forEach((node,i)=>node.innerHTML=compiled[i]);
    // Avoid Unicode mathematical-alphanumeric substitution, which silently
    // changes Latin letters to another font. Preserve italic/bold via CSS.
    for(const token of document.querySelectorAll('math mi')){
     const variant=token.getAttribute('mathvariant')||'';
     if(!['','normal','italic','bold','bold-italic'].includes(variant)){
      // Blackboard/script symbols are mathematical glyphs, not prose Latin.
      // Keep their explicit LaTeX style instead of turning E or L into a
      // different symbol to force a font that does not contain that style.
      token.style.fontFamily='"Cambria Math","Times New Roman"';
      continue;
     }
     token.setAttribute('mathvariant','normal');
     token.style.fontFamily='"Times New Roman"';
     token.style.fontStyle=(variant==='normal'||variant==='bold'||(!variant&&token.textContent.length>1))?'normal':'italic';
     if(variant.includes('bold'))token.style.fontWeight='bold';
    }
    await document.fonts.ready;
    const result=[];
    for(const node of nodes){
     const fo=node.closest('foreignObject'),box=node.parentElement;
     const original=Number(node.dataset.fontSize);
     if(fo.dataset.edge==='true'){
      const rect=node.getBoundingClientRect(),w=rect.width+4,h=rect.height+4;
      fo.setAttribute('width',w);fo.setAttribute('height',h);
      fo.setAttribute('x',Number(fo.dataset.cx)-w/2);fo.setAttribute('y',Number(fo.dataset.cy)-h/2);
      continue;
     }
     const availW=Number(fo.getAttribute('width'))-Number(box.dataset.padX)*2;
     const availH=Number(fo.getAttribute('height'))-Number(box.dataset.padY)*2;
     let size=original;
     for(let i=0;i<4;i++){
      const widest=Math.max(node.scrollWidth,...[...node.querySelectorAll('math')].map(m=>m.getBoundingClientRect().width),1);
      const tallest=node.scrollHeight;
      const ratio=Math.min(availW/widest,availH/tallest,1);
      if(ratio>=.995)break;
      size*=ratio*.99;box.style.fontSize=size+'px';
     }
     result.push({id:node.dataset.cellId,original,size:Number(size.toFixed(2)),height:node.scrollHeight,available:availH});
    }
    return result;
   },compiled);
   await page.pdf({path:task.pdf,preferCSSPageSize:true,printBackground:true});
   report.push({name:task.name,formulas:count,labels:diagnostics});
  }
 }finally{await browser.close();}
 fs.writeFileSync(process.argv[3],JSON.stringify({engine:'KaTeX MathML / Chromium',font:'Times New Roman',figures:report},null,2));
 console.log(`typeset ${report.length} diagrams, ${report.reduce((n,r)=>n+r.formulas,0)} math occurrences`);
})().catch(e=>{console.error(e);process.exit(1)});
