// Build portable previews while retaining each equation's native MathType OLE data.
const fs = require('fs');
const path = require('path');
const manifest = process.argv[2] || path.resolve(__dirname, '../../../../../tmp/report1-word-20261012/manifest.json');
const config = JSON.parse(fs.readFileSync(manifest, 'utf8'));
const qa = config.qa;
const library = config.mathjax_library;
const {mathjax} = require(path.join(library, 'js/mathjax.js'));
const {TeX} = require(path.join(library, 'js/input/tex.js'));
const {SVG} = require(path.join(library, 'js/output/svg.js'));
const {liteAdaptor} = require(path.join(library, 'js/adaptors/liteAdaptor.js'));
const {RegisterHTMLHandler} = require(path.join(library, 'js/handlers/html.js'));
const {AllPackages} = require(path.join(library, 'js/input/tex/AllPackages.js'));
const sharp = require(require.resolve('sharp', {paths: [
  'C:/Users/36089/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules'
]}));
const adaptor = liteAdaptor();
RegisterHTMLHandler(adaptor);
const document = mathjax.document('', {
 InputJax: new TeX({packages: AllPackages}), OutputJax: new SVG({fontCache:'local'})
});

async function main() {
 const metrics = {};
 for (const job of config.jobs) {
  const html = adaptor.outerHTML(document.convert(job.tex, {display: job.display}));
  if (html.includes('data-mjx-error')) throw new Error('Invalid equation: '+job.marker);
  let svg = html.slice(html.indexOf('<svg'), html.lastIndexOf('</svg>')+6);
  const view = svg.match(/viewBox="([^"]+)"/)[1].trim().split(/\s+/).map(Number);
  const width = view[2]/1000*12;
  const height = view[3]/1000*12;
  const scale = Math.min(1, job.max_width_pt/width);
  const w = width*scale, h = height*scale;
  const pxw = Math.ceil(w*600/72), pxh = Math.ceil(h*600/72);
  svg = svg.replace(/width="[^"]+"/, 'width="'+pxw+'px"')
           .replace(/height="[^"]+"/, 'height="'+pxh+'px"')
           .replace(/currentColor/g, '#000000');
  await sharp(Buffer.from(svg)).png().toFile(path.join(qa, 'objects', job.marker+'.png'));
  metrics[job.marker] = {width_pt:w, height_pt:h};
 }
 fs.writeFileSync(path.join(qa, 'preview-metrics.json'), JSON.stringify(metrics, null, 2));
 process.stdout.write('Generated '+config.jobs.length+' previews; native MathType objects remain editable.\n');
}
main().catch(e=>{process.stderr.write(e.stack+'\n');process.exitCode=1});
