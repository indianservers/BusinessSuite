const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const context = vm.createContext({});
vm.runInContext(fs.readFileSync('app/static/js/invoice.js','utf8'), context);
const product = {id:1,sku:'QA<&"',name:'<b data-qa-injection="169">QA text</b>',sales_price:1000,purchase_price:600,tax_rate:18,current_stock:10};
context.product = product;
vm.runInContext('invoiceProducts = [product]',context);
for (const markup of [context.cartRowTemplate(product),context.optionsHtml([product])]) {
  assert.ok(!markup.includes('<b data-qa-injection'));
  assert.ok(markup.includes('&lt;b data-qa-injection=&quot;169&quot;&gt;QA text&lt;/b&gt;'));
}
assert.equal(context.escapeInvoiceText(null),'');
console.log('Invoice text escaping: passed (cart and option labels)');
