import {Workbook} from '@oai/artifact-tool';
const workbook=Workbook.create();workbook.worksheets.add('样本');
console.log(workbook.help('workbook.render',{include:'index,examples,notes',maxChars:4200}).ndjson);
