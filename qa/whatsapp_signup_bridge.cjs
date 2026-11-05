const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const ts = require('../frontend/node_modules/typescript');
const session = { state:'s'.repeat(43), appId:'12345', configId:'67890', apiVersion:'v26.0', expires:Date.now()+590000 };
const origin = 'https://suite.example';
const tick = () => new Promise(setImmediate);

async function bridge(order) {
  const messages=[], listeners={}, elements={continue:{hidden:true,disabled:true,addEventListener(t,fn){this[t]=fn;}},status:{},workspace:{}};
  let callback, init;
  const location={origin,pathname:'/whatsapp-connect.html',hash:'#'+encodeURIComponent(JSON.stringify(session))};
  const opener={postMessage:(data,target)=>messages.push({data,target})};
  const sdk={init:value=>{init=value;},login:cb=>{callback=cb;}};
  const window={opener,FB:sdk,addEventListener:(t,fn)=>{listeners[t]=fn;},setTimeout:()=>1,clearTimeout(){}};
  const document={getElementById:id=>elements[id]};
  const context={window,document,location,history:{replaceState(){location.hash='';}},setTimeout:()=>1,Date,console};
  vm.runInNewContext(fs.readFileSync('frontend/public/whatsapp-connect.js','utf8'),context);
  await tick(); assert.equal(location.hash,''); assert.equal(elements.continue.disabled,false); assert.equal(init.fedCM,false);
  elements.continue.click();
  const finish = sourceOrigin => listeners.message({origin:sourceOrigin,data:JSON.stringify({type:'WA_EMBEDDED_SIGNUP',event:'FINISH',data:{waba_id:'12345',phone_number_id:'67890'}})});
  finish('https://evil.example'); assert.equal(messages.length,0);
  if(order==='code-first')callback({authResponse:{code:'one-use-code'}});
  finish('https://www.facebook.com');
  if(order==='assets-first')callback({authResponse:{code:'one-use-code'}});
  finish('https://www.facebook.com');
  assert.equal(messages.length,1);assert.equal(messages[0].target,origin);assert.equal(messages[0].data.code,'one-use-code');
  listeners.message({origin,source:{},data:{type:'SUITE_WHATSAPP_RESULT',state:session.state,success:true}});
  assert.doesNotMatch(elements.status.textContent,/WhatsApp connected/);
  listeners.message({origin,source:opener,data:{type:'SUITE_WHATSAPP_RESULT',state:session.state,success:true}});
  assert.match(elements.status.textContent,/WhatsApp connected/);
}

async function workspace() {
  let receiver, stateIndex=0, refIndex=0, posts=0, refreshed=0, opened;
  const acknowledgements=[], reports=[];
  const child={focus(){},postMessage:(data,target)=>acknowledgements.push({data,target})};
  const refs=[{current:session.state},{current:child},{current:{pin:'123456'}}];
  const window={location:{origin},addEventListener:(t,fn)=>{if(t==='message')receiver=fn;},removeEventListener(){},setTimeout:()=>1,clearTimeout(){},open:url=>{opened=url;return child;}};
  const jsx=(type,props)=>({type,props});
  const modules={
    react:{useState:()=>[stateIndex++===0?session:false,()=>{}],useRef:()=>refs[refIndex++],useEffect:fn=>{fn();}},
    'react/jsx-runtime':{jsx,jsxs:jsx},
    '@/services/api':{api:{post:async()=>{posts++;}}},
    '@/components/ui/button':{Button:'button'},
    './types':{whatsappBase:'/whatsapp',whatsappError:e=>e.message},
  };
  const context={window,Date,module:{exports:{}},exports:{},require:id=>{assert.ok(modules[id],id);return modules[id];}};
  context.exports=context.module.exports;
  const source=ts.transpileModule(fs.readFileSync('frontend/src/apps/communication/whatsapp/EmbeddedSignup.tsx','utf8'),{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.CommonJS,jsx:ts.JsxEmit.ReactJSX}}).outputText;
  vm.runInNewContext(source,context);
  const tree=context.module.exports.default({enabled:true,pin:'123456',done:async()=>{refreshed++;},report:m=>reports.push(m)});
  tree.props.children[0].props.onClick();
  const launch=JSON.parse(decodeURIComponent(opened.split('#')[1]));
  assert.equal(launch.state,session.state);assert.ok(!opened.includes('123456'),'Registration PIN must stay in the authenticated workspace');
  const data={type:'SUITE_WHATSAPP_AUTH',state:session.state,code:'one-use-code',wabaId:'12345',phoneNumberId:'67890'};
  await receiver({origin:'https://evil.example',source:child,data});
  await receiver({origin,source:{},data});
  await receiver({origin,source:child,data:{...data,state:'foreign'}});
  assert.equal(posts,0);
  const first=receiver({origin,source:child,data});
  await receiver({origin,source:child,data});await first;
  await receiver({origin,source:child,data});
  assert.equal(posts,1);assert.equal(refreshed,1);assert.equal(acknowledgements.length,1);
  assert.equal(acknowledgements[0].target,origin);assert.equal(acknowledgements[0].data.success,true);
}
(async()=>{await bridge('code-first');await bridge('assets-first');await workspace();console.log('PASS: dedicated signup handles callback races, exact origin/window/state checks, no secret launch data, one completion, and authenticated acknowledgement.');})().catch(e=>{console.error(e);process.exitCode=1;});
