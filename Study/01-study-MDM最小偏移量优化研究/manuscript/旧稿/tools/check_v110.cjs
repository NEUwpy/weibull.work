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
 const baseline=JSON.parse(fs.readFileSync(path.join(root,'revision-v1.10-baseline.json')));
 const before=fs.readFileSync(path.join(root,'Study01论文初稿-v1.9.md'));
 if(sha(before)!==baseline.source_sha256)throw Error('Previous manuscript changed');
 const appBefore=fs.readFileSync(path.join(root,'shelve/Study01论文附录-v1.8-正文v1.9配套.md'));
 const appNow=fs.readFileSync(path.join(root,'Study01论文附录-v1.8.md'),'utf8').replace(/\r\n/g,'\n');
 if(sha(appBefore)!==baseline.appendix_sha256)throw Error('Appendix snapshot changed');
 const appOld=appBefore.toString('utf8').replace(/\r\n/g,'\n');
 if(appOld.split('\n').filter((_,i)=>i!==2).join('\n')!==appNow.split('\n').filter((_,i)=>i!==2).join('\n'))throw Error('Appendix changes beyond version link');
 for(const [name,hash] of Object.entries(baseline.assets_sha256)){
  if(sha(fs.readFileSync(path.join(root,name)))!==hash)throw Error('Asset changed: '+name);
 }
 const old=before.toString('utf8').replace(/\r\n/g,'\n');
 const current=fs.readFileSync(path.join(root,'Study01论文初稿-v1.10.md'),'utf8').replace(/\r\n/g,'\n');
 const invariants={};
 for(const [name,pattern] of Object.entries({table_rows:/^\|.*$/gm,captions:/^\*\*(?:图|表) .*$/gm,images:/^!\[[^\[].*$/gm,references:/^\[\d+\].*$/gm,display_equations:/^\$\$\n[\s\S]*?\n\$\$/gm})){
  const a=old.match(pattern)||[],b=current.match(pattern)||[];
  if(JSON.stringify(a)!==JSON.stringify(b))throw Error('Changed '+name);
  invariants[name]=b.length;
 }
 const reports=[];
 for(const name of ['Study01论文初稿-v1.10.md','Study01论文附录-v1.8.md']){
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
 const result={date:'2026-09-05',scope:'Chinese argument and prose revision; no new experiments; no figure regeneration',source_sha256:baseline.source_sha256,main_sha256:sha(Buffer.from(current)),protected_assets:Object.keys(baseline.assets_sha256).length,appendix_body_unchanged:true,unchanged:invariants,reports};
 fs.writeFileSync(path.join(root,'revision-v1.10-qa.json'),JSON.stringify(result,null,2)+'\n');
 console.log(JSON.stringify(result,null,2));
})().catch(e=>{console.error(e);process.exitCode=1});
