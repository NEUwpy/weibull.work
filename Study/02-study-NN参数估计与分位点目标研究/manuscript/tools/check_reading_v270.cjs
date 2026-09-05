// Inspect generated local reading copies with the bundled headless browser.
const fs=require('fs'),path=require('path'),{pathToFileURL}=require('url');
const playwright=require(process.env.STUDY02_PLAYWRIGHT);
const root=path.resolve(__dirname,'../..'),manuscript=path.join(root,'manuscript');
const out=path.join(root,'artifacts/manuscript_review_v270');fs.mkdirSync(out,{recursive:true});
(async()=>{
 const browser=await playwright.chromium.launch({channel:'msedge',headless:true});
 const page=await browser.newPage({viewport:{width:1440,height:1100}}),results=[];
 for(const file of ['Study02论文初稿-v2.7.0.html','Study02论文附录-v2.7.0.html','submission/Study02-manuscript-v2.7.0-en.html','submission/Study02-supplement-v2.7.0-en.html']){
  const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto(pathToFileURL(path.join(manuscript,file)).href);await page.evaluate(()=>document.fonts.ready);
  const result=await page.evaluate(()=>({
   images:[...document.images].map(i=>({source:i.getAttribute('src'),ok:i.complete&&i.naturalWidth>0})),
   math:document.querySelectorAll('.katex').length,tables:document.querySelectorAll('table').length,
   mathErrors:document.querySelectorAll('.katex-error').length,
   overflow:document.documentElement.scrollWidth>window.innerWidth
  }));
  if(errors.length||result.mathErrors||result.overflow||result.images.some(i=>!i.ok))throw Error(JSON.stringify({file,errors,result}));
  if(file.includes('初稿')){
   await page.screenshot({path:path.join(out,'reading-main-top.png')});
   await page.locator('table').first().screenshot({path:path.join(out,'reading-main-table.png')});
  }
  results.push({file,...result,errors});
 }
 await browser.close();fs.writeFileSync(path.join(out,'reading-qa.json'),JSON.stringify(results,null,2));console.log(JSON.stringify(results));
})().catch(e=>{console.error(e);process.exit(1)});
