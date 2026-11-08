const fs=require('node:fs'),ts=require('../frontend/node_modules/typescript'),path=require('node:path');
const walk=d=>fs.readdirSync(d,{withFileTypes:true}).flatMap(e=>e.isDirectory()?walk(path.join(d,e.name)):[path.join(d,e.name)]);
const label=n=>ts.isJsxText(n)?n.text:n.children?.map(label).join(' ')||'';
const log=[];
for(const file of walk('frontend/src').filter(f=>f.endsWith('.tsx')&&!f.includes('shared/creation'))){
 let text=fs.readFileSync(file,'utf8');const sf=ts.createSourceFile(file,text,99,true,4),edits=[];
 function visit(n){if(ts.isJsxElement(n)&&/^(Button|button)$/.test(n.openingElement.tagName.getText(sf))){
  const title=label(n).replace(/\s+/g,' ').trim(),attr=n.openingElement.getText(sf);
  if(/^(Create\b|Add Mock Provider|Publish shared view)/i.test(title)&&/onClick=/.test(attr)&&/\.mutate\(|api\.post\(/.test(attr)){
   let p=n.parent,protectedForm=false;while(p){if(ts.isJsxElement(p)&&/Dialog|Modal|SmartCreate|form|CompactForm/.test(p.openingElement.tagName.getText(sf)))protectedForm=true;p=p.parent;}
   if(!protectedForm){
    let target=n,section=false; p=n.parent;
    while(p&&p!==sf){if(ts.isJsxElement(p)&&p.openingElement.tagName.getText(sf)==='div'){
      const source=p.getText(sf);
      if(/<(Input|input|EmployeeSearchSelect)\b/.test(source)&&source.length<5000&&!/GroupedRecords|GridTable|\.map\(/.test(source)) {target=p;section=true;}break;
    }p=p.parent;}
    if(edits.some(e=>target.getStart(sf)<e.end&&target.end>e.start))return;
    const tag=section?'SmartCreateSection':'SmartCreateAction';
    edits.push({start:target.getStart(sf),end:target.end,text:`<${tag} title=${JSON.stringify(title)}>${target.getText(sf)}</${tag}>`});
    log.push({file:file.replaceAll('\\','/'),line:sf.getLineAndCharacterOfPosition(n.getStart(sf)).line+1,title,component:tag});return;
   }
  }
 }ts.forEachChild(n,visit);}visit(sf);
 for(const e of edits.sort((a,b)=>b.start-a.start))text=text.slice(0,e.start)+e.text+text.slice(e.end);
 for(const tag of ['SmartCreateAction','SmartCreateSection'])if(edits.some(e=>e.text.startsWith('<'+tag+' '))&&!text.includes(`import { ${tag} }`))text=`import { ${tag} } from "@/shared/creation/${tag}";\n`+text;
 if(edits.length)fs.writeFileSync(file,text);
}
fs.writeFileSync('outputs/creation-inventory/preset-creation-migrations.json',JSON.stringify(log,null,2));console.log(JSON.stringify(log,null,2));
