import {test,expect,type Page} from "../frontend/node_modules/playwright/test";
async function fixture(page:Page){
  await page.route("**/api/**",r=>r.fulfill({json:[]}));
  await page.route("**/__hr_standards*",route=>route.fulfill({contentType:"text/html",body:`<html><head><script type="module">import R from '/@react-refresh';R.injectIntoGlobalHook(window);window.$RefreshReg$=()=>{};window.$RefreshSig$=()=>type=>type;window.__vite_plugin_react_preamble_installed__=true;</script></head><body><div id="root"></div><script type="module" src="/scripts/fixtures/hr-workflow-standards-qa.tsx"></script></body></html>`}));
}
test("denied Intern Management access exits the loading state",async({page})=>{
  await fixture(page);
  await page.route("**/api/v1/interns-hub/management/access",r=>r.fulfill({json:{allowed:false}}));
  await page.goto("/__hr_standards?interns");
  await expect(page.getByRole("heading",{name:"Manager/Admin access required"})).toBeVisible();
  await expect(page.getByText("Checking HRMS permissions…")).toHaveCount(0);
});
test("HR workflow cards and badges use every shared priority color",async({page})=>{
  await fixture(page);
  const levels=["Urgent","High","Medium","Low"];
  await page.route("**/api/v1/workflow/inbox*",r=>r.fulfill({json:{total:4,pending_action:4,submitted_by_me:0,by_source:{leave:4},items:levels.map((priority,i)=>({id:String(i),source:"leave",source_id:i,title:`QA ${priority} request`,status:"Pending",priority,action_url:"/hrms/leave",action_label:"Review",role_scope:"employee"}))}}));
  await page.goto("/__hr_standards");
  const rows=page.locator("[data-priority-row]");
  await expect(rows).toHaveCount(4);
  expect(await rows.evaluateAll(nodes=>nodes.map(n=>getComputedStyle(n).backgroundColor))).toEqual(["rgb(255, 240, 242)","rgb(255, 244, 233)","rgb(255, 250, 231)","rgb(237, 249, 242)"]);
  await expect(page.locator("[data-priority-badge]")).toHaveText(levels);
});
