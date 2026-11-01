const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),ts=require('typescript');
let user;const root=path.resolve(__dirname,'../src');const cache=new Map();
const installed=['hrms','crm','project_management','srm','fam','power_apps'];
function load(file){file=path.resolve(file);if(cache.has(file))return cache.get(file).exports;const m={exports:{}};cache.set(file,m);const code=ts.transpileModule(fs.readFileSync(file,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2020}}).outputText;const req=name=>{if(name==='@/store/authStore')return{useAuthStore:{getState:()=>({user})}};if(name==='@/appRegistry')return{getInstalledAppKeys:()=>installed,isFrontendModuleEnabled:()=>true};if(name==='lucide-react')return new Proxy({},{get:()=>()=>null});if(name.startsWith('./')||name.startsWith('@/')){let target=name.startsWith('@/')?path.join(root,name.slice(2)):path.join(path.dirname(file),name);return load(target+'.ts');}return require(name);};new Function('module','exports','require',code)(m,m.exports,req);return m.exports;}
const {searchableNavigation}=load(path.join(root,'lib/search-navigation.ts'));
global.window={location:{pathname:'/dashboard'}};
user={role:'super_admin',is_superuser:true};
for(const context of ['/dashboard','/hrms','/pms/tasks']){const pages=searchableNavigation(user.role,true,context);assert.ok(pages.some(p=>p.url==='/pms/tasks'&&p.title==='Tasks'));assert.ok(pages.some(p=>p.url==='/crm/leads'));assert.ok(pages.some(p=>p.url==='/fam/ledgers'));assert.equal(new Set(pages.map(p=>p.url)).size,pages.length);}
user={role:'employee',is_superuser:false,access:{managed:true,companyId:1,grants:{hrms:{enabled:true,role:'employee',scope:'own',permissions:['employee_view'],actions:['view']}},modules:[{key:'hrms',route:'/hrms',navigationPaths:['/hrms']}],isGlobalAdmin:false,isAccessAdmin:false}};
const restricted=searchableNavigation('employee',false,'/dashboard');assert.ok(restricted.every(p=>!p.url.startsWith('/pms')&&!p.url.startsWith('/crm')&&!p.url.startsWith('/fam')));
console.log('PASS: global cross-module pages, context independence, deduplication and managed-access restrictions');
