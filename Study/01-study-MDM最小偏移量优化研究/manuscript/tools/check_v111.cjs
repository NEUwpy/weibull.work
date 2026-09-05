const fs=require('node:fs');
const path=require('node:path');
const crypto=require('node:crypto');
const root=path.resolve(__dirname,'..');
const sha=b=>crypto.createHash('sha256').update(b).digest('hex');
(async()=>{
 const {unified}=await import('unified');
 const {default:parse}=await import('remark-parse');
 const {default:math}=await import('remark-math');
 const {default:gfm}=await import('remark-gfm');
 const katex=require('katex');

 const unchanged=[];
 for(const [oldName,newName] of [['shelve/正文/Study01论文初稿-v1.10.md','Study01论文初稿-v1.11.md'],['shelve/附录/Study01论文附录-v1.8.md','Study01论文附录-v1.9.md']]){
  const old=fs.readFileSync(path.join(root,oldName),'utf8').replace(/\r\n/g,'\n');
  const current=fs.readFileSync(path.join(root,newName),'utf8').replace(/\r\n/g,'\n');
  const counts={};
  for(const [name,pattern] of Object.entries({table_rows:/^\|.*$/gm,references:/^\[\d+\].*$/gm,display_equations:/^\$\$\n[\s\S]*?\n\$\$/gm})){
   const a=old.match(pattern)||[],b=current.match(pattern)||[];
   if(JSON.stringify(a)!==JSON.stringify(b))throw Error('Changed '+newName+' '+name);
   counts[name]=b.length;
  }
  unchanged.push({file:newName,...counts});
 }
 const reports=[];
 for(const name of ['Study01论文初稿-v1.11.md','Study01论文附录-v1.9.md']){
  const source=fs.readFileSync(path.join(root,name),'utf8');
  const tree=unified().use(parse).use(math).use(gfm).parse(source);
  const ranges=[],errors=[],links=[];let inline=0,display=0;
  function visit(n){
   if(n.type==='math'||n.type==='inlineMath'){
    n.type==='math'?display++:inline++;
    ranges.push([n.position.start.offset,n.position.end.offset]);
    try{katex.renderToString(n.value,{displayMode:n.type==='math',throwOnError:true,strict:'error'});}
    catch(e){errors.push({line:n.position.start.line,message:e.message});}
   }
   if((n.type==='image'||n.type==='link')&&n.url&&!/^(?:https?:|#|mailto:)/.test(n.url)){
    const resolved=path.resolve(root,decodeURIComponent(n.url.split('#')[0]));
    if(!fs.existsSync(resolved))errors.push({line:n.position.start.line,missing:n.url});
    links.push(n.url);
   }
   for(const child of n.children||[])visit(child);
  }visit(tree);
  let residual=source;
  for(const [a,b] of ranges.sort((a,b)=>b[0]-a[0]))residual=residual.slice(0,a)+' '.repeat(b-a)+residual.slice(b);
  for(const [i,line] of residual.split('\n').entries()){
   if(/(?<!\\)\$|\\(?:beta|eta|gamma|frac|mathrm|%|_)|!\[\[/.test(line))errors.push({line:i+1,residual:line});
  }
  if(errors.length)throw Error(JSON.stringify({name,errors}));
  reports.push({file:name,inline_math:inline,display_math:display,math_errors:0,local_links_checked:links.length,missing_links:0,residual_math_delimiters:0});
 }
 const result={scope:'Annotation cleanup and explanation placement',unchanged,reports};
 fs.writeFileSync(path.join(root,'shelve/修订记录/revision-v1.11-qa.json'),JSON.stringify(result,null,2)+'\n');
 console.log(JSON.stringify(result,null,2));
})().catch(e=>{console.error(e);process.exitCode=1});
