const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const source = fs.readFileSync(path.join(__dirname, '../app/static/js/pos-terminal.js'), 'utf8');
const storage = new Map();
const requests = [];
function page(fail) {
  const fields = new Map();
  const field = selector => {
    if (!fields.has(selector)) fields.set(selector, {value: '', textContent: '', selectedOptions: [{}], dataset: {sessionId:'QA-53', warehouseId:'1', saleUrl:'/pos/sale', walkinId:'0'}});
    return fields.get(selector);
  };
  field('#posCustomer').value = '1';
  const context = vm.createContext({console, document: {querySelector: field, querySelectorAll: () => [], addEventListener() {}},
    localStorage: {getItem: key => storage.get(key) || null, setItem: (key, value) => storage.set(key, value), removeItem: key => storage.delete(key)},
    bootstrap: {Modal: Object.assign(class {show(){}}, {getInstance: () => ({hide(){}})})},
    fetch: async (_url, options) => {
      requests.push(JSON.parse(options.body));
      if (fail) throw Error('Response lost after server commit');
      return {ok: true, status: 200, json: async () => ({sale_id:1,invoice_no:'QA-53-001',grand_total:2360,change_due:0,recovered:true})};
    }});
  vm.runInContext(source, context);
  vm.runInContext(`validateLine=()=>null; toast=()=>{}; rememberRecentProducts=()=>{}; renderCart=()=>{};
    paymentPayload=()=>({payment_mode:'Cash',paid_total:2360,total:2360,cash_tendered:2360});`, context);
  return context;
}
(async () => {
  const interrupted = page(true);
  vm.runInContext(`POS.cart=[{product_id:1,qty:2,rate:1000,tax_rate:18}];`, interrupted);
  await vm.runInContext('completeSale()', interrupted);
  assert.equal(vm.runInContext('POS.submitting', interrupted), false, 'Retry button must unlock after a lost response');
  assert.ok(vm.runInContext('POS.pendingSale.request_id', interrupted));
  const reloaded = page(false);
  vm.runInContext('restoreCartState()', reloaded);
  await vm.runInContext('completeSale()', reloaded);
  assert.deepEqual(requests[0], requests[1], 'Reload recovery must retry the identical request identity and payment');
  assert.equal(vm.runInContext('POS.cart.length', reloaded), 0);
  assert.equal(vm.runInContext('POS.pendingSale', reloaded), null);
  assert.equal(storage.has('vyapara_pos_cart_QA-53'), false);
  console.log('PASS: lost-response retry unlocks controls, survives reload, reuses the request, and clears recovery only after success');
})().catch(error => {console.error(error);process.exitCode=1;});
