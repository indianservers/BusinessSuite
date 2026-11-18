# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: sidebar-quick-create.spec.ts >> ellipsis offers contextual creation and configuration without changing pages
- Location: ..\playwright\sidebar-quick-create.spec.ts:97:5

# Error details

```
Error: expect(locator).toContainText(expected) failed

Locator: getByRole('dialog')
Expected substring: "Create contact"
Timeout: 8000ms
Error: element(s) not found

Call log:
  - Expect "toContainText" with timeout 8000ms
  - waiting for getByRole('dialog')

```

```yaml
- status
- complementary "Cache and sync diagnostics":
  - button "Cache & sync · idle"
- link "Skip to content":
  - /url: "#suite-main"
- complementary "Application navigation":
  - link "Business Suite home":
    - /url: /dashboard
    - img
    - strong: VyaparaCRM
    - text: CRM 1.01 · Admin Console
  - button "Collapse navigation":
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
    - option "VyaparaCRM" [selected]
    - option "KaryaFlow PMS"
    - option "Sales & Inventory Management"
    - option "Finance & Accounting Management"
  - link "Users & access":
    - /url: /admin/access
  - navigation "Module navigation":
    - img
    - textbox "Find a page in this application":
      - /placeholder: Find a page…
      - text: Contacts
    - button "Clear menu search":
      - img
    - text: 1 results
    - button "Expand all menu categories":
      - img
    - button "Collapse all menu categories":
      - img
    - list:
      - listitem:
        - button "Customers & leads 1" [expanded]:
          - img
          - text: Customers & leads 1
          - img
        - list:
          - listitem:
            - link "Contacts":
              - /url: /crm/contacts
              - img
              - text: Contacts
            - button "Create Contact":
              - img
            - button "More options for Contacts":
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
  - button "Open search":
    - img
  - button "Open workspace switcher":
    - img
    - text: Customers & contacts
    - img
  - text: Branch
  - combobox "Current branch":
    - option "Workflow test branch" [selected]
  - link "Company Admin":
    - /url: /company-admin
  - button "Refresh page data"
  - button "Pages with refresh"
  - button "New":
    - img
    - text: New
    - img
  - button "Notifications":
    - img
  - button "Switch to dark theme":
    - img
  - button "Account menu": AD
- main:
  - navigation "Breadcrumb":
    - link "Business Suite applications":
      - /url: /dashboard
    - link "VyaparaCRM":
      - /url: /crm
    - text: Contacts
  - button "Team workspace":
    - img
    - text: Team workspace
  - button "Page actions"
  - status "Loading Contacts":
    - paragraph: Loading Contacts
- button "Ask AI Assistant":
  - img
  - text: Ask AI Assistant
- region "Notifications (F8)":
  - list
- status: Loading contact form…
- status:
  - text: Loading contact form…
  - button "Cancel"
- tooltip "More options for Contacts"
```

# Test source

