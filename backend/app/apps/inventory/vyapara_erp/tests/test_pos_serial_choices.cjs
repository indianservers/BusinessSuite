const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const ctx=vm.createContext({document:{addEventListener(){}},console});
vm.runInContext(fs.readFileSync('app/static/js/pos-terminal.js','utf8'),ctx);
vm.runInContext(`var selected=null; var warned='';
 searchProducts=async()=>[{id:4,sku:'QA-SERIAL',name:'Serialized',rate:1000,tax_rate:18,stock:1,track_inventory:true,serial_tracking:true,serials:[{id:7,serial_no:'QA-ABC'}]}];
 openLineDetail=product=>{selected=product;};toast=message=>{warned=message;};`,ctx);
(async()=>{
 await vm.runInContext(`addProduct({id:4,sku:'QA-SERIAL',name:'Serialized',rate:1000,tax_rate:18,stock:1,track_inventory:true,serial_tracking:true,serials:[]})`,ctx);
 assert.equal(vm.runInContext('selected.serials[0].id',ctx),7);
 assert.equal(vm.runInContext('POS.cart.length',ctx),0,'Tracked tile must open selection before creating a cart line');
 assert.match(vm.runInContext('validateLine({...selected,qty:1})',ctx),/requires a serial/);
 assert.equal(vm.runInContext('validateLine({...selected,qty:1,serial_id:7})',ctx),'');
 console.log('PASS: tracked tile loads serial options; checkout requires a selected serial');
})().catch(error=>{console.error(error);process.exitCode=1;});
