const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),ts=require('typescript');
function load(name){const source=fs.readFileSync(path.resolve(__dirname,'../src/apps/hrms/workbench/'+name),'utf8'),output=ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2021}}).outputText,mod={exports:{}};new Function('module','exports','require',output)(mod,mod.exports,require);return mod.exports;}
const {csvRows,previewBankResults}=load('bankResults.ts');
assert.deepEqual(csvRows('a,b\r\n"one,two","say ""yes"""\r\n'),[['a','b'],['one,two','say "yes"']]);
assert.throws(()=>csvRows('a\n"unclosed'),/Unclosed/);
const lines=[{employee_id:10,payroll_record_id:100,status:'Pending'},{employee_id:11,payroll_record_id:101,status:'Paid'}];
const preview=previewBankResults('payroll_record_id,employee_id,status,reference,failure_reason\n100,10,Paid,UTR-1,\n101,11,Paid,UTR-2,\n999,12,Failed,,Rejected\n100,10,Failed,,Duplicate',lines);
assert.equal(preview.valid.length,1);assert.equal(preview.errors.length,3);
assert.equal(preview.valid[0].line.utr_number,'UTR-1');
assert.match(preview.errors[0].error,/already recorded Paid/);assert.match(preview.errors[1].error,/No matching/);assert.match(preview.errors[2].error,/Duplicate/);
assert.equal(previewBankResults('employee_id,status,reference\n10,Paid,',lines).errors.length,1);
assert.equal(previewBankResults('employee_id,status,failure_reason\n10,Failed,Bank rejected',lines).valid[0].line.failure_reason,'Bank rejected');
assert.equal(previewBankResults('employee_id,status,reference\n10,Paid,UTR', [...lines,{employee_id:10,payroll_record_id:102,status:'Pending'}]).valid.length,0,'Ambiguous employees require a payroll record ID');
const memory=new Map();global.localStorage={getItem:k=>memory.get(k)??null,setItem:(k,v)=>memory.set(k,v),removeItem:k=>memory.delete(k)};
const {useHRWork,hrScope}=load('state.ts'),mine=hrScope(10,1),otherUser=hrScope(11,1),otherCompany=hrScope(10,2),store=useHRWork.getState();
store.pin(mine,{path:'/hrms/leave',label:'Leave'});store.visit(mine,{path:'/hrms/leave',label:'Leave'});store.context(mine,{month:'10',employee_id:'42'});
assert.equal(useHRWork.getState().scopes[mine].context.employee_id,'42');assert.equal(useHRWork.getState().scopes[otherUser],undefined);assert.equal(useHRWork.getState().scopes[otherCompany],undefined);
assert.deepEqual(load('state.ts').useHRWork.getState().scopes[mine].pins,[{path:'/hrms/leave',label:'Leave'}]);
console.log('PASS HR bank CSV parsing, matching, rejected rows, paid protection, favorites, context persistence and account/company isolation');
