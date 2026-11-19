const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict'),Module=require('node:module'),ts=require('typescript'),React=require('react'),{renderToStaticMarkup}=require('react-dom/server');
const filename=path.resolve(__dirname,'../src/pages/auth/GoogleSignInFallback.tsx');
const compiled=ts.transpileModule(fs.readFileSync(filename,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,jsx:ts.JsxEmit.ReactJSX,target:ts.ScriptTarget.ES2020}}).outputText;
const mod=new Module(filename,module);mod.filename=filename;mod.paths=Module._nodeModulePaths(path.dirname(filename));mod._compile(compiled,filename);
const {googleSignInState:state,default:View}=mod.exports;
const base={firebaseEnabled:false,moduleCount:5,googleSso:false,pending:false,failed:false};
assert.equal(state({...base,pending:true}),'loading');
assert.equal(state({...base,failed:true}),'error');
assert.equal(state(base),'unavailable');
assert.equal(state({...base,firebaseEnabled:true}),'ready');
assert.equal(state({...base,firebaseEnabled:true,moduleCount:0}),'unavailable');
assert.equal(state({...base,googleSso:true,failed:true}),'ready');
assert.equal(state({...base,firebaseEnabled:true,pending:true}),'ready');
for(const status of ['loading','error','unavailable']){
 const html=renderToStaticMarkup(React.createElement(View,{state:status,onRetry(){}}));
 assert.match(html,/Continue with Google/);assert.match(html,/disabled/);assert.match(html,/role="status"/);
 assert.equal(html.includes('Retry sign-in options'),status!=='loading');
 if(status==='error')assert.match(html,/could not load/);
 if(status==='unavailable')assert.match(html,/not configured/);
}
assert.equal(renderToStaticMarkup(React.createElement(View,{state:'ready',onRetry(){}})),'');
let retries=0;
const failedView=View({state:'error',onRetry(){retries++;}});
const retryButton=failedView.props.children[2];
assert.equal(retryButton.props.type,'button');retryButton.props.onClick();assert.equal(retries,1);
const vm=require('node:vm');
function compile(relative,requireFn){
 const source=fs.readFileSync(path.resolve(__dirname,'../src/lib',relative),'utf8');
 const output=ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2020}}).outputText;
 const exports={};vm.runInNewContext(output,{exports,require:requireFn,URL});return exports;
}
const navigation=compile('suiteNavigation.ts',()=>({modules:[{homePath:'/pms'},{homePath:'/srm'}]}));
const login=compile('login.ts',()=>navigation);
assert.equal(login.loginDestination('/pms?workspace=3'),'/pms?workspace=3');
assert.equal(login.loginDestination('https://evil.example/pms'),'/dashboard');
console.log('PASS Google availability: loading, failure, retry, unconfigured, native/SSO readiness, no duplicate enabled control.');
