import { test, expect } from "../frontend/node_modules/playwright/test";

async function authenticate(page: any, initialModules = ["fam", "inventory"]) {
  let activeModules = [...initialModules];
  await page.route("**/api/v1/**", async (route: any) => {
    await route.fulfill({ contentType: "application/json", body: "{}" });
  });
  await page.route("**/api/v1/business-os/modules", async (route: any) => {
    if (route.request().method() === "PUT") {
      const payload = route.request().postDataJSON();
      activeModules = payload.enabled_modules;
      await route.fulfill({ contentType: "application/json", body: JSON.stringify(modulesResponse(activeModules)) });
      return;
    }
    await route.fulfill({ contentType: "application/json", body: JSON.stringify(modulesResponse(activeModules)) });
  });
  await page.route("**/api/v1/business-os/integration-rules", async (route: any) => {
    await route.fulfill({ contentType: "application/json", body: JSON.stringify(integrationRules(activeModules)) });
  });
  await page.route("**/api/v1/business-os/dashboard", async (route: any) => {
    await route.fulfill({ contentType: "application/json", body: JSON.stringify({ enabled_modules: activeModules, widgets: dashboardWidgets(activeModules) }) });
  });
  await page.route("**/api/v1/business-os/reports/catalog", async (route: any) => {
    await route.fulfill({ contentType: "application/json", body: JSON.stringify({ enabled_modules: activeModules, reports: reportCards(activeModules) }) });
  });
  await page.route("**/api/v1/business-os/rbac/catalog", async (route: any) => {
    await route.fulfill({ contentType: "application/json", body: JSON.stringify({ enabled_modules: activeModules, roles: roleCards(activeModules) }) });
  });
  await page.route("**/api/v1/business-os/customer-720", async (route: any) => {
    await route.fulfill({ contentType: "application/json", body: JSON.stringify({ enabled_modules: activeModules, sections: customer720(activeModules) }) });
  });
  await page.route("**/api/v1/business-os/ai/ask", async (route: any) => {
    const question = String(route.request().postDataJSON().question || "").toLowerCase();
    const blocked = question.includes("crm") && !activeModules.includes("crm");
    await route.fulfill({ contentType: "application/json", body: JSON.stringify({ allowed: !blocked, module: blocked ? "crm" : "business_os", answer: blocked ? "CRM is not enabled for this company, so I cannot answer that question or expose its data." : "Module-aware AI check passed.", evidence: { enabled_modules: activeModules } }) });
  });
  await page.route("**/api/v1/business-os/lifecycle/**", async (route: any) => route.fulfill({ contentType: "application/json", body: "[]" }));
  await page.route("**/api/v1/auth/sso/providers/active", async (route: any) => route.fulfill({ contentType: "application/json", body: "[]" }));
  await page.route("**/api/v1/auth/login", async (route: any) => {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        access_token: "bos-token",
        refresh_token: "bos-refresh",
        user_id: 1,
        email: "admin@test.com",
        role: "admin",
        is_superuser: true,
        employee_id: null,
      }),
    });
  });
  await page.route("**/api/v1/auth/me", async (route: any) => route.fulfill({ contentType: "application/json", body: JSON.stringify({ id: 1, email: "admin@test.com", role: { name: "admin" }, is_superuser: true }) }));
  await page.goto("/login", { waitUntil: "domcontentloaded" });
  await page.getByLabel("Email address").fill("admin@test.com");
  await page.getByLabel("Password").fill("Password@123");
  await page.getByRole("button", { name: "Sign in" }).click();
  await page.waitForURL(/\/hrms|\/admin|\/$/);
}

async function navigateInApp(page: any, path: string) {
  await page.evaluate((nextPath: string) => {
    window.history.pushState({}, "", nextPath);
    window.dispatchEvent(new PopStateEvent("popstate"));
  }, path);
  await page.waitForLoadState("networkidle");
}

