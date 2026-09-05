// Offline reading copies of the reviewed Markdown, with typeset mathematics.
const fs=require('fs'),path=require('path');
const repo=path.resolve(__dirname,'../../../..');
const {marked}=require(path.join(repo,'node_modules/marked'));
const katex=require(path.join(repo,'node_modules/katex'));
const manuscript=path.resolve(__dirname,'..');
const dest=path.join(manuscript,'reading-assets');fs.mkdirSync(dest,{recursive:true});
fs.copyFileSync(path.join(repo,'node_modules/katex/dist/katex.min.css'),path.join(dest,'katex.min.css'));
fs.copyFileSync(path.join(repo,'node_modules/katex/LICENSE'),path.join(dest,'LICENSE.katex.txt'));
fs.cpSync(path.join(repo,'node_modules/katex/dist/fonts'),path.join(dest,'fonts'),{recursive:true});
let rendered=[];
for(const [file,css] of [
 ['Study02论文初稿-v2.7.0.md','reading-assets/katex.min.css'],
 ['Study02论文附录-v2.7.0.md','reading-assets/katex.min.css'],
 ['submission/Study02-manuscript-v2.7.0-en.md','../reading-assets/katex.min.css'],
 ['submission/Study02-supplement-v2.7.0-en.md','../reading-assets/katex.min.css']]){
 const input=path.join(manuscript,file);let source=fs.readFileSync(input,'utf8'),math=[];
 source=source.replace(/\$\$([\s\S]*?)\$\$|\\\[([\s\S]*?)\\\]|\\\(([\s\S]*?)\\\)|(?<!\\)\$([^\n$]+?)\$/g,(all,a,b,c,d)=>{
  const i=math.length;math.push(katex.renderToString(a??b??c??d,{displayMode:a!==undefined||b!==undefined,throwOnError:true,strict:'ignore',trust:false}));return `ZZZMATHPLACEHOLDER${i}ZZZ`;
 });
 let html=marked.parse(source).replace(/ZZZMATHPLACEHOLDER(\d+)ZZZ/g,(_,i)=>math[Number(i)]);
 html=html.replace(/href="([^"#]+)\.md"/g,(all,p)=>/Study02.*v2\.7\.0/.test(p)?`href="${p}.html"`:all);
 const title=source.split('\n')[0].replace(/^# /,'');
 const page=`<!doctype html><html lang="${file.startsWith('submission')?'en':'zh-CN'}"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>${title}</title><link rel="stylesheet" href="${css}"><style>
 body{margin:0;background:#f4f3ef;color:#20252a;font:16px/1.75 Georgia,'Microsoft YaHei',serif}main{max-width:1160px;margin:32px auto;padding:48px 60px;background:white;border-top:5px solid #0072b2}h1{font-size:30px;line-height:1.4}h2{margin-top:2.2em;border-bottom:1px solid #ddd;padding-bottom:.25em}h3{margin-top:1.7em}p{margin:1em 0}table{border-collapse:collapse;width:100%;font:13px/1.5 Arial,'Microsoft YaHei',sans-serif;margin:22px 0}th,td{border-bottom:1px solid #ddd;padding:9px;text-align:left}th{background:#eef4f7}img{max-width:100%;height:auto}a{color:#006da8}blockquote{border-left:3px solid #aaa;padding-left:16px;color:#555}.katex-display{overflow-x:auto;overflow-y:hidden;padding:8px 0}.katex{font-size:1.08em}code{font-size:13px;overflow-wrap:anywhere}em{color:#46515a}small{display:block;color:#666;font:13px Arial,sans-serif}@media(max-width:800px){main{padding:24px 18px;margin:0}table{display:block;overflow:auto}}@media print{body{background:white}main{margin:0;padding:0;border:0}h2,h3{break-after:avoid}img,tr{break-inside:avoid}}
 </style><main><small>Study02 v2.7.0 · Reading copy generated from the editable manuscript</small>${html}</main></html>`;
 fs.writeFileSync(input.replace(/\.md$/,'.html'),page);rendered.push({file,equations:math.length});
}
console.log(JSON.stringify(rendered));
