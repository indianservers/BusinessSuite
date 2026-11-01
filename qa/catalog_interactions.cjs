const fs=require('node:fs'),path=require('node:path');
const ts=require('../frontend/node_modules/typescript');
const root=path.resolve(__dirname,'..');const out=path.join(root,'.local/full-interaction-audit');fs.mkdirSync(out,{recursive:true});
const results={routes:[],controls:[],apiCalls:[],noOpHandlers:[]};
function walk(dir){return fs.readdirSync(dir,{withFileTypes:true}).flatMap(e=>e.isDirectory()?walk(path.join(dir,e.name)):/\.(tsx?|jsx?)$/.test(e.name)?[path.join(dir,e.name)]:[])}
for(const f of walk(path.join(root,'frontend/src'))){const text=fs.readFileSync(f,'utf8');const s=ts.createSourceFile(f,text,ts.ScriptTarget.Latest,true,f.endsWith('tsx')?ts.ScriptKind.TSX:ts.ScriptKind.TS);const file=path.relative(root,f).replace(/\\/g,'/');
function pos(n){return s.getLineAndCharacterOfPosition(n.getStart(s)).line+1}
function visit(n){
 if(ts.isPropertyAssignment(n)&&n.name.getText(s)==='path'&&(ts.isStringLiteral(n.initializer)||ts.isNoSubstitutionTemplateLiteral(n.initializer)))results.routes.push({file,line:pos(n),path:n.initializer.text});
 if(ts.isJsxOpeningElement(n)||ts.isJsxSelfClosingElement(n)){const tag=n.tagName.getText(s);if(/^(button|Button|input|Input|textarea|Textarea|select|Select|form|a|Link|Checkbox|Switch|RichTextField)$/.test(tag)){const attrs={};for(const a of n.attributes.properties)if(ts.isJsxAttribute(a)){const key=a.name.getText(s);if(['aria-label','name','type','to','href','onClick','onChange','onSubmit','disabled','asChild','required','placeholder'].includes(key))attrs[key]=a.initializer?a.initializer.getText(s).slice(0,250):true;}results.controls.push({file,line:pos(n),tag,attributes:attrs});}}
 if(ts.isJsxAttribute(n)&&/^on(?:Click|Submit|Change)$/.test(n.name.getText(s))&&n.initializer&&ts.isJsxExpression(n.initializer)){const e=n.initializer.expression;if(e&&ts.isArrowFunction(e)&&ts.isBlock(e.body)&&!e.body.statements.length)results.noOpHandlers.push({file,line:pos(n),handler:n.name.getText(s)});}
 if(ts.isCallExpression(n)&&ts.isPropertyAccessExpression(n.expression)&&/^(get|post|put|patch|delete)$/.test(n.expression.name.text)&&/api|client|http/i.test(n.expression.expression.getText(s))&&n.arguments[0])results.apiCalls.push({file,line:pos(n),method:n.expression.name.text.toUpperCase(),url:n.arguments[0].getText(s).slice(0,350)});
 ts.forEachChild(n,visit);
}visit(s);}
fs.writeFileSync(path.join(out,'source-catalog.json'),JSON.stringify(results,null,2));
console.log(JSON.stringify({routes:results.routes.length,controls:results.controls.length,apiCalls:results.apiCalls.length,noOpHandlers:results.noOpHandlers},null,2));
