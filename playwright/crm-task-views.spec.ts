import {test,expect} from '../frontend/node_modules/playwright/test';
const filters={queue:'overdue',status:'all',priority:'High',mine:true,sort:'due_date:asc',search:'delivery'};
async function server(page:any,initial:any[]=[]){let items=initial,revision=initial.length?1:0;const writes:any[]=[];
 await page.route(/\/crm\/task-views(?:\/[^?]*)?(?:\?.*)?$/,async(route:any)=>{const request=route.request(),method=request.method(),url=new URL(request.url());
  const owner=request.headers()['x-task-view-user'],company=request.headers()['x-task-view-company'];expect(owner).toBe('7');
  if(company==='2')return route.fulfill({json:{items:[],revision:0,limit:30}});
  expect(company).toBe('1');const body=method==='GET'||method==='DELETE'?null:request.postDataJSON();
  if(method!=='GET')writes.push({method,path:url.pathname,body});
  if(method==='POST'&&url.pathname.endsWith('/import-browser')){for(const view of body.views)items.push({...view,id:String(items.length+1).padStart(32,'0')});revision++;return route.fulfill({json:{items,revision,limit:30,imported:body.views.length,retained:0}})}
  if(method==='POST'){items.push({...body,id:String(items.length+1).padStart(32,'0')});revision++}
  if(method==='PUT'){items=items.map(v=>url.pathname.endsWith(v.id)?{id:v.id,name:body.name,filters:body.filters}:v);revision++}
  if(method==='DELETE'){items=items.filter(v=>!url.pathname.endsWith(v.id));revision++}
  return route.fulfill({json:{items,revision,limit:30}})
 });return writes;
}

test('CRM views persist through the server and reload without browser view storage',async({page})=>{
 const writes=await server(page);await page.goto('/crm-task-views-qa.html');
 await page.getByLabel('Task view name',{exact:true}).fill('Delivery focus');await page.getByRole('button',{name:'Save view',exact:true}).click();
 await expect(page.getByRole('status')).toContainText('privately on the server');expect(writes[0].body).toEqual({name:'Delivery focus',filters});
 expect(await page.evaluate(()=>localStorage.getItem('crm.task-views.v1:7:1'))).toBeNull();
 await page.reload();await expect(page.getByRole('option',{name:'Delivery focus',exact:true})).toHaveCount(1);
 await page.getByLabel('Apply saved task view',{exact:true}).selectOption('00000000000000000000000000000001');
 await page.getByRole('button',{name:'Remove saved view',exact:true}).click();await expect(page.getByRole('status')).toContainText('Tasks are unchanged');
});

test('browser view import requires an explicit review and removes only the confirmed copy',async({page})=>{
 await server(page);await page.addInitScript(({filters})=>localStorage.setItem('crm.task-views.v1:7:1',JSON.stringify([{name:'Browser overdue',filters}])),{filters});
 await page.goto('/crm-task-views-qa.html');await page.getByText('1 browser views available to import',{exact:true}).click();
 expect(await page.evaluate(()=>localStorage.getItem('crm.task-views.v1:7:1'))).not.toBeNull();
 await page.getByRole('button',{name:'Import browser views to server',exact:true}).click();
 await expect(page.getByRole('status')).toContainText('Imported 1 browser views');expect(await page.evaluate(()=>localStorage.getItem('crm.task-views.v1:7:1'))).toBeNull();
});

test('bot view links apply authorized server filters and company switches clear the list',async({page})=>{
 const id='1234567890abcdef1234567890abcdef';await server(page,[{id,name:'Bot view',filters}]);await page.goto('/crm-task-views-qa.html?view='+id);
 await expect(page.getByRole('status')).toContainText('Applied “Bot view”');await expect(page.getByTestId('applied-filters')).toContainText('delivery');
 await page.getByRole('button',{name:'Switch fixture company',exact:true}).click();await expect(page.getByRole('option',{name:'Bot view',exact:true})).toHaveCount(0);
});
