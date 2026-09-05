const fs=require('node:fs'),path=require('node:path');
const {chromium}=require('C:/Users/36089/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const root=__dirname,stem='fig1_adaptive_selection';
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe'});
 const page=await browser.newPage({viewport:{width:1500,height:1000}});
 const xml=fs.readFileSync(path.join(root,stem+'.drawio'),'utf8');
 await page.route('http://127.0.0.1:8766/',r=>r.fulfill({contentType:'text/html',body:`<!doctype html><meta charset="utf-8"><style>html,body,iframe{margin:0;border:0;width:100%;height:100%;}</style><iframe src="https://embed.diagrams.net/?embed=1&proto=json&spin=1&ui=atlas&libraries=0&grid=0&pv=0&math=1"></iframe><script>window.messages=[];window.addEventListener('message',e=>{if(e.origin!=='https://embed.diagrams.net')return;try{const m=typeof e.data==='string'?JSON.parse(e.data):e.data;window.messages.push(m);}catch{}});window.send=m=>document.querySelector('iframe').contentWindow.postMessage(JSON.stringify(m),'https://embed.diagrams.net');</script>`}));
 await page.goto('http://127.0.0.1:8766/');
 await page.waitForFunction(()=>window.messages.some(m=>m.event==='init'),{},{timeout:60000});
 console.log('draw.io editor initialized');
 await page.evaluate(xml=>window.send({action:'load',xml,title:'Study01 Fig.1',autosave:0,fit:1,background:'#ffffff'}),xml);
 await page.waitForFunction(()=>window.messages.some(m=>m.event==='load'),{},{timeout:60000});
 // The editor loads MathJax asynchronously; wait for the actual formula DOM.
 const frame=page.frames().find(f=>f.url().startsWith('https://embed.diagrams.net'));
 await frame.waitForSelector('mjx-container, .MathJax, .MathJax_SVG, .MathJax_CHTML',{timeout:45000});
 console.log('Diagram loaded with rendered formulas');
 for(const format of ['xmlsvg','png']){
  await page.evaluate(format=>{window.messages=window.messages.filter(m=>m.event!=='export');window.send({action:'export',format,scale:format==='png'?2:1,border:20,background:'#ffffff',embedImages:true,embedFonts:true});},format);
  await page.waitForFunction(()=>window.messages.some(m=>m.event==='export'),{},{timeout:60000});
  const msg=await page.evaluate(()=>window.messages.find(m=>m.event==='export'));
  if(!msg.data)throw Error(JSON.stringify(msg));
  const comma=msg.data.indexOf(','),body=msg.data.slice(comma+1);
  const bytes=msg.data.slice(0,comma).includes('base64')?Buffer.from(body,'base64'):Buffer.from(decodeURIComponent(body));
  fs.writeFileSync(path.join(root,stem+(format==='png'?'.png':'.svg')),bytes);
  console.log('draw.io exported '+format+' ('+bytes.length+' bytes)');
 }
 await browser.close();
})().catch(e=>{console.error(e);process.exitCode=1;process.exit(1)});