```ts
  6   | async function setup(page: Page, role: "admin" | "srm_viewer" = "admin") {
  7   |   await authenticate(page, role);
  8   |   await page.route("**/api/v1/access/settings/defaults/effective", r => r.fulfill({json:{values:{},modules:{},companyId:1}}));
  9   |   await page.route("**/api/v1/catalog/items**", r => r.fulfill({json:{items:[],total:0,pages:0,permissions:{product:true,service:true}}}));
  10  |   await page.route("**/api/v1/access/setup", r => r.fulfill({json:{companyId:1,ready:true,items:[]}}));
  11  |   await page.route("**/api/v1/employees/workbench/home**", r => r.fulfill({json:{pending_counts:{}}}));
  12  | }
  13  | async function menu(page: Page, query: string) {
  14  |   const navigation = page.locator(".module-menu").first();
  15  |   await navigation.getByRole("textbox", {name:"Find a page in this application"}).fill(query);
  16  |   return navigation;
  17  | }
  18  | 
  19  | test("CRM menu opens capture directly without navigating to the list", async ({page}) => {
  20  |   await authenticateCrm(page);
  21  |   await page.route("**/api/v1/access/settings/defaults/effective", r => r.fulfill({json:{values:{},modules:{},companyId:1}}));
  22  |   await page.route("**/api/v1/catalog/items**", r => r.fulfill({json:{items:[],total:0,pages:0,permissions:{product:true,service:true}}}));
  23  |   await page.route("**/api/v1/access/setup", r => r.fulfill({json:{companyId:1,ready:true,items:[]}})); await page.goto("/crm/contacts");
  24  |   const navigation = await menu(page,"Contacts");
  25  |   await navigation.getByRole("button",{name:"Create Contact",exact:true}).click();
  26  |   await expect(page.getByRole("dialog")).toContainText("Create contact");
  27  |   await expect(page).toHaveURL(/\/crm\/contacts$/);
  28  |   await page.keyboard.press("Escape");
  29  |   await expect(page.getByRole("dialog")).toHaveCount(0);
  30  |   await navigation.getByRole("button",{name:"Create Contact",exact:true}).click();
  31  |   await expect(page.getByRole("dialog")).toContainText("Create contact");
  32  | });
  33  | 
  34  | test("PMS project shortcut keeps the chosen workspace and opens its project form", async ({page}) => {
  35  |   await setup(page);
  36  |   await page.route("**/api/v1/project-management/**", r => {
  37  |     const path = new URL(r.request().url()).pathname;
  38  |     return r.fulfill({json:path.endsWith("/workspaces")?[{id:7,name:"Design studio",role:"Owner"}]:path.endsWith("/overview")?{role:"Owner",projects:[],tasks:[]}:path.endsWith("/workspaces/7")?{id:7,name:"Design studio",role:"Owner"}:path.includes("custom-fields")?{fields:[]}:[]});
  39  |   });
  40  |   await page.goto("/pms/projects?workspace=7");
  41  |   const navigation = await menu(page,"Projects");
  42  |   await navigation.getByRole("button",{name:"Create Project",exact:true}).click();
  43  |   await expect(page.getByRole("dialog").getByRole("textbox",{name:"Project name",exact:true})).toBeVisible();
  44  |   await expect(page).toHaveURL(/workspace=7/);
  45  | });
  46  | 
  47  | test("sales menu focuses the existing order form without submitting it", async ({page}) => {
  48  |   await setup(page); let writes=0;
  49  |   page.on("request", r => {if(r.url().includes("/api/")&&r.method()==="POST") writes++;});
  50  |   await page.goto("/srm/sales-orders"); const navigation=await menu(page,"Sales orders");
  51  |   await navigation.getByRole("button",{name:"Create Sales order",exact:true}).click();
  52  |   await expect(page).toHaveURL(/sales-orders$/);
  53  |   await expect(page.locator("[data-smart-create=true]")).toHaveCount(1);
  54  |   await expect(page.locator("#new-record").locator("input").first()).toBeFocused();
  55  |   expect(writes).toBe(0);
  56  | });
  57  | 
  58  | test("finance shortcut opens the voucher draft", async ({page}) => {
  59  |   await setup(page); await page.goto("/fam/vouchers"); const navigation=await menu(page,"Vouchers");
  60  |   await navigation.getByRole("button",{name:"Create Voucher",exact:true}).click();
  61  |   await expect(page).toHaveURL(/\/fam\/vouchers$/);
  62  |   await expect(page.locator("[data-smart-create=true]")).toHaveCount(1);
  63  | });
  64  | 
  65  | test("HR employee shortcut opens the shared employee form", async ({page}) => {
  66  |   await setup(page); await page.goto("/hrms/employees"); const navigation=await menu(page,"Employees");
  67  |   await navigation.getByRole("button",{name:"Create Employee",exact:true}).click();
  68  |   await expect(page.getByRole("dialog")).toContainText("Create employee");
  69  |   await expect(page.getByRole("dialog").getByRole("textbox",{name:/^First Name/})).toBeVisible();
  70  | });
  71  | 
  72  | test("view-only sales users do not receive create shortcuts", async ({page}) => {
  73  |   await setup(page,"srm_viewer"); await page.goto("/srm/sales-orders"); const navigation=await menu(page,"Sales orders");
  74  |   await expect(navigation.locator(".module-menu-create")).toHaveCount(0);
  75  |   await expect(navigation.getByRole("link",{name:"Sales Orders",exact:true})).toBeVisible();
  76  | });
  77  | 
  78  | test("customization shortcut opens the field editor and can be reused", async ({page}) => {
  79  |   await setup(page); await page.route("**/api/v1/customization/**",r=>r.fulfill({json:{items:[]}}));
  80  |   await page.goto("/admin/customization/fields"); const navigation=await menu(page,"Fields");
  81  |   await navigation.getByRole("button",{name:"Create Field",exact:true}).click();
  82  |   await expect(page.getByRole("dialog")).toBeVisible();
  83  |   await page.keyboard.press("Escape");
  84  |   await navigation.getByRole("button",{name:"Create Field",exact:true}).click();
  85  |   await expect(page.getByRole("dialog")).toBeVisible();
  86  | });
  87  | 
  88  | test("catalog quick create works on the same page repeatedly", async ({page}) => {
  89  |   await setup(page); await page.route("**/api/v1/catalog/items**",r=>r.fulfill({json:{items:[],total:0,pages:0,permissions:{product:true,service:true}}}));
  90  |   await page.goto("/srm/inventory/products"); const navigation=await menu(page,"Products");
  91  |   await navigation.getByRole("button",{name:"Create Catalog item",exact:true}).first().click();
  92  |   await expect(page.getByRole("dialog")).toBeVisible(); await page.keyboard.press("Escape");
  93  |   await navigation.getByRole("button",{name:"Create Catalog item",exact:true}).first().click();
  94  |   await expect(page.getByRole("dialog")).toBeVisible();
  95  | });
  96  | 
  97  | test("ellipsis offers contextual creation and configuration without changing pages", async ({page}) => {
  98  |   await setup(page); await page.goto("/crm/contacts"); const navigation=await menu(page,"Contacts");
  99  |   await navigation.getByRole("button",{name:"More options for Contacts",exact:true}).click();
  100 |   const dropdown=page.getByRole("menu").first();
  101 |   await expect(dropdown.getByRole("menuitem",{name:"Add to favorites",exact:true})).toBeVisible();
  102 |   await expect(dropdown.getByRole("menuitem",{name:"Custom fields",exact:true})).toBeVisible();
  103 |   await expect(page).toHaveURL(/\/crm\/contacts$/);
  104 |   await dropdown.getByRole("menuitem",{name:"Create new",exact:true}).hover();
  105 |   await page.getByRole("menuitem",{name:"Contact",exact:true}).click();
> 106 |   await expect(page.getByRole("dialog")).toContainText("Create contact");
      |                                          ^ Error: expect(locator).toContainText(expected) failed
  107 | });
  108 | 
  109 | test("menu appearance and favorites persist without renaming business records", async ({page}) => {
  110 |   await setup(page);let writes=0;
  111 |   page.on("request",r=>{if(r.url().includes("/api/")&&["POST","PUT","PATCH","DELETE"].includes(r.method()))writes++;});
  112 |   await page.goto("/crm/contacts");let navigation=await menu(page,"Contacts");
  113 |   await navigation.getByRole("button",{name:"More options for Contacts",exact:true}).click();
  114 |   await page.getByRole("menuitem",{name:"Rename menu item",exact:true}).click();
  115 |   const dialog=page.getByRole("dialog");await dialog.getByLabel("Menu name",{exact:true}).fill("Our contacts");
  116 |   await dialog.getByLabel("Menu icon",{exact:true}).selectOption("people");await dialog.getByRole("button",{name:"green menu color",exact:true}).click();await dialog.getByRole("button",{name:"Save menu item",exact:true}).click();
  117 |   await navigation.getByRole("button",{name:"More options for Our contacts",exact:true}).click();
  118 |   await page.getByRole("menuitem",{name:"Add to favorites",exact:true}).click();await page.reload();
  119 |   navigation=page.locator(".module-menu").first();await expect(navigation.getByRole("list",{name:"Favorite menu pages"})).toContainText("Our contacts");
  120 |   await menu(page,"Our contacts");await expect(navigation.getByRole("link",{name:"Our contacts",exact:true}).first()).toBeVisible();
  121 |   expect(writes).toBe(0);
  122 | });
  123 | 
  124 | test("ellipsis copy link preserves workspace context and keyboard dismissal", async ({page,context}) => {
  125 |   await context.grantPermissions(["clipboard-read","clipboard-write"]);await setup(page);
  126 |   await page.route("**/api/v1/project-management/workspaces",r=>r.fulfill({json:[{id:7,name:"Design",role:"Guest"}]}));
  127 |   await page.goto("/pms/projects?workspace=7");const navigation=await menu(page,"Projects");
  128 |   const more=navigation.getByRole("button",{name:"More options for Projects",exact:true});await more.click();
  129 |   await page.getByRole("menuitem",{name:"Copy link",exact:true}).click();
  130 |   await expect.poll(()=>page.evaluate(()=>navigator.clipboard.readText())).toContain("/pms/projects?workspace=7");
  131 |   await more.click();await page.keyboard.press("Escape");await expect(page.getByRole("menu")).toHaveCount(0);await expect(more).toBeFocused();
  132 |   await expect(navigation.getByRole("button",{name:"Create Project",exact:true})).toHaveCount(0);
  133 | });
  134 | 
  135 | test("mobile menu create closes the drawer and focuses employee capture", async ({page}) => {
  136 |   await page.setViewportSize({width:390,height:844});await setup(page);await page.goto("/hrms/employees");
  137 |   await page.getByRole("button",{name:"Open navigation",exact:true}).click();
  138 |   const navigation=await menu(page,"Employees");await navigation.getByRole("button",{name:"Create Employee",exact:true}).click();
  139 |   await expect(page.getByRole("dialog")).toContainText("Create employee");
  140 |   await expect(page.getByRole("button",{name:"Close navigation",exact:true})).not.toBeVisible();
  141 |   expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth+1)).toBeTruthy();
  142 | });
  143 | 
  144 | for (const [path,query,label] of [["/hrms/employees","Employees","Employees"],["/srm/sales-orders","Sales orders","Sales Orders"],["/fam/vouchers","Vouchers","Vouchers"],["/ai/copilot","Copilot","Copilot"],["/analytics/reports","Reports","Reports"],["/admin/customization/fields","Fields","Fields"]]) {
  145 |   test(`context menu works in ${path}`, async ({page})=>{
  146 |     await setup(page);await page.goto(path);const navigation=await menu(page,query);
  147 |     await navigation.getByRole("button",{name:`More options for ${label}`,exact:true}).click();
  148 |     await expect(page.getByRole("menuitem",{name:"Copy link",exact:true})).toBeVisible();
  149 |     await expect(page.getByRole("menuitem",{name:"Delete",exact:true})).toHaveCount(0);
  150 |     await page.keyboard.press("Escape");await expect(page.getByRole("menu")).toHaveCount(0);
  151 |   });
  152 | }
  153 | 
  154 | test("Power Apps quick creation preserves the selected environment",async({page})=>{
  155 |   await setup(page);await page.route("**/api/v1/power-apps/**",r=>{
  156 |     const path=new URL(r.request().url()).pathname;
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
```