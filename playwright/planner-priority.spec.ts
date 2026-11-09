import {test,expect} from "../frontend/node_modules/playwright/test";
import {calendarDefaults} from "../frontend/src/apps/project-management/pages/calendarTypes";
test("planner calendar items retain the shared priority backgrounds",async({page})=>{
  await page.setViewportSize({width:1440,height:1000});
  const levels=["Urgent","High","Medium","Low"],today=new Date().toISOString().slice(0,10);
  await page.route("**/api/**",r=>r.fulfill({json:[]}));
  await page.route("**/api/v1/project-management/planner/preferences",r=>r.fulfill({json:{revision:1,preferences:{...calendarDefaults,timezone:"UTC",show_task_dates:true,task_scope:"all"}}}));
  await page.route("**/api/v1/project-management/planner",r=>r.fulfill({json:{projects:[{id:1,name:"QA project",workspace_id:1,due_date:null,status:"Active",can_schedule:true}],tasks:levels.map((priority,id)=>({id:id+1,project_id:1,title:`QA ${priority}`,task_key:`QA-${id+1}`,start_date:null,due_date:today,status:"To Do",priority,assignee_user_ids:[1],can_schedule:true})),milestones:[],people:[]}}));
  await page.route("**/__planner_priority",r=>r.fulfill({contentType:"text/html",body:`<html><head><script type="module">import R from '/@react-refresh';R.injectIntoGlobalHook(window);window.$RefreshReg$=()=>{};window.$RefreshSig$=()=>type=>type;window.__vite_plugin_react_preamble_installed__=true;</script></head><body><div id="root"></div><script type="module" src="/scripts/fixtures/planner-priority-qa.tsx"></script></body></html>`}));
  await page.goto("/__planner_priority");
  const chips=page.locator(".planner-chip[data-priority-row]");
  await expect(chips).toHaveCount(4);
  expect(await chips.evaluateAll(nodes=>Object.fromEntries(nodes.map(n=>[n.getAttribute("data-priority"),getComputedStyle(n).backgroundColor])))).toEqual({Urgent:"rgb(255, 240, 242)",High:"rgb(255, 223, 191)",Medium:"rgb(255, 250, 231)",Low:"rgb(237, 249, 242)"});
});
