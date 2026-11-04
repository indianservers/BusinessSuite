import {expect,test,type Page} from '../frontend/node_modules/playwright/test';
import {authenticate} from './srm-test-utils';

async function pos(page:Page, failure=0){
  await authenticate(page,'srm_admin');
  const customer={id:10,name:'Axiom Telecom',entityKind:'Company',status:'Active',roles:['Customer'],contacts:[],relationships:[],purchases:[],canEdit:false,phone:'2025550101',phone_country_code:'+1'};
  await page.route('**/api/v1/srm/business/customers*',route=>route.fulfill({json:{items:[customer],next:null}}));
  await page.route('**/api/v1/srm/inventory/items*',route=>route.fulfill({json:{items:[{id:21,item_name:'Care service',sku:'CARE',product_type:'service',track_inventory:false,sales_rate:100,current_quantity:100,gst_rate:0,active:true}],total:1}}));
  await page.route('**/api/v1/follow-ups/options',route=>route.fulfill({json:{customers:[customer],employees:[],teams:[]}}));
  await page.route('**/api/v1/master-data/companies/10*',route=>route.fulfill({json:customer}));
  await page.route('**/api/v1/master-data/company/10/channels*',route=>route.fulfill({json:{items:[],version:'1'}}));
  await page.route('**/api/v1/record-360/company/10**',route=>{
    if(failure)return route.fulfill({status:failure,json:{detail:failure===403?'Customer access is restricted':'Customer service is unavailable'}});
    if(/\/(work|events)(?:\?|$)/.test(route.request().url()))return route.fulfill({json:{items:[],total:null,has_more:false,next_cursor:null,page:1,per_page:25,sections:{}}});
    return route.fulfill({json:{id:10,kind:'company',name:customer.name,status:'Active',fields:{industry:'Telecom'},customer:{id:10,name:customer.name},projects:[],relations:[],allowed_actions:[],sections:{}}});
  });
  const writes:string[]=[];
  page.on('request',request=>{if(request.method()!=='GET'&&/\/srm\/(sales-orders|.*payments|receipts)/.test(request.url()))writes.push(request.url());});
  await page.goto('/srm/pos');
  await expect(page.getByRole('heading',{name:'Sales & Inventory POS'})).toBeVisible();
  return writes;
}

for(const failure of [0,403,500])test(`customer profile preserves cart and payment state (${failure||'success'})`,async({page})=>{
  await page.setViewportSize({width:1500,height:1000});
  const writes=await pos(page,failure);
  await expect(page.getByRole('button',{name:'Open customer 360'})).toHaveCount(0);
  await page.getByRole('combobox',{name:'Sale customer'}).click();
  await page.getByRole('option',{name:/Axiom Telecom/}).click();
  await page.getByRole('button',{name:/Care service/}).first().click();
  const cart=page.locator('.srm-pos-cart');
  await cart.getByLabel('Qty',{exact:true}).fill('3');
  await cart.getByLabel('Rate',{exact:true}).fill('125');
  await cart.getByLabel('Disc %',{exact:true}).fill('10');
  await page.getByRole('button',{name:'Pay',exact:true}).click();
  const payment=page.getByRole('dialog',{name:'Complete Payment'});
  await expect(payment).toBeVisible();
  await payment.getByLabel('Payment amount',{exact:true}).fill('500');
  await payment.getByLabel('Payment reference',{exact:true}).fill('CARD-360-REF');
  await payment.getByRole('button',{name:'View customer 360',exact:true}).click();
  const profile=page.getByRole('dialog',{name:'Customer 360',exact:true});
  await expect(profile).toBeVisible();
  if(failure)await expect(profile.getByRole('alert')).toContainText(failure===403?'Customer access is restricted':'Customer service is unavailable');
  else await expect(profile.getByRole('heading',{name:'Axiom Telecom',exact:true})).toBeVisible();
  await profile.getByRole('button',{name:'Close dialog',exact:true}).click();
  await expect(payment).toBeVisible();
  await expect(payment.getByLabel('Payment amount',{exact:true})).toHaveValue('500');
  await expect(payment.getByLabel('Payment reference',{exact:true})).toHaveValue('CARD-360-REF');
  await expect(payment.getByRole('combobox',{name:'Follow-up customer'})).toHaveValue('10');
  await payment.getByRole('button',{name:'Close Complete Payment'}).click();
  await expect(cart.getByLabel('Qty',{exact:true})).toHaveValue('3');
  await expect(cart.getByLabel('Rate',{exact:true})).toHaveValue('125');
  await expect(cart.getByLabel('Disc %',{exact:true})).toHaveValue('10');
  await expect(page).toHaveURL(/\/srm\/pos$/);
  expect(writes).toEqual([]);
});
