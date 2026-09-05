const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto');
const root=path.resolve(__dirname,'..');
const sha=p=>crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex');
(async()=>{
 const {unified}=await import('unified');
 const {default:parse}=await import('remark-parse');
 const {default:math}=await import('remark-math');
 const {default:gfm}=await import('remark-gfm');
 const katex=require('katex');
 const reports=[];
 for(const [oldName,newName] of [['shelve/正文/Study01论文初稿-v1.11.md','Study01论文初稿-v1.12.md'],['shelve/附录/Study01论文附录-v1.9.md','Study01论文附录-v1.10.md']]){
  const source=fs.readFileSync(path.join(root,newName),'utf8');
  const old=fs.readFileSync(path.join(root,oldName),'utf8').replace(/\]\(([^)]+)\)/g,(match,url)=>{if(/^(https?:|#|mailto:)/.test(url))return match;return ']('+path.relative(root,path.resolve(path.dirname(path.join(root,oldName)),url)).split(path.sep).join('/')+')';});
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
    if(!fs.existsSync(path.resolve(root,decodeURIComponent(n.url.split('#')[0]))))errors.push({missing:n.url});
    links.push(n.url);
   }
   for(const child of n.children||[])visit(child);
  }visit(tree);
  let residual=source;
  for(const [a,b] of ranges.sort((a,b)=>b[0]-a[0]))residual=residual.slice(0,a)+' '.repeat(b-a)+residual.slice(b);
  for(const [i,line] of residual.split('\n').entries())if(/(?<!\\)\$|\\(?:beta|eta|gamma|frac|mathrm|%|_)|!\[\[/.test(line))errors.push({line:i+1,residual:line});
  const captions=[...source.matchAll(/^\*\*(?:图|表) ([A-F]?\d+)  /gm)].map(x=>x[0]);
  if(new Set(captions).size!==captions.length)errors.push('Duplicate figure/table number');
  const refs=t=>(t.match(/^\[\d+\].*$/gm)||[]).map(x=>x.replace(/^\[\d+\]\s*/, '')).sort();
  if(JSON.stringify(refs(old))!==JSON.stringify(refs(source)))errors.push('Reference list changed');
  // All previously reported table blocks remain intact; only A4 is newly added.
  const tables=t=>t.replace(/\r\n/g,'\n').match(/^\|.*(?:\n\|.*)*/gm)||[];
  for(const table of tables(old))if(!tables(source).includes(table))errors.push('Existing table changed');
  if(errors.length)throw Error(JSON.stringify({newName,errors}));
  reports.push({file:newName,sha256:sha(path.join(root,newName)),inline_math:inline,display_math:display,
    math_errors:0,local_links:links.length,tables:tables(source).length,existing_tables_unchanged:true,reference_entries_unchanged:true});
 }
 const source=JSON.parse(fs.readFileSync(path.join(root,'figures/figure_sources.json'),'utf8'));
 let restored=0;
 for(const [file,info] of Object.entries(source.restored_3d_figures.exports)){
  if(sha(path.join(root,'figures',file))!==info.sha256)throw Error('Restored 3D asset changed: '+file);
  restored++;
 }
 const out={scope:'Focused offset mechanism revision; existing primary comparisons preserved',reports,restored_3d_assets_unchanged:restored};
 fs.writeFileSync(path.join(root,'shelve/修订记录/revision-v1.12-qa.json'),JSON.stringify(out,null,2)+'\n');
 console.log(JSON.stringify(out,null,2));
})().catch(e=>{console.error(e);process.exitCode=1});
