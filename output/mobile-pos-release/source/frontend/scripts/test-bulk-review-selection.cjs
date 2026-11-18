const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const ts=require('typescript');
const source=ts.createSourceFile('grid.tsx',fs.readFileSync('src/shared/data-grid/SharedDataGrid.tsx','utf8'),ts.ScriptTarget.Latest,true,ts.ScriptKind.TSX);
let action;
function find(node){if(ts.isFunctionDeclaration(node)&&node.name?.text==='runBulkAction')action=node;else ts.forEachChild(node,find);}
find(source);assert.ok(action,'actual grid action implementation exists');
const code=ts.transpileModule(action.getText(source),{compilerOptions:{target:ts.ScriptTarget.ES2022}}).outputText;
function setup(){
 const cleared=[],errors=[];let refreshed=0;
 const context={bulkBusy:undefined,selectedRecords:[{id:1},{id:2}],selection:['1','2'],window:{confirm:()=>true},setBulkBusy:value=>context.bulkBusy=value,setActionError:value=>errors.push(value),emitSelection:value=>cleared.push(value),request:{refetch:async()=>refreshed++},errorText:error=>error.message};
 vm.createContext(context);vm.runInContext(code,context);
 return{context,cleared,errors,get refreshed(){return refreshed;}};
}
(async()=>{
 const cancelled=setup();let settle;let calls=0;
 const pending=cancelled.context.runBulkAction({id:'review',run:()=>{calls++;return new Promise(resolve=>settle=resolve);}});
 assert.equal(cancelled.context.bulkBusy,'review');assert.equal(cancelled.cleared.length,0);
 await cancelled.context.runBulkAction({id:'review',run:()=>{calls++;}});assert.equal(calls,1,'one review at a time');
 settle(false);await pending;assert.equal(cancelled.cleared.length,0);assert.equal(cancelled.refreshed,0);assert.equal(cancelled.context.bulkBusy,undefined);
 const saved=setup();await saved.context.runBulkAction({id:'review',run:async()=>true});assert.equal(saved.cleared.length,1);assert.equal(saved.cleared[0].length,0);assert.equal(saved.refreshed,1);
 const failed=setup();await failed.context.runBulkAction({id:'review',run:async()=>{throw new Error('Review rejected');}});assert.equal(failed.cleared.length,0);assert.equal(failed.refreshed,0);assert.equal(failed.errors.at(-1),'Review rejected');
 const legacy=setup();await legacy.context.runBulkAction({id:'legacy',run:async()=>{}});assert.equal(legacy.cleared.length,1);assert.equal(legacy.refreshed,1);
 console.log('PASS: actual grid bulk action preserves selection until confirmed, keeps it on cancel/error, prevents duplicate review and retains legacy success behavior');
})().catch(error=>{console.error(error);process.exitCode=1;});
