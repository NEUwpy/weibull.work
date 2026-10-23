import fs from 'node:fs/promises';
import path from 'node:path';
import crypto from 'node:crypto';
import {pathToFileURL} from 'node:url';
import {ROOT,TMP,FINAL,plan} from './生成PPT.mjs';
const SKILL='C:/Users/36089/.codex/plugins/cache/openai-primary-runtime/presentations/26.1022.11436/skills/presentations';
const PY='C:/Users/36089/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe';
process.env.RUNTIME_NODE_MODULES ??= 'C:/Users/36089/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules';
const {finalizePresentation}=await import(pathToFileURL(path.join(SKILL,'container_tools/artifact_tool_utils.mjs')).href);
const source=await fs.access(path.join(ROOT,'ppt.pptx')).then(()=>path.join(ROOT,'ppt.pptx')).catch(()=>path.join(ROOT,'其他/历史版本/PPT原始模板-2026-10-23.pptx'));
const sourceSha=crypto.createHash('sha256').update(await fs.readFile(source)).digest('hex');
const tableOwners=plan.flatMap((p,i)=>p.type==='table'?[i+1]:[]);
const validationDir=path.join(TMP,'final',String(Date.now()));
await fs.mkdir(validationDir,{recursive:true});
const validated=path.join(validationDir,path.basename(FINAL));
const result=await finalizePresentation({
 workspaceDir:ROOT,candidatePath:path.join(TMP,'candidate.pptx'),finalPath:validated,
 explicitTotalSlideCount:plan.length,requiredNativeTableOwnerSlides:tableOwners,
 pythonExecutable:PY,
 integrityValidatorPath:path.join(SKILL,'container_tools/inspect_presentation_package_integrity.py'),
 layoutValidatorPath:path.join(SKILL,'container_tools/inspect_presentation_layout_geometry.py'),
 layoutArgs:['--expected-slide-size-emu','12192000,6858000','--validate-bullet-geometry','--validate-heading-fit',...tableOwners.flatMap(n=>['--require-native-table-slide',String(n)])],
 fontPolicy:{basis:'reference',families:['Microsoft YaHei'],referencePath:source,referenceSha256:sourceSha},
 verifyArtifactToolImport:true,receiptPath:path.join(TMP,'validation-'+path.basename(validationDir)+'.json'),
});
await fs.copyFile(validated,FINAL);
const manifestPath=path.join(import.meta.dirname,'版本与页码映射.json');
const manifest=JSON.parse(await fs.readFile(manifestPath,'utf8'));
manifest.template={file:'其他/历史版本/PPT原始模板-2026-10-23.pptx',sha256:sourceSha};
manifest.outputSha256=crypto.createHash('sha256').update(await fs.readFile(FINAL)).digest('hex');
await fs.writeFile(manifestPath,JSON.stringify(manifest,null,2)+'\n');
console.log(JSON.stringify({output:FINAL,sha256:manifest.outputSha256,result}));
