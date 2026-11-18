const fs=require('node:fs'),path=require('node:path'),zlib=require('node:zlib'),assert=require('node:assert/strict');
const directory=process.argv[2];assert(directory,'Provide the Vite build directory');
const manifest=JSON.parse(fs.readFileSync(path.join(directory,'.vite/manifest.json'),'utf8'));
const startup=new Set();function visit(key){if(startup.has(key))return;startup.add(key);for(const child of manifest[key].imports||[])visit(child);}visit('index.html');
const main=fs.readFileSync(path.join(directory,manifest['index.html'].file));
assert(main.length<900000,'Keep the main JavaScript bundle below 900 kB');
for(const feature of ['Deal360Page.tsx','DashboardsPage.tsx','WorkspaceCollaboration.tsx','WorkspaceWork.tsx','ImportWorkspace.tsx']){
 const key=Object.keys(manifest).find(key=>key.endsWith('/'+feature));assert(key,'Missing lazy route '+feature);assert(!startup.has(key),feature+' must load on demand');
}
function payload(base){
 const html=fs.readFileSync(path.join(base,'index.html'),'utf8');
 const files=[...new Set([...html.matchAll(/(?:src|href)="([^"]+\.js)"/g)].map(match=>match[1]))];
 let bytes=0,gzip=0;for(const file of files){const data=fs.readFileSync(path.join(base,file.replace(/^\//,'')));bytes+=data.length;gzip+=zlib.gzipSync(data).length;}
 return {files:files.length,bytes,gzip};
}
const result={main:{bytes:main.length,gzip:zlib.gzipSync(main).length},startup:payload(directory),deferredFeatures:5};
if(process.argv[3])result.previousStartup=payload(process.argv[3]);
console.log(JSON.stringify(result,null,2));
