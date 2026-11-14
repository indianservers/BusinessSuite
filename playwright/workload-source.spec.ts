import {test,expect} from '../frontend/node_modules/playwright/test';

test('workload citations apply project/period filters and follow subsequent source links',async({page})=>{
 const seen:URL[]=[];const writes:string[]=[];
 page.on('request',request=>{if(['POST','PUT','PATCH','DELETE'].includes(request.method()))writes.push(request.url())});
 await page.route('**/project-management/workload?**',async route=>{
  seen.push(new URL(route.request().url()));
  await route.fulfill({json:{basis:'hours',from:'2026-05-04',to:'2026-05-11',weeks:[],rows:[],sprints:[],users:[],
   projects:[{id:7,name:'Synthetic source project',project_key:'SYN'},{id:9,name:'Another source project',project_key:'OTH'}],
   summary:{over_capacity:0,near_capacity:0,under_capacity:0}}});
 });
 await page.goto('/workload-source-qa.html');
 await expect.poll(()=>seen.some(url=>url.searchParams.get('projectId')==='7'&&url.searchParams.get('from')==='2026-05-04'&&url.searchParams.get('to')==='2026-05-17')).toBe(true);
 await page.getByRole('link',{name:'Open another workload citation',exact:true}).click();
 await expect.poll(()=>seen.some(url=>url.searchParams.get('projectId')==='9'&&url.searchParams.get('from')==='2026-06-01'&&url.searchParams.get('to')==='2026-06-07')).toBe(true);
 await expect(page.getByRole('heading',{name:'Workload',exact:true})).toBeVisible();
 await page.getByRole('link',{name:'Open workspace workload citation',exact:true}).click();
 await expect.poll(()=>seen.some(url=>url.searchParams.get('workspace_id')==='12'&&!url.searchParams.has('projectId'))).toBe(true);
 await expect(page.getByText('Workspace 12: authorized projects only. Work outside this scope may add load.',{exact:true})).toBeVisible();
 expect(writes).toEqual([]);
});
