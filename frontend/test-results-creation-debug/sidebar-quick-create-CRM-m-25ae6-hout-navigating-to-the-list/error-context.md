# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: sidebar-quick-create.spec.ts >> CRM menu opens capture directly without navigating to the list
- Location: playwright\sidebar-quick-create.spec.ts:17:5

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
  - navigation "CRM pages":
    - text: CRM / Contacts
    - button "Explore pages"
  - main:
    - text: CRM
    - img
    - text: Contacts
    - heading "Contacts" [level=1]
    - text: 0 contacts
    - paragraph: Manage people, lifecycle stages, follow-up dates, and account links.
    - button "Review duplicates & merge":
      - img
      - text: Review duplicates & merge
    - button "Create contact":
      - img
      - text: Create contact
    - img
    - text: Search contacts
    - textbox "Search contacts":
      - /placeholder: Search contacts...
    - button "All contacts"
    - button "My contacts"
    - button "Due this week"
    - button "No follow-up"
    - button "Filters":
      - img
      - text: Filters
    - button "Columns":
      - img
      - text: Columns
    - button "Import":
      - img
      - text: Import
    - button "Export":
      - img
      - text: Export
    - text: Contacts could not be loaded.
    - table:
      - rowgroup:
        - row "Select all contacts Contact Company Email Phone Lifecycle stage Status Owner Next follow-up Updated Actions":
          - columnheader "Select all contacts":
            - checkbox "Select all contacts"
          - columnheader "Contact":
            - button "Contact":
              - text: Contact
              - img
          - columnheader "Company":
            - button "Company":
              - text: Company
              - img
          - columnheader "Email":
            - button "Email":
              - text: Email
              - img
          - columnheader "Phone":
            - button "Phone":
              - text: Phone
              - img
          - columnheader "Lifecycle stage":
            - button "Lifecycle stage":
              - text: Lifecycle stage
              - img
          - columnheader "Status":
            - button "Status":
              - text: Status
              - img
          - columnheader "Owner":
            - button "Owner":
              - text: Owner
              - img
          - columnheader "Next follow-up":
            - button "Next follow-up":
              - text: Next follow-up
              - img
          - columnheader "Updated":
            - button "Updated":
              - text: Updated
              - img
          - columnheader "Actions"
      - rowgroup:
        - row "No contacts match the current search or filters.":
          - cell "No contacts match the current search or filters."
    - text: Showing 0 to 0 of 0 contacts
    - combobox "Rows per page":
      - option "10 rows" [selected]
      - option "25 rows"
      - option "50 rows"
      - option "100 rows"
    - button "Previous" [disabled]:
      - img
    - text: 1 / 1
    - button "Next" [disabled]:
      - img
  - complementary: Select a contact to inspect details.
- button "Ask AI Assistant":
  - img
  - text: Ask AI Assistant
- region "Notifications (F8)":
  - list
