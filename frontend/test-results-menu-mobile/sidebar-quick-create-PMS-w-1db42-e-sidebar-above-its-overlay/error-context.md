# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: sidebar-quick-create.spec.ts >> PMS workspace uses the shared mobile sidebar above its overlay
- Location: ..\playwright\sidebar-quick-create.spec.ts:249:5

# Error details

```
Error: expect(locator).toBeVisible() failed

Locator: getByRole('dialog', { name: 'Application navigation', exact: true }).getByRole('button', { name: 'Create Project', exact: true })
Expected: visible
Timeout: 8000ms
Error: element(s) not found

Call log:
  - Expect "toBeVisible" with timeout 8000ms
  - waiting for getByRole('dialog', { name: 'Application navigation', exact: true }).getByRole('button', { name: 'Create Project', exact: true })

```

```yaml
- status
- complementary "Cache and sync diagnostics":
  - button "Cache & sync · idle"
- button "Page actions"
- navigation "PMS pages":
  - link "Workspaces":
    - /url: /pms/workspaces
  - text: Projects / Projects
  - button "Explore pages"
- dialog "Application navigation":
  - link "Business Suite home":
    - /url: /dashboard
    - img
    - strong: KaryaFlow PMS
    - text: PMS 1.01 · Admin Console
  - button "Close navigation":
    - img
  - link "All applications":
    - /url: /dashboard
    - img
    - text: All applications
  - img
  - combobox "Switch business module":
    - option "All applications"
    - option "Power Apps"
    - option "AI HRMS"
    - option "VyaparaCRM"
    - option "KaryaFlow PMS" [selected]
    - option "Sales & Inventory Management"
    - option "Finance & Accounting Management"
  - link "Users & access":
    - /url: /admin/access
  - navigation "Module navigation":
    - img
    - textbox "Find a page in this application":
      - /placeholder: Find a page…
      - text: Projects
    - button "Clear menu search":
      - img
    - text: 13 results
    - button "Expand all menu categories":
      - img
    - button "Collapse all menu categories":
      - img
    - list:
      - listitem:
        - button "Tasks & projects 12" [expanded]:
          - img
          - text: Tasks & projects 12
          - img
        - list:
          - listitem:
            - link "Product Launch":
              - /url: /pms/product-launch
              - img
              - text: Product Launch
            - button "More options for Product Launch":
              - img
          - listitem:
            - link "Work pipeline":
              - /url: /pms/work-hub
              - img
              - text: Work pipeline
            - button "More options for Work pipeline":
              - img
          - listitem:
            - link "Issues":
              - /url: /pms/issues
              - img
              - text: Issues
            - button "More options for Issues":
              - img
          - listitem:
            - link "All tasks":
              - /url: /pms/tasks
              - img
              - text: All tasks
            - button "More options for All tasks":
              - img
          - listitem:
            - link "Tasks & Follow-ups":
              - /url: /pms/tasks-follow-ups
              - img
              - text: Tasks & Follow-ups
            - button "More options for Tasks & Follow-ups":
              - img
          - listitem:
            - link "Issue Navigator":
              - /url: /pms/navigator
              - img
              - text: Issue Navigator
            - button "More options for Issue Navigator":
              - img
          - listitem:
            - link "Issue Navigator Pro":
              - /url: /pms/issue-navigator-pro
              - img
              - text: Issue Navigator Pro
            - button "More options for Issue Navigator Pro":
              - img
          - listitem:
            - link "Workspaces":
              - /url: /pms/workspaces
              - img
              - text: Workspaces
            - button "Create Workspace":
              - img
            - button "More options for Workspaces":
              - img
          - listitem:
            - link "Projects":
              - /url: /pms/projects
              - img
              - text: Projects
            - button "More options for Projects":
              - img
          - listitem:
            - link "Software Delivery":
              - /url: /pms/software
              - img
              - text: Software Delivery
            - button "More options for Software Delivery":
              - img
          - listitem:
            - link "Releases":
              - /url: /pms/releases
              - img
              - text: Releases
            - button "More options for Releases":
              - img
          - listitem:
            - link "My work":
              - /url: /pms/my-work
              - img
              - text: My work
            - button "More options for My work":
              - img
      - listitem:
        - button "Reports & finances 1" [expanded]:
          - img
          - text: Reports & finances 1
          - img
        - list:
          - listitem:
            - link "Project Analytics":
              - /url: /pms/analytics/projects
              - img
              - text: Project Analytics
            - button "More options for Project Analytics":
              - img
    - link "Company Admin":
      - /url: /company-admin
      - img
      - text: Company Admin
  - link "My account":
    - /url: /account
    - img
    - text: admin@example.com
  - link "Help and support":
    - /url: /help
    - text: Help & support
  - button "Sign out":
    - img
    - text: Sign out
- banner:
  - button "Open navigation":
    - img
  - text: Branch
  - combobox "Current branch":
    - option "Workflow test branch" [selected]
  - button "Notifications":
    - img
  - button "Switch workspace":
    - text: W
    - strong: Choose workspace
    - img
  - button "Profile menu": A
- img
- text: Workspaces
- img
- strong: Workspace board
- img
- img
- heading "Good work happens together." [level=2]
- paragraph: Create a home for your projects. Invite your people. Turn the next big idea into done.
- button "Create workspace":
  - img
  - text: Create workspace
- button "Join a workspace"
- text: Workspace creation is available to PMS administrators and project managers.
- button "Close navigation overlay"
- status
- button "Workspace tools":
  - img
- navigation "PMS mobile navigation":
  - link "My Work":
    - /url: /pms/my-work
  - link "Projects":
    - /url: /pms/projects
  - link "Tasks":
    - /url: /pms/tasks
  - link "Reports":
    - /url: /pms/reports
- button "Projects quick actions":
  - img
  - text: Projects actions
- region "Notifications (F8)":
  - list
```

