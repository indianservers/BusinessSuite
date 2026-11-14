import {test,expect} from '../frontend/node_modules/playwright/test';
const filters={status:'Pending',priority:'Critical',assigned_to_me:true,my_tickets:false};
async function server(page:any,initial:any[]=[]){let items=initial,revision=initial.length?1:0;const writes:any[]=[];
 await page.route(/\/helpdesk\/ticket-views(?:\/[^?]*)?(?:\?.*)?$/,async(route:any)=>{const request=route.request(),method=request.method(),url=new URL(request.url());
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

test('HRMS views persist through the server and reload without browser view storage',async({page})=>{
 const writes=await server(page);await page.goto('/hrms-ticket-views-qa.html');
 await page.getByLabel('Ticket view name',{exact:true}).fill('Delivery focus');await page.getByRole('button',{name:'Save view',exact:true}).click();
 await expect(page.getByRole('status')).toContainText('privately on the server');expect(writes[0].body).toEqual({name:'Delivery focus',filters});
 expect(await page.evaluate(()=>Object.keys(localStorage).filter(key=>/view/i.test(key)))).toEqual([]);
 await page.reload();await expect(page.getByRole('option',{name:'Delivery focus',exact:true})).toHaveCount(1);
 await page.getByLabel('Apply saved ticket view',{exact:true}).selectOption('00000000000000000000000000000001');
 await page.getByRole('button',{name:'Remove saved view',exact:true}).click();await expect(page.getByRole('status')).toContainText('Tickets are unchanged');
});

test('bot view links apply authorized server filters and company switches clear the list',async({page})=>{
 const id='1234567890abcdef1234567890abcdef';await server(page,[{id,name:'Bot view',filters}]);await page.goto('/hrms-ticket-views-qa.html?view='+id);
 await expect(page.getByRole('status')).toContainText('Applied “Bot view”');await expect(page.getByTestId('applied-filters')).toContainText('Critical');
 await page.getByRole('button',{name:'Switch fixture company',exact:true}).click();await expect(page.getByRole('option',{name:'Bot view',exact:true})).toHaveCount(0);
});


test('native helpdesk sends all saved filters to its canonical ticket API',async({page})=>{
 const id='abcdefabcdefabcdefabcdefabcdefab';await server(page,[{id,name:'Critical assigned',filters}]);
 const reads:URL[]=[];
 await page.route(/\/helpdesk\/(tickets|categories|analytics|sla-breaches)(?:\?.*)?$/,async route=>{
  const url=new URL(route.request().url());if(url.pathname.endsWith('/tickets'))reads.push(url);
  await route.fulfill({json:url.pathname.endsWith('/analytics')?{total:0,open:0,resolved:0,sla_breached:0,due_soon:0,first_response_breached:0,csat_average:0,csat_responses:0,by_status:{}}:[]});
 });
 await page.goto('/hrms-ticket-views-qa.html?native=1&view='+id);
 await expect(page.getByLabel('Filter ticket status',{exact:true})).toHaveValue('Pending');
 await expect(page.getByLabel('Filter ticket priority',{exact:true})).toHaveValue('Critical');
 await expect(page.getByLabel('Assigned to me',{exact:true})).toBeChecked();
 await expect.poll(()=>reads.some(url=>url.searchParams.get('status')==='Pending'&&url.searchParams.get('priority')==='Critical'&&url.searchParams.get('assigned_to_me')==='true'&&url.searchParams.get('my_tickets')==='false')).toBe(true);
 await page.getByLabel('Raised by me',{exact:true}).check();
 await expect.poll(()=>reads.some(url=>url.searchParams.get('my_tickets')==='true')).toBe(true);
});