function modulesResponse(enabled: string[]) {
  const moduleKeys = ["fam", "inventory", "crm", "srm", "project_management", "hrms", "ai", "portals", "communication"];
  return {
    company_id: 1,
    enabled_modules: enabled,
    modules: moduleKeys.map((key) => ({ module_key: key, display_name: key === "project_management" ? "PMS" : key.toUpperCase(), enabled: enabled.includes(key), is_financial_backbone: key === "fam", home_path: key === "inventory" ? "/Inventory" : `/${key}` })),
    supported_combinations: [
      { name: "Accounts only", modules: ["fam"] },
      { name: "Accounts + Inventory", modules: ["fam", "inventory"] },
      { name: "CRM only", modules: ["crm"] },
      { name: "CRM + SRM", modules: ["crm", "srm"] },
      { name: "SRM only", modules: ["srm"] },
      { name: "PMS only", modules: ["project_management"] },
      { name: "SRM + PMS", modules: ["srm", "project_management"] },
      { name: "PMS + FAM invoicing", modules: ["project_management", "fam"] },
      { name: "Accounts + Inventory + SRM", modules: ["fam", "inventory", "srm"] },
      { name: "Full Business OS", modules: moduleKeys },
    ],
  };
}

function integrationRules(enabled: string[]) {
  const active = new Set(enabled);
  const rows = [
    ["crm_won_to_srm_order", "crm", "srm", "deal_won", "create_sales_order"],
    ["srm_engagement_to_pms_project", "srm", "project_management", "engagement_confirmed", "create_project"],
    ["pms_timesheet_to_fam_invoice", "project_management", "fam", "timesheet_approved", "create_invoice_draft"],
    ["inventory_grni_posting", "inventory", "fam", "grn_posted", "post_accounting"],
  ];
  return rows.map(([rule_key, source_module, target_module, event_name, action_name], index) => ({
    id: index + 1,
    rule_key,
    source_module,
    target_module,
    event_name,
    action_name,
    enabled: true,
    source_enabled: active.has(source_module),
    target_enabled: active.has(target_module),
    effective: active.has(source_module) && active.has(target_module),
  }));
}

function dashboardWidgets(enabled: string[]) {
  if (enabled.length === 1 && enabled.includes("fam")) return ["Cash", "Receivables", "Payables", "GST", "Trial Balance", "P&L", "Balance Sheet"].map(title => ({ title, status: "enabled", evidence: "Visible because required modules are enabled." }));
  if (enabled.includes("fam") && enabled.includes("inventory") && !enabled.includes("crm")) return ["Cash", "Stock Value", "Low Stock", "COGS", "GRNI", "Valuation", "HSN Summary", "Gross Margin"].map(title => ({ title, status: "enabled", evidence: "Visible because required modules are enabled." }));
  if (enabled.includes("crm") && enabled.includes("srm")) return ["Pipeline", "Won Deals", "Sales Orders", "Contracts", "Billing Plans", "Invoices", "Collections"].map(title => ({ title, status: "enabled", evidence: "Visible because required modules are enabled." }));
  return ["Lead-to-Cash", "Procure-to-Pay", "Project-to-Profit", "Inventory-to-Accounting", "Cash Flow", "Business Health Score"].map(title => ({ title, status: "enabled", evidence: "Visible because required modules are enabled." }));
}

function reportCards(enabled: string[]) {
  const active = new Set(enabled);
  const rows = [
    ["lead_to_cash", "Lead-to-Cash", ["crm", "srm"]],
    ["inventory_valuation", "Inventory Valuation", ["inventory"]],
    ["gst_summary", "GST Summary", ["fam"]],
    ["project_profitability", "Project Profitability", ["project_management"]],
    ["cash_collection", "Cash Collection", ["srm"]],
    ["stock_cogs", "Stock COGS", ["inventory", "fam"]],
  ];
  return rows.map(([key, title, required]) => {
    const req = required as string[];
    const enabledCard = req.every(item => active.has(item));
    return { key, title, required_modules: req, enabled: enabledCard, reason: enabledCard ? "Available for enabled modules." : `Missing: ${req.filter(item => !active.has(item)).join(", ")}.` };
  });
}

