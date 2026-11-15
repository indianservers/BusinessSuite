const fs=require('fs'),ts=require('../frontend/node_modules/typescript'),vm=require('vm'),assert=require('assert');
const sandboxModule={exports:{}};vm.runInNewContext(ts.transpileModule(fs.readFileSync(require('path').join(__dirname,'../frontend/src/lib/pharma-checkout-money.ts'),'utf8'),{compilerOptions:{target:ts.ScriptTarget.ES2020,module:ts.ModuleKind.CommonJS}}).outputText,{exports:sandboxModule.exports,module:sandboxModule});
const cases=JSON.parse(fs.readFileSync(require('path').join(__dirname,'pharma-money-golden.json')));
for(const c of cases){const p=c.actual_payload;const q=sandboxModule.exports.pharmaCheckoutQuote(p.lines.map(l=>({quantity:l.quantity,price:l.unit_price,discount:l.discount_amount,taxRate:l.tax_rate})),p.bill_discount_amount);if(c.native.status)assert.equal(q,null,c.id);else assert.equal(q?.grandTotal.toFixed(2),c.native.total,c.id);}
console.log(`${cases.length} native golden cases passed`);
