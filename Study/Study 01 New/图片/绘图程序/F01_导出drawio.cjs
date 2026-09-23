// Export the authoritative draw.io composition through diagrams.net.
const fs=require('node:fs'),path=require('node:path');
const runtime=process.env.PLAYWRIGHT_MODULE || 'C:/Users/36089/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright';
const {chromium}=require(runtime);
const root=path.resolve(__dirname,'..'),stem='F01_MDM原理联图';
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:process.env.CHROME_PATH||'C:/Program Files/Google/Chrome/Application/chrome.exe'});
 try {
 const page=await browser.newPage({viewport:{width:1500,height:1600}});
 await page.route('http://127.0.0.1:8766/',r=>r.fulfill({contentType:'text/html',body:
 '<!doctype html><meta charset="utf-8"><style>html,body,iframe{margin:0;border:0;width:100%;height:100%;}</style><iframe src="https://embed.diagrams.net/?embed=1&proto=json&spin=1&ui=atlas&libraries=0&grid=0&pv=0&math=1"></iframe><script>window.messages=[];window.addEventListener("message",e=>{if(e.origin!=="https://embed.diagrams.net")return;try{window.messages.push(typeof e.data==="string"?JSON.parse(e.data):e.data);}catch{}});window.send=m=>document.querySelector("iframe").contentWindow.postMessage(JSON.stringify(m),"https://embed.diagrams.net");</script>'}));
 await page.goto('http://127.0.0.1:8766/');
 await page.waitForFunction(()=>window.messages.some(m=>m.event==='init'),{},{timeout:60000});
 await page.evaluate(xml=>window.send({action:'load',xml,title:'Study01 F01',autosave:0,fit:1,background:'#ffffff'}),fs.readFileSync(path.join(root,stem+'.drawio'),'utf8'));
 await page.waitForFunction(()=>window.messages.some(m=>m.event==='load'),{},{timeout:60000});
 const frame=page.frames().find(f=>f.url().startsWith('https://embed.diagrams.net'));
 await frame.waitForSelector('mjx-container, .MathJax, .MathJax_SVG, .MathJax_CHTML',{timeout:45000});
 for(const format of ['xmlsvg','png']){
  await page.evaluate(format=>{
   window.messages=window.messages.filter(m=>m.event!=='export');
   window.send({action:'export',format,scale:format==='png'?3:1,border:16,background:'#ffffff',embedImages:true,embedFonts:true});
  },format);
  await page.waitForFunction(()=>window.messages.some(m=>m.event==='export'),{},{timeout:60000});
  const msg=await page.evaluate(()=>window.messages.find(m=>m.event==='export'));
  if(!msg.data)throw Error(JSON.stringify(msg));
  const comma=msg.data.indexOf(','),body=msg.data.slice(comma+1);
  const bytes=msg.data.slice(0,comma).includes('base64')?Buffer.from(body,'base64'):Buffer.from(decodeURIComponent(body));
  fs.writeFileSync(path.join(root,stem+(format==='png'?'.png':'.svg')),bytes);
  console.log('Exported',format,bytes.length);
 }
 const svg=fs.readFileSync(path.join(root,stem+'.svg'),'utf8');
 const dims=svg.match(/viewBox="([\d.\s-]+)"/)[1].split(/\s+/).map(Number);
 const height=183*dims[3]/dims[2];
 const pdfPage=await browser.newPage();
 await pdfPage.setContent('<!doctype html><meta charset="utf-8"><style>@page{size:183mm '+height+'mm;margin:0}html,body{margin:0;padding:0}body>svg{display:block;width:183mm;height:'+height+'mm}</style>'+svg);
 await pdfPage.evaluate(()=>document.fonts.ready);
 await pdfPage.pdf({path:path.join(root,stem+'.pdf'),printBackground:true,preferCSSPageSize:true});
 const metadataPath=path.join(root,'数据',stem+'.json');
 const metadata=JSON.parse(fs.readFileSync(metadataPath,'utf8'));
 const png=fs.readFileSync(path.join(root,stem+'.png'));
 metadata.revision=12;
 metadata.export={source:stem+'.drawio',renderer:'diagrams.net embedded editor; PDF from exported SVG via Chromium',pdf_size_mm:[183,height],png_pixels:[png.readUInt32BE(16),png.readUInt32BE(20)],editable:'Native stage regions, labels, sample marks and arrows; four embedded scientific SVG panels'};
 for(const file of [stem+'.drawio','绘图程序/F01_组装drawio.py','绘图程序/F01_导出drawio.cjs']) {
   metadata.sha256[file]=require('node:crypto').createHash('sha256').update(fs.readFileSync(path.join(root,file))).digest('hex');
 }
 fs.writeFileSync(metadataPath,JSON.stringify(metadata,null,2)+'\n');
 console.log('Exported PDF',183,height);
 } finally {await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1});
