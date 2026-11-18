const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const ts=require('typescript');
const source=fs.readFileSync('src/components/mobile/useMobileDraftGuard.ts','utf8');
const code=ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.CommonJS}}).outputText;

// Run the actual hook against modeled history events; live journeys are verified separately.
function setup(overrides={}){
 const listeners=new Map(),queue=[],exports={},confirmations=[];
 let routerEvents=0,discarded=0;
 const history={state:{idx:2},go(delta){queue.push(this.state.idx+delta);}};
 const options={enabled:true,dirty:true,guardHistory:true,draftKey:'task:1:draft',pending:()=>false,message:'Discard?',onDiscard(){discarded++;options.dirty=false;},confirmDiscard:confirm=>confirmations.push(confirm),...overrides};
 const react={useRef:value=>({current:value}),useCallback:fn=>fn,useLayoutEffect:fn=>fn(),useEffect:fn=>fn()};
 const context={exports,require:name=>{assert.equal(name,'react');return react;},window:{history,addEventListener:(name,fn)=>listeners.set(name,fn),removeEventListener(){}},document:{addEventListener(){},removeEventListener(){}}};
 vm.runInNewContext(code,context);
 exports.useMobileDraftGuard(options);
 function pop(index){history.state={idx:index};let stopped=false;listeners.get('popstate')?.({state:history.state,stopImmediatePropagation(){stopped=true;}});if(!stopped)routerEvents++;}
 function flush(){let count=0;while(queue.length){assert.ok(count++<10,'history restoration must settle');pop(queue.shift());}}
 return {options,pop,flush,history,confirmations,get discarded(){return discarded;},get routerEvents(){return routerEvents;}};
}

for(const target of [0,1,3,5]){
 const test=setup();test.pop(target);test.flush();
 assert.equal(test.history.state.idx,2,'restore original entry before asking');
 assert.equal(test.routerEvents,0,'keep editor mounted while deciding');
 assert.equal(test.confirmations.length,1);
 // Keep editing means not executing the discard callback.
 assert.equal(test.discarded,0);
 test.confirmations[0]();test.flush();
 assert.equal(test.history.state.idx,target,'discard resumes original Back/Forward distance');
 assert.equal(test.discarded,1);assert.equal(test.routerEvents,1);
}
const pending=setup({pending:()=>true});pending.pop(1);pending.flush();
assert.equal(pending.history.state.idx,2);assert.equal(pending.confirmations.length,0);assert.equal(pending.routerEvents,0);
const clean=setup({dirty:false});clean.pop(1);clean.flush();assert.equal(clean.history.state.idx,1);assert.equal(clean.routerEvents,1);assert.equal(clean.confirmations.length,0);
const unknown=setup();unknown.pop(undefined);unknown.flush();assert.equal(unknown.routerEvents,1);assert.equal(unknown.confirmations.length,0);
const optOut=setup({guardHistory:false});optOut.pop(1);optOut.flush();assert.equal(optOut.routerEvents,1);assert.equal(optOut.confirmations.length,0);
console.log('PASS: actual draft guard restores indexed Back/Forward, retains editor until decision, resumes exact distance after discard, blocks pending traversal and preserves clean/unknown/opt-out behavior');
