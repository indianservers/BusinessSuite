import fs from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
import {Workbook,SpreadsheetFile} from '@oai/artifact-tool';
const specs=JSON.parse(await fs.readFile(new URL('./import-catalog.json',import.meta.url),'utf8'));
const wb=Workbook.create();
const guide=wb.worksheets.add('Read me');
const instructions=[
 ['Business Suite import samples','Instructions'],
 ['Start here','Select the appropriate data worksheet in the import workspace. Import one worksheet at a time.'],
 ['Sample data only','Replace the example rows before using this workbook. IDs such as 1 are placeholders, not confirmed record IDs.'],
 ['Map columns first','Confirm suggested matches, fill required fields, and use fixed values for shared local IDs where appropriate.'],
 ['Preview and clean','Review all validation errors, cleaning suggestions and duplicate decisions. Correct values or return to mapping.'],
 ['Duplicates','Default: skip existing records. Supported master records can be updated. Transactions cannot be overwritten.'],
 ['Finish','Review the preview and confirm import. Import history records results and provides revoke / remap options.'],
 ['Revoke','Undo is blocked if imported records were later edited or have dependent records. No partial revoke is performed.'],
 ['Finance connectors','Connect QuickBooks Online or Zoho Books after administrator OAuth setup; fetched data goes through the same mapping and preview.'],
 ['Finance amounts','Outstanding bills must use the company base currency. No automatic currency conversion or journal posting.'],
 ['HR salary units','CTC is annual; Basic and HRA are monthly. Salary assignments are imported, not processed payslips.'],
 ['Required fields','See the field guide below. Empty optional sample cells may remain blank. Dates use YYYY-MM-DD.'],
 ['Module / worksheet','Required fields / import notes'],
 ...specs.map(s=>[`${s.module.toUpperCase()} / ${s.key}`,s.fields.filter(f=>f.required).map(f=>f.key).join(', ')+(s.note?' — '+s.note:'')]),
];
guide.getRangeByIndexes(0,0,instructions.length,2).values=instructions;
guide.getRange('A:A').format.columnWidth=32;
guide.getRange('B:B').format.columnWidth=112;
guide.getRangeByIndexes(0,0,instructions.length,2).format.wrapText=true;
guide.getRangeByIndexes(0,0,instructions.length,2).format.rowHeight=44;
guide.getRange('A1:B1').format.fill='#253858';
guide.getRange('A1:B1').format.font.color='#FFFFFF';
guide.getRange('A1:B1').format.font.bold=true;
guide.freezePanes.freezeRows(1);
for(const spec of specs){
 const sheet=wb.worksheets.add(`${spec.module}_${spec.key}`.slice(0,31));
 const headers=spec.fields.map(f=>f.key),values=spec.fields.map(f=>f.sample);
 sheet.getRangeByIndexes(0,0,1,headers.length).values=[headers];
 sheet.getRangeByIndexes(1,0,1,headers.length).values=[values];
 sheet.getRangeByIndexes(0,0,1,headers.length).format.fill='#253858';
 sheet.getRangeByIndexes(0,0,1,headers.length).format.font.color='#FFFFFF';
 sheet.getRangeByIndexes(0,0,1,headers.length).format.font.bold=true;
 sheet.getRangeByIndexes(0,0,2,headers.length).format.rowHeight=30;
 sheet.getRangeByIndexes(0,0,2,headers.length).format.columnWidth=25;
 sheet.getRangeByIndexes(1,0,1,headers.length).format.font.color='#1256A0';
 sheet.freezePanes.freezeRows(1);
 for(let i=0;i<spec.fields.length;i++)if(spec.fields[i].type==='number')sheet.getRangeByIndexes(1,i,1,1).setNumberFormat('0.00');
}
await wb.recalculate();
const output=await SpreadsheetFile.exportXlsx(wb);
await output.save(fileURLToPath(new URL('./business-suite-import-samples.xlsx',import.meta.url)));
const image=await wb.render({sheetName:'crm_leads',range:'A1:E2',scale:1.5,format:'png'});
await fs.writeFile(new URL('./template-preview.png',import.meta.url),new Uint8Array(await image.arrayBuffer()));
console.log(await wb.inspect({kind:'sheet',include:'id,name',maxChars:2000}));
