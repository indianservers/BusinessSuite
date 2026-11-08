const fs = require('node:fs');
const path = require('node:path');
const ts = require('../frontend/node_modules/typescript');
const root = path.resolve(__dirname, '../frontend/src');
const out = path.resolve(__dirname, '../outputs/creation-inventory');
const walk = dir => fs.readdirSync(dir, {withFileTypes:true}).flatMap(e => e.isDirectory() ? walk(path.join(dir,e.name)) : [path.join(dir,e.name)]);
function label(n) { if(ts.isJsxText(n)) return n.text; return n.children?.map(label).join(' ') || ''; }
const result=[];
for(const file of walk(root).filter(f=>f.endsWith('.tsx'))) {
 const source=fs.readFileSync(file,'utf8'), sf=ts.createSourceFile(file,source,99,true,4);
 function visit(n) {
  if(ts.isJsxElement(n) && ['form','CompactForm','CardContent'].includes(n.openingElement.tagName.getText(sf))) {
   const kind=n.openingElement.tagName.getText(sf), buttons=[], fields=[];
   function collect(x) {
    if(ts.isJsxElement(x) && ['Button','button'].includes(x.openingElement.tagName.getText(sf))) {const text=label(x).replace(/\s+/g,' ').trim(); if(text) buttons.push(text);}
    if(ts.isJsxSelfClosingElement(x)&&/^(Input|Select|NativeSelect|Textarea|input|select|textarea|EmployeeSearchSelect|CompanySelect)$/.test(x.tagName.getText(sf))) fields.push(x.getText(sf).slice(0,190));
    ts.forEachChild(x,collect);
   }collect(n);
   const create=buttons.filter(b=>/^(create|add|new|invite|schedule|log|apply|request|upload|register|submit|start|generate|publish|save)\b/i.test(b));
   if(fields.length && create.length) {
    const ancestors=[];let p=n.parent;while(p){if(ts.isJsxElement(p))ancestors.push(p.openingElement.tagName.getText(sf));p=p.parent;}
    let title=''; let card=n;while(card&&!title){if(ts.isJsxElement(card)&&card.openingElement.tagName.getText(sf)==='Card'){function find(x){if(ts.isJsxElement(x)&&x.openingElement.tagName.getText(sf)==='CardTitle')title=label(x).replace(/\s+/g,' ').trim();if(!title)ts.forEachChild(x,find);}find(card);}card=card.parent;}
    result.push({file:path.relative(path.resolve(__dirname,'..'),file).replaceAll('\\','/'),line:sf.getLineAndCharacterOfPosition(n.getStart(sf)).line+1,kind,title,fields:fields.length,actions:create,protected:ancestors.some(a=>/Dialog|Modal|SmartCreateSection/.test(a)),ancestors,start:n.getStart(sf),end:n.end});
   }
  } ts.forEachChild(n,visit);
 }visit(sf);
}
fs.mkdirSync(out,{recursive:true});fs.writeFileSync(path.join(out,'all-module-creation-surfaces.json'),JSON.stringify(result,null,2));
console.log(JSON.stringify({surfaces:result.length,unwrapped:result.filter(r=>!r.protected).length,byModule:result.reduce((m,r)=>(m[r.file.split('/')[3]]=(m[r.file.split('/')[3]]||0)+1,m),{})},null,2));
for(const r of result.filter(r=>!r.protected))console.log(`${r.file}:${r.line} ${r.kind} ${r.title} (${r.fields}) ${r.actions.join(' | ')}`);