- tooltip "Quick capture contact"
```

# Test source

```ts
  1   | import { resolve } from "node:path";
  2   | import { test, expect, type Page } from "../frontend/node_modules/playwright/test";
  3   | import { authenticate } from "./srm-test-utils";
  4   | 
  5   | async function setup(page: Page, role: "admin" | "srm_viewer" = "admin") {
  6   |   await authenticate(page, role);
  7   |   await page.route("**/api/v1/access/settings/defaults/effective", r => r.fulfill({json:{values:{},modules:{},companyId:1}}));
  8   |   await page.route("**/api/v1/access/setup", r => r.fulfill({json:{companyId:1,ready:true,items:[]}}));
  9   |   await page.route("**/api/v1/employees/workbench/home**", r => r.fulfill({json:{pending_counts:{}}}));
  10  | }
  11  | async function menu(page: Page, query: string) {
  12  |   const navigation = page.locator(".module-menu").first();
  13  |   await navigation.getByRole("textbox", {name:"Find a page in this application"}).fill(query);
  14  |   return navigation;
  15  | }
  16  | 
  17  | test("CRM menu opens capture directly without navigating to the list", async ({page}) => {
  18  |   page.on("console",m=>{if(m.text().includes("creation-audit-stack"))console.log(m.text());});
  19  |   await setup(page); await page.goto("/crm/contacts");
  20  |   const navigation = await menu(page,"Contacts");
  21  |   await navigation.getByRole("button",{name:"Create Contact",exact:true}).click();
> 22  |   await expect(page.getByRole("dialog")).toContainText("Create contact");
      |                                          ^ Error: expect(locator).toContainText(expected) failed
  23  |   await expect(page).toHaveURL(/\/crm\/contacts$/);
  24  |   await page.keyboard.press("Escape");
  25  |   await expect(page.getByRole("dialog")).toHaveCount(0);
  26  |   await navigation.getByRole("button",{name:"Create Contact",exact:true}).click();
  27  |   await expect(page.getByRole("dialog")).toContainText("Create contact");
  28  | });
  29  | 
  30  | test("PMS project shortcut keeps the chosen workspace and opens its project form", async ({page}) => {
  31  |   await setup(page);
  32  |   await page.route("**/api/v1/project-management/**", r => {
  33  |     const path = new URL(r.request().url()).pathname;
  34  |     return r.fulfill({json:path.endsWith("/workspaces")?[{id:7,name:"Design studio",role:"Owner"}]:path.endsWith("/overview")?{role:"Owner",projects:[],tasks:[]}:path.endsWith("/workspaces/7")?{id:7,name:"Design studio",role:"Owner"}:path.includes("custom-fields")?{fields:[]}:[]});
  35  |   });
  36  |   await page.goto("/pms/projects?workspace=7");
  37  |   const navigation = await menu(page,"Projects");
  38  |   await navigation.getByRole("button",{name:"Create Project",exact:true}).click();
  39  |   await expect(page.getByRole("dialog").getByRole("textbox",{name:"Project name",exact:true})).toBeVisible();
  40  |   await expect(page).toHaveURL(/workspace=7/);
  41  | });
  42  | 
  43  | test("sales menu focuses the existing order form without submitting it", async ({page}) => {
  44  |   await setup(page); let writes=0;
  45  |   page.on("request", r => {if(r.url().includes("/api/")&&r.method()==="POST") writes++;});
  46  |   await page.goto("/srm/sales-orders"); const navigation=await menu(page,"Sales orders");
  47  |   await navigation.getByRole("button",{name:"Create Sales order",exact:true}).click();
  48  |   await expect(page).toHaveURL(/sales-orders$/);
  49  |   await expect(page.locator("[data-smart-create=true]")).toHaveCount(1);
  50  |   await expect(page.locator("#new-record").locator("input").first()).toBeFocused();
  51  |   expect(writes).toBe(0);
  52  | });
  53  | 
  54  | test("finance shortcut opens the voucher draft", async ({page}) => {
  55  |   await setup(page); await page.goto("/fam/vouchers"); const navigation=await menu(page,"Vouchers");
  56  |   await navigation.getByRole("button",{name:"Create Voucher",exact:true}).click();
  57  |   await expect(page).toHaveURL(/\/fam\/vouchers$/);
  58  |   await expect(page.locator("[data-smart-create=true]")).toHaveCount(1);
  59  | });
  60  | 
  61  | test("HR employee shortcut opens the shared employee form", async ({page}) => {
  62  |   await setup(page); await page.goto("/hrms/employees"); const navigation=await menu(page,"Employees");
  63  |   await navigation.getByRole("button",{name:"Create Employee",exact:true}).click();
  64  |   await expect(page.getByRole("dialog")).toContainText("Create employee");
  65  |   await expect(page.getByRole("dialog").getByRole("textbox",{name:/^First Name/})).toBeVisible();
  66  | });
  67  | 
  68  | test("view-only sales users do not receive create shortcuts", async ({page}) => {
  69  |   await setup(page,"srm_viewer"); await page.goto("/srm/sales-orders"); const navigation=await menu(page,"Sales orders");
  70  |   await expect(navigation.locator(".module-menu-create")).toHaveCount(0);
  71  |   await expect(navigation.getByRole("link",{name:"Sales Orders",exact:true})).toBeVisible();
  72  | });
  73  | 
  74  | test("customization shortcut opens the field editor and can be reused", async ({page}) => {
  75  |   await setup(page); await page.route("**/api/v1/customization/**",r=>r.fulfill({json:{items:[]}}));
  76  |   await page.goto("/admin/customization/fields"); const navigation=await menu(page,"Fields");
  77  |   await navigation.getByRole("button",{name:"Create Field",exact:true}).click();
  78  |   await expect(page.getByRole("dialog")).toBeVisible();
  79  |   await page.keyboard.press("Escape");
  80  |   await navigation.getByRole("button",{name:"Create Field",exact:true}).click();
  81  |   await expect(page.getByRole("dialog")).toBeVisible();
  82  | });
  83  | 
  84  | test("catalog quick create works on the same page repeatedly", async ({page}) => {
  85  |   await setup(page); await page.route("**/api/v1/catalog/items**",r=>r.fulfill({json:{items:[],total:0,pages:0,permissions:{product:true,service:true}}}));
  86  |   await page.goto("/srm/inventory/products"); const navigation=await menu(page,"Products");
  87  |   await navigation.getByRole("button",{name:"Create Catalog item",exact:true}).first().click();
  88  |   await expect(page.getByRole("dialog")).toBeVisible(); await page.keyboard.press("Escape");
  89  |   await navigation.getByRole("button",{name:"Create Catalog item",exact:true}).first().click();
  90  |   await expect(page.getByRole("dialog")).toBeVisible();
  91  | });
  92  | 
  93  | test("ellipsis offers contextual creation and configuration without changing pages", async ({page}) => {
  94  |   await setup(page); await page.goto("/crm/contacts"); const navigation=await menu(page,"Contacts");
  95  |   await navigation.getByRole("button",{name:"More options for Contacts",exact:true}).click();
  96  |   const dropdown=page.getByRole("menu").first();
  97  |   await expect(dropdown.getByRole("menuitem",{name:"Add to favorites",exact:true})).toBeVisible();
  98  |   await expect(dropdown.getByRole("menuitem",{name:"Custom fields",exact:true})).toBeVisible();
  99  |   await expect(page).toHaveURL(/\/crm\/contacts$/);
  100 |   await dropdown.getByRole("menuitem",{name:"Create new",exact:true}).hover();
  101 |   await page.getByRole("menuitem",{name:"Contact",exact:true}).click();
  102 |   await expect(page.getByRole("dialog")).toContainText("Create contact");
  103 | });
  104 | 
  105 | test("menu appearance and favorites persist without renaming business records", async ({page}) => {
  106 |   await setup(page);let writes=0;
  107 |   page.on("request",r=>{if(r.url().includes("/api/")&&["POST","PUT","PATCH","DELETE"].includes(r.method()))writes++;});
  108 |   await page.goto("/crm/contacts");let navigation=await menu(page,"Contacts");
  109 |   await navigation.getByRole("button",{name:"More options for Contacts",exact:true}).click();
  110 |   await page.getByRole("menuitem",{name:"Rename menu item",exact:true}).click();
  111 |   const dialog=page.getByRole("dialog");await dialog.getByLabel("Menu name",{exact:true}).fill("Our contacts");
  112 |   await dialog.getByLabel("Menu icon",{exact:true}).selectOption("people");await dialog.getByRole("button",{name:"green menu color",exact:true}).click();await dialog.getByRole("button",{name:"Save menu item",exact:true}).click();
  113 |   await navigation.getByRole("button",{name:"More options for Our contacts",exact:true}).click();
  114 |   await page.getByRole("menuitem",{name:"Add to favorites",exact:true}).click();await page.reload();
  115 |   navigation=page.locator(".module-menu").first();await expect(navigation.getByRole("list",{name:"Favorite menu pages"})).toContainText("Our contacts");
  116 |   await menu(page,"Our contacts");await expect(navigation.getByRole("link",{name:"Our contacts",exact:true}).first()).toBeVisible();
  117 |   expect(writes).toBe(0);
  118 | });
  119 | 
  120 | test("ellipsis copy link preserves workspace context and keyboard dismissal", async ({page,context}) => {
  121 |   await context.grantPermissions(["clipboard-read","clipboard-write"]);await setup(page);
  122 |   await page.route("**/api/v1/project-management/workspaces",r=>r.fulfill({json:[{id:7,name:"Design",role:"Guest"}]}));
```