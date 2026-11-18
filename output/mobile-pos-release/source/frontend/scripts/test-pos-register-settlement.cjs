const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),ts=require('typescript');
const {QueryClient}=require('@tanstack/react-query');
const source=fs.readFileSync(require('node:path').join(__dirname,'../src/apps/srm/pages/SRMPOSPage.tsx'),'utf8');
const ast=ts.createSourceFile('pos.tsx',source,ts.ScriptTarget.Latest,true,ts.ScriptKind.TSX);
const helpers=ast.statements.filter(n=>ts.isFunctionDeclaration(n)&&['refreshSettledRegister','registerCashDisplay'].includes(n.name?.text)).map(n=>n.getText(ast)).join('\n');
const context=vm.createContext({});
vm.runInContext(ts.transpileModule(helpers,{compilerOptions:{target:ts.ScriptTarget.ES2022}}).outputText,context);
const {refreshSettledRegister,registerCashDisplay}=context;
async function main(){
 const client=new QueryClient({defaultOptions:{queries:{retry:false,gcTime:0}}}),key=['srm','pos-active-session','demo'];
 let oldSignal,releaseOld,reads=0;
 const stale=client.fetchQuery({queryKey:key,queryFn:({signal})=>{oldSignal=signal;return new Promise(resolve=>{releaseOld=resolve;});}}).catch(()=>undefined);
 await Promise.resolve();
 await refreshSettledRegister(client,key,async signal=>{assert.equal(signal.aborted,false);reads++;return {expected_cash:100};},()=>true);
 assert.equal(oldSignal.aborted,true);releaseOld({expected_cash:0});await stale;
 assert.equal(client.getQueryData(key).expected_cash,100);
 // Recovery rereads authority instead of adding the same payment a second time.
 await refreshSettledRegister(client,key,async()=>({expected_cash:100}),()=>true);
 assert.equal(client.getQueryData(key).expected_cash,100);
 await assert.rejects(refreshSettledRegister(client,key,async()=>{throw Error('offline');},()=>true));
 assert.equal(client.getQueryState(key).status,'error');
 assert.equal(registerCashDisplay(false,true,100,String),'Unavailable');
 assert.equal(registerCashDisplay(true,false,0,String),'Refreshing...');
 assert.equal(registerCashDisplay(false,false,100,String),'100');
 assert.equal(registerCashDisplay(false,false,NaN,String),'Unavailable');
 await refreshSettledRegister(client,key,async()=>{reads++;return {};},()=>false);assert.equal(reads,1);
 assert.match(source,/const registerCashReady = !activeRegister.isFetching && !activeRegister.isError/);
 assert.match(source,/const canCloseSession = registerCashReady/);
 assert.match(source,/refreshSettledRegister\(queryClient,registerQueryKey,readActiveRegister,owns\)\.catch\(\(\)=>undefined\)/);
 assert.match(source,/signal,recordCache:false/);client.clear();
 console.log('POS register settlement: race, recovery, failure display and scope guards passed');
}
main().catch(error=>{console.error(error);process.exitCode=1;});
