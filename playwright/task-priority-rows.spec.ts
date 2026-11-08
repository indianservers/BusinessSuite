import { test, expect } from "../frontend/node_modules/playwright/test";
import { authenticateCrm } from "./crm-core-test-utils";

test("task priorities color every cell and update immediately",async({page},testInfo)=>{
  await authenticateCrm(page);
  const tasks=["Urgent","High","Medium","Low"].map((priority,index)=>({id:index+1,title:`${priority} task`,task_key:`QA-${index+1}`,project_id:1,project_name:"QA project",priority,status:"To Do",assignees:[],assignee_user_ids:[],tags:[],progress:0,can_edit:true}));
  await page.route("**/api/v1/**",async route=>{
    const path=new URL(route.request().url()).pathname.replace('/api/v1','');
    if(path==='/access/settings/defaults/effective')return route.fulfill({json:{values:{},modules:{},companyId:1}});
    if(path==='/access/setup')return route.fulfill({json:{companyId:1,ready:true,items:[]}});
    if(path==='/project-management/tasks')return route.fulfill({json:{items:tasks,total:4,page:1,pageSize:25,pages:1,summary:{total:4},filters:{projects:[{id:1,name:"QA project",can_manage_tasks:true}],statuses:["To Do"],priorities:["Urgent","High","Medium","Low"],assignees:[],reporters:[],tags:[],sprints:[],epics:[]}}});
    if(path.startsWith('/project-management/tasks/')&&route.request().method()==='PATCH'){
      const task=tasks.find(task=>task.id===Number(path.split('/').pop()))!;Object.assign(task,route.request().postDataJSON());return route.fulfill({json:task});
    }
    if(path.startsWith('/project-management/'))return route.fulfill({json:path.includes('custom-fields')?{fields:[]}:[]});
    return route.fallback();
  });
  await page.goto('/pms/tasks');
  const rows=page.locator('tr[data-priority]');await expect(rows).toHaveCount(4);
  const colors=await rows.evaluateAll(rows=>rows.map(row=>getComputedStyle(row.querySelector('td')!).backgroundColor));
  expect(new Set(colors).size).toBe(4);
  await rows.first().hover();
  expect(await rows.first().locator('td').evaluateAll(cells=>new Set(cells.map(cell=>getComputedStyle(cell).backgroundColor)).size)).toBe(1);
  await page.getByLabel('Select Urgent task',{exact:true}).check();
  await expect(rows.first()).toHaveAttribute('aria-selected','true');
  await page.getByLabel('Priority for Low task',{exact:true}).selectOption('Urgent');
  await expect(page.locator('tr[data-priority="urgent"]')).toHaveCount(2);
  await page.screenshot({path:testInfo.outputPath('priority-rows.png'),fullPage:true});
});
