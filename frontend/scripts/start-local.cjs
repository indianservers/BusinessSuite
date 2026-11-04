// Keep the usual local URL on a current, optimized build. No source server on 5173.
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto');
const {spawnSync,spawn}=require('node:child_process');
const root=path.resolve(__dirname,'..');
process.chdir(root);
process.env.VITE_DEV_API_PROXY_TARGET ||= 'http://127.0.0.1:1534';
process.env.VITE_API_BASE_URL ??= '';
const marker=path.join(root,'dist/.local-build.json');
function fingerprint(){
 const hash=crypto.createHash('sha256');
 function visit(file){
  if(!fs.existsSync(file))return;
  const stat=fs.statSync(file),relative=path.relative(root,file).replaceAll('\\','/');
  if(stat.isDirectory()){for(const name of fs.readdirSync(file).sort())visit(path.join(file,name));return;}
  hash.update(relative+'\0');
  // Source contents detect edits; public binaries only need metadata to avoid
  // reading large local model weights on each launch.
  hash.update(relative.startsWith('public/')?`${stat.size}:${stat.mtimeMs}`:fs.readFileSync(file));
 }
 for(const item of ['src','public','interns-hub/src','../shared','index.html','vite.config.ts','package.json','package-lock.json','tsconfig.json','tsconfig.node.json','scripts/start-local.cjs'])visit(path.join(root,item));
 for(const name of fs.readdirSync(root).filter(name=>name.startsWith('.env')).sort())visit(path.join(root,name));
 hash.update(JSON.stringify(Object.entries(process.env).filter(([name])=>name.startsWith('VITE_')).sort(([a],[b])=>a.localeCompare(b))));
 return hash.digest('hex');
}
function run(args){const result=spawnSync(process.execPath,args,{cwd:root,stdio:'inherit'});if(result.error)throw result.error;if(result.status!==0)process.exit(result.status||1);}
async function main(){
if(!process.argv.includes('--build-only'))await new Promise((resolve,reject)=>{
 const probe=require('node:net').createServer();
 probe.once('error',()=>reject(new Error('Port 5173 is already in use. Stop the existing local frontend before starting another copy.')));
 probe.listen(5173,'127.0.0.1',()=>probe.close(resolve));
});
const before=fingerprint();let saved;
try{saved=JSON.parse(fs.readFileSync(marker,'utf8'));}catch{}
if(saved?.fingerprint!==before||!fs.existsSync('dist/index.html')||!fs.existsSync('dist/.vite/manifest.json')){
 console.log('Building the optimized local app…');
 run(['node_modules/typescript/bin/tsc','--noEmit']);
 run(['--max-old-space-size=4096','node_modules/vite/bin/vite.js','build','--manifest']);
 run(['scripts/write-release-version.mjs']);
 // Never mark a build current if another edit arrived while it was compiling.
 if(fingerprint()!==before){console.error('Source changed during the build. Run npm start again to build the latest files.');process.exit(1);}
 fs.writeFileSync(marker,JSON.stringify({fingerprint:before,builtAt:new Date().toISOString()},null,2));
}else console.log('Optimized build is current; skipping compilation.');
if(process.argv.includes('--build-only'))process.exit(0);
console.log('Business Suite: http://localhost:5173 (optimized)');
const child=spawn(process.execPath,['node_modules/vite/bin/vite.js','preview','--host','127.0.0.1','--port','5173','--strictPort'],{cwd:root,stdio:'inherit'});
for(const signal of ['SIGINT','SIGTERM'])process.on(signal,()=>child.kill(signal));
child.on('exit',code=>process.exit(code||0));
child.on('error',error=>{console.error(error.message);process.exit(1);});
}
main().catch(error=>{console.error(error.message);process.exitCode=1;});
