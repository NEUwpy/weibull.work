const fs=require('fs'),path=require('path');
const {chromium}=require('C:/Users/36089/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
(async()=>{
 const browser=await chromium.launch({channel:'msedge',headless:true});
 for(const lang of ['zh','en']){
 const p=await browser.newPage({viewport:{width:1650,height:950}});const stem=path.join(__dirname,`study02-framework-${lang}`);
 await p.setContent('<iframe style="width:1600px;height:900px;border:0" id="editor"></iframe>');
 await p.evaluate(xml=>{window.events=[];window.addEventListener('message',e=>{try{const m=JSON.parse(e.data);window.events.push(m);if(m.event==='init')document.querySelector('iframe').contentWindow.postMessage(JSON.stringify({action:'load',xml,autosave:0}),'*')}catch{}});document.querySelector('iframe').src='https://embed.diagrams.net/?embed=1&proto=json&spin=1&ui=min&libraries=0';},fs.readFileSync(stem+'.drawio','utf8'));
 await p.waitForFunction(()=>events.some(e=>e.event==='load'),{},{timeout:60000});
 for(const format of ['svg','png']){
 await p.evaluate(format=>{window.events=[];document.querySelector('iframe').contentWindow.postMessage(JSON.stringify({action:'export',format,scale:2,border:15,transparent:false}),'*')},format);
 await p.waitForFunction(()=>events.some(e=>e.event==='export'),{},{timeout:60000});
 const event=await p.evaluate(()=>events.find(e=>e.event==='export'));if(!event.data)throw Error(JSON.stringify(event));
 const data=event.data;fs.writeFileSync(stem+'.'+format,data.startsWith('data:')?Buffer.from(data.split(',')[1],'base64'):data);
 }
 await p.close();
 const view=await browser.newPage({viewport:{width:1200,height:700}});
 const svg=fs.readFileSync(stem+'.svg','utf8');
 await view.setContent('<style>body{margin:0}svg{width:100%;height:auto;display:block}</style>'+svg);
 await view.evaluate(()=>document.fonts.ready);
 const area=await view.locator('svg').boundingBox();
 await view.locator('svg').screenshot({path:stem+'-paper-width.png'});
 await view.pdf({path:stem+'.pdf',width:'200mm',height:(200*area.height/area.width)+'mm',printBackground:true,margin:{top:0,bottom:0,left:0,right:0}});
 await view.close();console.log('Exported '+lang);
 }await browser.close();
})().catch(e=>{console.error(e);process.exit(1)});
