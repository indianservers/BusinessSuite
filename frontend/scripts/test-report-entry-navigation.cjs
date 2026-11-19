const assert=require('node:assert/strict');
const fs=require('node:fs');
const ts=require('typescript');
const vm=require('node:vm');
const code=ts.transpileModule(fs.readFileSync('src/apps/srm/report-navigation.ts','utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2020}}).outputText;
const exportsObject={};vm.runInNewContext(code,{exports:exportsObject,URLSearchParams,Set});
const {reportEntry,reportHref}=exportsObject;
const entry=href=>reportEntry(new URL(href,'https://besterp.app').searchParams);
for(const report of ['overview','reconciliation','stock','customers','invoices','returns','profitability']){
 const href=reportHref(report);assert.equal(entry(href).report,report,`${report} must survive a new page load`);
}
assert.equal(entry(reportHref('stock',{low:true})).lowOnly,true);
assert.equal(entry(reportHref('reconciliation',{low:true})).lowOnly,true);
assert.equal(entry(reportHref('customers',{low:true})).lowOnly,false);
assert.equal(entry(reportHref('overview',{panel:'saved'})).saved,true);
assert.equal(entry(reportHref('overview',{panel:'summary'})).summary,true);
assert.equal(entry('/srm/reports?summary=latest').summary,true,'Existing notification links remain valid');
assert.equal(entry('/srm/reports?report=../../exports/1/download').report,'overview','Unrecognized paths cannot become API targets');
assert.equal(entry(reportHref('invalid')).report,'overview');
console.log('PASS: seven report reload links, low-stock links, both panels, legacy notifications and invalid-report fallback');
