const fs=require('node:fs'),path=require('node:path'),Module=require('node:module'),ts=require('../frontend/node_modules/typescript');
const output='outputs/creation-inventory/all-module-routes.json';
const write=fs.writeFileSync;
fs.writeFileSync=(file,data,...args)=>String(file).endsWith('route-coverage.json')?write(output,data,...args):write(file,data,...args);
const audit=path.resolve('frontend/scripts/audit-ui-routes.cjs'),m=new Module(audit,module);m.filename=audit;m.paths=Module._nodeModulePaths(path.dirname(audit));
try{m._compile(fs.readFileSync(audit,'utf8'),audit);}finally{fs.writeFileSync=write;}
function initializer(file,name){const sf=ts.createSourceFile(file,fs.readFileSync(file,'utf8'),99,true,4);let found;function walk(n){if(ts.isVariableDeclaration(n)&&n.name.getText(sf)===name)found=n.initializer;ts.forEachChild(n,walk);}walk(sf);if(!found)throw Error('Missing '+name);return found.getText(sf);}
const applications=initializer('frontend/src/apps/power-apps/registry.ts','applicationRoutes').replace(/ as const$/,'');
const app=initializer('frontend/src/App.tsx','commonRoutes');
const exportsObject={};const React={createElement:(type,props)=>({component:type?.displayName||String(type),props})};
const context=new Proxy({},{has:()=>true,get:(_,key)=>key===Symbol.unscopables?undefined:key==='exports'?exportsObject:key==='React'?React:key==='undefined'?undefined:Object.assign(()=>null,{displayName:String(key)})});
const code=ts.transpileModule(`const applicationRoutes=${applications};exports.routes=${app};`,{compilerOptions:{module:ts.ModuleKind.CommonJS,jsx:ts.JsxEmit.React,target:ts.ScriptTarget.ES2020}}).outputText;
new Function('context',`with(context){${code}}`)(context);
const prior=JSON.parse(fs.readFileSync(output,'utf8'));
const byPath=new Map(prior.routes.filter(r=>!r.source.endsWith('/App.tsx')).map(r=>[r.path,r]));
for(const row of exportsObject.routes){const pathname='/'+row.path.replace(/^\//,'');byPath.set(pathname,{path:pathname,module:pathname.split('/')[1],source:'frontend/src/App.tsx',component:row.element?.component,dynamic:pathname.includes(':'),testing:'Current source route; see all-module creation verification ledger'});}
const appSource=ts.createSourceFile('App.tsx',fs.readFileSync('frontend/src/App.tsx','utf8'),99,true,4);
function explicitRoutes(n){if(ts.isJsxSelfClosingElement(n)&&n.tagName.getText(appSource)==='Route'){const attr=n.attributes.properties.find(p=>ts.isJsxAttribute(p)&&p.name.getText(appSource)==='path');if(attr?.initializer&&ts.isStringLiteral(attr.initializer)&&attr.initializer.text.startsWith('/settings')){const pathname=attr.initializer.text;byPath.set(pathname,{path:pathname,module:'settings',source:'frontend/src/App.tsx',dynamic:pathname.includes(':'),testing:'Optional shared settings route; concrete catalog sections exercised separately'});}}ts.forEachChild(n,explicitRoutes);}explicitRoutes(appSource);
const routes=[...byPath.values()];fs.writeFileSync(output,JSON.stringify({generatedBy:'node qa/build_creation_route_inventory.cjs',counts:{routes:routes.length},routes},null,2));console.log('Current routes including shared settings and Power Apps:',routes.length);