# Test source

```ts
  157 |     return r.fulfill({json:path.endsWith("catalog")?{applications:[{id:"automations",name:"Automations",route:"/power-apps/automations",icon:"Workflow",status:"available",description:"Automations",environments:["testing"],required_permissions:[],feature_flags:[]}],permissions:["power_apps_view","power_apps_create"],templates:[]}:path.endsWith("environments")?{items:[{key:"testing",enabled:true}]}:path.endsWith("overview")?{counts:{},recent:[],unsupported_metrics:[]}: {items:[],total:0}});
  158 |   });
  159 |   await page.goto("/power-apps?environment=testing");const navigation=await menu(page,"Automations");
  160 |   await navigation.getByRole("button",{name:"Create Automation",exact:true}).click();
  161 |   await expect(page).toHaveURL(/\/power-apps\/automations\/new\?environment=testing/);
  162 | });
  163 | 
  164 | test("asset shortcut reveals its form from a different asset tab",async({page})=>{
  165 |   await setup(page);await page.route("**/api/v1/assets**",r=>r.fulfill({json:r.request().url().includes("capabilities")?{can_manage:true}:[]}));
  166 |   await page.goto("/hrms/assets");await page.getByRole("button",{name:"Employee custody",exact:true}).click();
  167 |   const navigation=await menu(page,"Assets");await navigation.getByRole("button",{name:"Create Asset",exact:true}).click();
  168 |   await expect(page.getByRole("heading",{name:"Register an asset",exact:true})).toBeVisible();
  169 |   await expect(page.locator('input:focus')).toHaveCount(1);
  170 | });
  171 | 
  172 | test("HR sidebar actions render with populated employee cards",async({page},testInfo)=>{
  173 |   await page.setViewportSize({width:1500,height:1000});await setup(page);
  174 |   const items=[{id:1,employee_id:"EMP-1",first_name:"Asha",last_name:"Rao",status:"Active",employment_type:"Full-time",date_of_joining:"2026-01-01",personal_email:"asha@example.com",phone_number:null},{id:2,employee_id:"EMP-2",first_name:"Ravi",last_name:"Kumar",status:"Probation",employment_type:"Contract",date_of_joining:"2026-02-01",personal_email:null,phone_number:null}];
  175 |   await page.route("**/api/v1/employees/**",r=>r.fulfill({json:r.request().url().includes("workbench/home")?{pending_counts:{}}:r.request().url().includes("filter-options")?{}:{items,total:2,pages:1,page:1}}));
  176 |   await page.goto("/hrms/employees");await expect(page.getByText("Asha Rao",{exact:true})).toBeVisible();
  177 |   const navigation=page.locator(".module-menu").first();await navigation.getByRole("button",{name:"Expand all menu categories",exact:true}).click();
  178 |   await navigation.getByRole("button",{name:"More options for People",exact:true}).click();
  179 |   await page.getByRole("menuitem",{name:"Create new",exact:true}).hover();
  180 |   await expect(page.getByRole("menuitem",{name:"Add Employee",exact:true})).toBeVisible();
  181 |   await page.screenshot({path:resolve(testInfo.project.testDir,"../outputs/navigation-actions/HRMS-menu-preview.png")});
  182 | });
  183 | 
  184 | 
  185 | test("employee directory and sidebar use one guided creation UI", async ({page}) => {
  186 |   await setup(page);
  187 |   await page.goto("/hrms/employees");
  188 |   await page.locator("#quick-add-employee").click();
  189 |   const dialog=page.getByRole("dialog");
  190 |   await expect(dialog.getByRole("textbox",{name:/^First Name/})).toBeVisible();
  191 |   const fields=await dialog.locator("input,select,textarea").evaluateAll(nodes=>nodes.map(node=>({tag:node.tagName,name:node.getAttribute("name"),type:node.getAttribute("type")})));
  192 |   await expect(dialog.getByRole("button",{name:"1 Personal",exact:true})).toBeVisible();
  193 |   await dialog.getByRole("button",{name:"Cancel",exact:true}).click();
  194 |   await expect(dialog).toHaveCount(0);
  195 |   const navigation=await menu(page,"Employees");
  196 |   await navigation.getByRole("button",{name:"Create Employee",exact:true}).click();
  197 |   await expect(dialog.getByRole("textbox",{name:/^First Name/})).toBeVisible();
  198 |   expect(await dialog.locator("input,select,textarea").evaluateAll(nodes=>nodes.map(node=>({tag:node.tagName,name:node.getAttribute("name"),type:node.getAttribute("type")})))).toEqual(fields);
  199 |   await expect(page.locator("[data-smart-create=true]")).toHaveCount(1);
  200 |   await expect(page).toHaveURL(/\/hrms\/employees$/);
  201 | });
  202 | 
  203 | test("customer creation has the same fields in CRM and Sales", async ({page}) => {
  204 |   await authenticateCrm(page);
  205 |   await page.route("**/api/v1/access/settings/defaults/effective", r => r.fulfill({json:{values:{},modules:{},companyId:1}}));
  206 |   await page.route("**/api/v1/catalog/items**", r => r.fulfill({json:{items:[],total:0,pages:0,permissions:{product:true,service:true}}}));
  207 |   await page.route("**/api/v1/access/setup", r => r.fulfill({json:{companyId:1,ready:true,items:[]}}));
  208 |   await page.route("**/api/v1/master-data/form-options**",route=>route.fulfill({json:{country:"IN",currency:"INR",phone_country_code:"+91"}}));
  209 |   let fields: string[]=[];
  210 |   for(const module of ["crm","srm"]){
  211 |     await page.goto(`/${module}/customers`);
  212 |     const navigation=await menu(page,"Customers");
  213 |     await navigation.getByRole("button",{name:"Create Customer",exact:true}).click();
  214 |     const dialog=page.getByRole("dialog");
  215 |     await expect(dialog.getByRole("heading",{name:"Create customer",exact:true})).toBeVisible();
  216 |     const actual=await dialog.locator("input,select,textarea").evaluateAll(nodes=>nodes.map(node=>[node.tagName,node.getAttribute("name"),node.getAttribute("aria-label"),node.getAttribute("type")].join(":")));
  217 |     if(module==="crm")fields=actual;else expect(actual).toEqual(fields);
  218 |     await expect(dialog).toHaveCount(1);
  219 |     await dialog.getByRole("button",{name:"Cancel",exact:true}).click();
  220 |     await expect(dialog).toHaveCount(0);
  221 |   }
  222 | });
  223 | 
  224 | 
  225 | for(const [module,first,second] of [
  226 |   ["crm","/crm/contacts","/crm/customers"],
  227 |   ["hrms","/hrms/employees","/hrms/leave"],
  228 |   ["srm","/srm/sales-orders","/srm/invoices"],
  229 |   ["fam","/fam/customers","/fam/vouchers"],
  230 |   ["pms","/pms/projects","/pms/product-launch"],
  231 | ])test(`${module} keeps the same styled menu across its pages`,async({page})=>{
  232 |   await setup(page);
  233 |   let catalog:string[]=[];
  234 |   for(const route of [first,second,...(module === "pms" ? ["/pms"] : [])]){
  235 |     await page.goto(route);
  236 |     const navigation=page.locator('.module-menu').first();
  237 |     await navigation.getByRole('button',{name:'Expand all menu categories',exact:true}).click();
  238 |     const links=await navigation.locator('.module-menu-categories .module-menu-row > a,.module-menu-landing .module-menu-row > a').evaluateAll(nodes=>nodes.map(node=>`${node.textContent?.trim()}:${new URL((node as HTMLAnchorElement).href).pathname}`).sort());
  239 |     if(route===first)catalog=links;else expect(links).toEqual(catalog);
  240 |     if(module === 'crm' && route === second) await page.locator('.suite-sidebar').screenshot({path:resolve('../outputs/shared-sidebar-crm.png')});
  241 |     await expect(navigation.locator('.module-menu-more').first()).toBeVisible();
  242 |     await expect(navigation.locator('.module-menu-create').first()).toBeVisible();
  243 |     expect(await navigation.evaluate(node=>getComputedStyle(node).getPropertyValue('--menu-accent').trim())).toBe('270 100% 80%');
  244 |     expect(await page.locator('.suite-sidebar').evaluate(node=>getComputedStyle(node).backgroundImage)).toContain('57, 36, 82');
  245 |   }
  246 | });
  247 | 
  248 | 
  249 | test("PMS workspace uses the shared mobile sidebar above its overlay",async({page})=>{
  250 |   await setup(page);
  251 |   await page.setViewportSize({width:390,height:844});
  252 |   await page.goto('/pms');
  253 |   await page.getByRole('button',{name:'Open navigation',exact:true}).click();
  254 |   const sidebar=page.getByRole('dialog',{name:'Application navigation',exact:true});
  255 |   await expect(sidebar).toBeVisible();
  256 |   await sidebar.getByRole('textbox',{name:'Find a page in this application'}).fill('Projects');
> 257 |   await expect(sidebar.getByRole('button',{name:'Create Project',exact:true})).toBeVisible();
      |                                                                                ^ Error: expect(locator).toBeVisible() failed
  258 |   await sidebar.getByRole('button',{name:'Close navigation',exact:true}).click();
  259 |   await expect(sidebar).toHaveCount(0);
  260 | });
  261 | 
```