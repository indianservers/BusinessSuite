const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const ts=require('typescript');
const source=ts.createSourceFile('review.tsx',fs.readFileSync('src/apps/project-management/components/BulkTaskCompletion.tsx','utf8'),ts.ScriptTarget.Latest,true,ts.ScriptKind.TSX);
let review;
function find(node){if(ts.isFunctionDeclaration(node)&&node.name?.text==='review')review=node;else ts.forEachChild(node,find);}
find(source);assert.ok(review,'actual review worker exists');
const code=ts.transpileModule(review.getText(source),{compilerOptions:{target:ts.ScriptTarget.ES2022}}).outputText;
function setup(count,ignoresAbort=false){
 const reads=[],pending=[],commits=[],phases=[];let choices=0;
 const context={AbortController,alive:{current:true},generation:{current:0},reviewAbort:{current:null},records:Array.from({length:count},(_,i)=>({id:i+1,title:`Task ${i+1}`,status:'To Do'})),setPhase:value=>phases.push(value),setRows:value=>commits.push(value),setError(){},setMustReview(){},workspaceError:error=>error.message,
  tasksAPI:{get(id,fresh,signal){reads.push({id,fresh,signal});return new Promise((resolve,reject)=>{pending.push(()=>resolve({id,title:`Task ${id}`,status:'To Do'}));if(!ignoresAbort)signal.addEventListener('abort',()=>reject(new Error('Read aborted')),{once:true});});}},
  api:{get:async(_path,options)=>{choices++;assert.ok(options.signal);return{data:{can_request:false,transitions:[],requests:[]}};}},taskStatusNeedsReview:()=>false};
 vm.createContext(context);vm.runInContext(code,context);
 return{context,reads,pending,commits,phases,get choices(){return choices;}};
}
(async()=>{
 const apiSource=ts.createSourceFile('api.ts',fs.readFileSync('src/apps/project-management/services/api.ts','utf8'),ts.ScriptTarget.Latest,true);
 let getter;
 function findGetter(node){if(ts.isVariableDeclaration(node)&&node.name.getText(apiSource)==='tasksAPI'&&ts.isObjectLiteralExpression(node.initializer)){getter=node.initializer.properties.find(property=>ts.isPropertyAssignment(property)&&property.name.getText(apiSource)==='get');}else ts.forEachChild(node,findGetter);}
 findGetter(apiSource);assert.ok(getter,'actual task read adapter exists');
 const transportCalls=[],transport={BASE_URL:'/project-management',api:{get:async(...args)=>{transportCalls.push(args);return{data:{id:99}};}}};
 vm.createContext(transport);vm.runInContext(ts.transpileModule(`this.getTask=${getter.initializer.getText(apiSource)}`,{compilerOptions:{target:ts.ScriptTarget.ES2022}}).outputText,transport);
 const controller=new AbortController();await transport.getTask(99,true,controller.signal);
 assert.equal(transportCalls[0][0],'/project-management/tasks/99');assert.equal(transportCalls[0][1].signal,controller.signal);assert.equal(transportCalls[0][1].recordCache,false);assert.equal(transportCalls[0][1]._recordSyncBypass,true);
 await transport.getTask(99);assert.equal(transportCalls[1][1],undefined,'legacy reads keep existing cache behavior');
 await transport.getTask(99,false,controller.signal);assert.equal(transportCalls[2][1].signal,controller.signal);
 const cancelled=setup(20);const work=cancelled.context.review();
 assert.equal(cancelled.reads.length,4,'review bounds concurrent reads');
 assert.ok(cancelled.reads.every(read=>read.fresh&&read.signal));
 cancelled.context.alive.current=false;cancelled.context.generation.current++;cancelled.context.reviewAbort.current.abort();await work;
 assert.equal(cancelled.reads.length,4,'unmount must not enqueue remaining records');assert.equal(cancelled.choices,0);assert.equal(cancelled.commits.filter(rows=>rows.length).length,0);assert.equal(cancelled.phases.at(-1),'loading','unmounted review must not publish idle');
 const late=setup(20,true);const lateWork=late.context.review();late.context.alive.current=false;late.context.generation.current++;late.context.reviewAbort.current.abort();late.pending.splice(0).forEach(resolve=>resolve());await lateWork;
 assert.equal(late.choices,0,'late task response must not start a projection read');assert.equal(late.reads.length,4);assert.equal(late.commits.filter(rows=>rows.length).length,0);
 const replacement=setup(4,true);const old=replacement.context.review();const oldReads=replacement.pending.splice(0);const fresh=replacement.context.review();oldReads.forEach(resolve=>resolve());await old;
 assert.equal(replacement.choices,0,'superseded review must not advance');assert.equal(replacement.commits.filter(rows=>rows.length).length,0);
 replacement.pending.splice(0).forEach(resolve=>resolve());await fresh;
 assert.equal(replacement.choices,4);assert.equal(replacement.commits.filter(rows=>rows.length).length,1);assert.equal(replacement.commits.at(-1).length,4);assert.equal(replacement.phases.at(-1),'idle');
 console.log('PASS: task adapter forwards abort signals without changing legacy reads; actual bulk review worker stops queued records after unmount, ignores late responses and only publishes the newest review');
})().catch(error=>{console.error(error);process.exitCode=1;});