function roleCards(enabled: string[]) {
  const active = new Set(enabled);
  return [
    { role: "Accounts Admin", available: active.has("fam"), permissions: active.has("fam") ? ["fam_view", "fam_manage"] : [], reason: active.has("fam") ? "Role available." : "Enable fam to use this role." },
    { role: "Inventory Manager", available: active.has("inventory"), permissions: active.has("inventory") ? ["fam_inventory_view"] : [], reason: active.has("inventory") ? "Role available." : "Enable inventory to use this role." },
    { role: "CRM Sales Executive", available: active.has("crm"), permissions: active.has("crm") ? ["crm_view"] : [], reason: active.has("crm") ? "Role available." : "Enable crm to use this role." },
  ];
}

function customer720(enabled: string[]) {
  return enabled.filter(module => ["crm", "srm", "project_management", "fam", "inventory"].includes(module)).map(module => ({ module, title: module === "fam" ? "FAM" : module.toUpperCase(), description: `${module} data section` }));
}

test("Business OS admin toggles modules and hides disabled routes", async ({ page }) => {
  await authenticate(page);
  await navigateInApp(page, "/admin/business-os/modules");
  await expect(page.getByText("Business OS Modular Foundation")).toBeVisible();
  await expect(page.getByText("Accounts only")).toBeVisible();
  await page.getByRole("button", { name: /CRM only/ }).click();
  await page.getByRole("button", { name: "Save modules" }).click();
  await expect(page.getByText("Business OS module configuration saved")).toBeVisible();
  expect(await page.evaluate(() => localStorage.getItem("bos-enabled-modules"))).toBe("crm");
});

test("Inventory link uses /Inventory canonical URL", async ({ page }) => {
  await authenticate(page);
  await navigateInApp(page, "/");
  await expect(page.getByRole("link", { name: /Inventory/ })).toHaveAttribute("href", "/Inventory");
});

test("Business OS integration rules reflect optional handoff combinations", async ({ page }) => {
  await authenticate(page, ["crm"]);
  await navigateInApp(page, "/admin/business-os/modules");
  const combinations = [
    { name: /CRM only/, expected: "crm" },
    { name: /CRM \+ SRM/, expected: "crm,srm" },
    { name: /SRM \+ PMS/, expected: "srm,project_management" },
    { name: /PMS only/, expected: "project_management" },
    { name: /PMS \+ FAM invoicing/, expected: "project_management,fam" },
    { name: /^Accounts \+ Inventory fam, inventory$/, expected: "fam,inventory" },
    { name: /^Accounts \+ Inventory \+ SRM/, expected: "fam,inventory,srm" },
    { name: /Full Business OS/, expected: "fam,inventory,crm,srm,project_management,hrms,ai,portals,communication" },
  ];
  for (const combo of combinations) {
    await page.getByRole("button", { name: combo.name }).click();
    await page.getByRole("button", { name: "Save modules" }).click();
    expect(await page.evaluate(() => localStorage.getItem("bos-enabled-modules"))).toBe(combo.expected);
  }
  await navigateInApp(page, "/admin/business-os/integrations");
  await expect(page.getByText("crm_won_to_srm_order")).toBeVisible();
  await expect(page.getByText("Effective").first()).toBeVisible();
});

test("Business OS workspace changes dashboard reports customer 720 RBAC and AI by enabled modules", async ({ page }) => {
  await authenticate(page, ["fam"]);
  await navigateInApp(page, "/business-os/dashboard");
  await expect(page.getByText("Cash")).toBeVisible();
  await expect(page.getByText("GST")).toBeVisible();
  await expect(page.getByText("Pipeline")).toHaveCount(0);

  await navigateInApp(page, "/business-os/reports");
  await expect(page.getByText("GST Summary")).toBeVisible();
  await expect(page.getByText("Inventory Valuation")).toBeVisible();
  await expect(page.getByText("Missing: inventory.").first()).toBeVisible();

  await navigateInApp(page, "/business-os/customer-720");
  await expect(page.getByRole("heading", { name: "FAM" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "CRM" })).toHaveCount(0);

  await navigateInApp(page, "/business-os/ai");
  await expect(page.getByText("Accounts Admin")).toBeVisible();
  await expect(page.getByText("CRM Sales Executive")).toBeVisible();
  await page.getByRole("button", { name: "Ask" }).click();
  await expect(page.getByText(/CRM is not enabled/)).toBeVisible();
});
