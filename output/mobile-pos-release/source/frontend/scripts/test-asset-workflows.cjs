const path = require("node:path");
const { chromium, expect: base } = require("playwright/test");
const expect = base.configure({ timeout: 30000 });
(async () => {
  process.chdir(path.resolve(__dirname, ".."));
  const { createServer } = await import("vite");
  const server = await createServer({
    root: process.cwd(),
    server: { host: "127.0.0.1", port: 0, hmr: false, watch: null },
  });
  await server.listen();
  const browser = await chromium.launch();
  try {
    const page = await browser.newPage({
        viewport: { width: 1440, height: 1100 },
      }),
      errors = [],
      writes = [];
    page.on("pageerror", (e) => errors.push(e.message));
    let asset = {
      id: 1,
      name: "Dell Latitude",
      asset_tag: "LAP-001",
      category_id: 1,
      status: "Available",
      condition: "Good",
      serial_number: "SER-001",
    };
    let custody = null,
      approvals = [],
      documents = [],
      policy = {
        recovery_enabled: true,
        recovery_limit: "500",
        reminders_enabled: true,
        reminder_days: 7,
        repeat_days: 7,
        channels: ["in_app"],
        manager_user_ids: [],
        inspection_approver_id: null,
        recovery_approver_id: null,
        exception_approver_id: null,
      };
    await page.route("**/api/v1/**", async (route) => {
      const req = route.request(),
        u = new URL(req.url()),
        p = u.pathname,
        method = req.method();
      let data = [];
      if (method === "GET") {
        if (p.endsWith("/capabilities")) data = { can_manage: true };
        else if (p.endsWith("/categories"))
          data = [
            { id: 1, name: "Laptop" },
            { id: 2, name: "Vehicles" },
          ];
        else if (p.endsWith("/employees"))
          data = [{ id: 2, name: "Team Member", employee_code: "EMP-002" }];
        else if (p.endsWith("/approvers"))
          data = [{ id: 1, name: "HR Manager" }];
        else if (p.endsWith("/policy"))
          data = { values: policy, can_configure: true };
        else if (p.endsWith("/summary"))
          data = {
            total: 1,
            returned: custody?.returned_date ? 1 : 0,
            statuses: { [asset.status]: 1 },
            categories: [{ category_id: 1, count: 1 }],
          };
        else if (p.endsWith("/insights"))
          data = {
            repair_backlog: 0,
            overdue: 0,
            due_soon: 0,
            pending_inspections: 0,
            outstanding_recoveries: "0",
            warranty_expiring: [],
            high_value: [],
            replacement_due: [],
          };
        else if (p.endsWith("/assets/"))
          data =
            asset.status === "Available"
              ? [asset]
              : u.searchParams.get("status")
                ? []
                : [asset];
        else if (p.endsWith("/assignments")) {
          data =
            custody &&
            (u.searchParams.get("active") !== "false") ===
              !custody.returned_date
              ? [custody]
              : [];
          if (u.searchParams.get("paged"))
            data = {
              items: data,
              total: data.length,
              summary: [{ label: "Records", value: data.length }],
            };
        } else if (/\/assets\/\d+$/.test(p))
          data = {
            ...asset,
            assignments: custody ? [custody] : [],
            documents,
            approvals,
            timeline: [],
          };
        else if (p.endsWith("/receipt") || p.endsWith("/certificate")) {
          await route.fulfill({
            contentType: "application/pdf",
            body: "%PDF-1.4 QA",
          });
          return;
        }
      } else {
        let body = req.headers()["content-type"]?.includes("application/json")
          ? req.postDataJSON()
          : null;
        writes.push({ p, method, body });
        if (p.endsWith("/assignments/batch")) {
          custody = {
            id: 10,
            asset_id: 1,
            asset_name: asset.name,
            asset_tag: asset.asset_tag,
            employee_id: 2,
            employee_name: "Team Member",
            assigned_date: body.assigned_date,
            expected_return_date: body.expected_return_date,
            accessories: body.accessories,
            condition_at_assignment: body.condition_at_assignment,
            acknowledged: false,
            returned_date: null,
            inspection_status: "Not Required",
            recovery_status: "None",
          };
          asset.status = "Assigned";
          data = { assignment_ids: [10], handover_group: body.request_key };
        } else if (p.endsWith("/receive")) {
          custody = {
            ...custody,
            returned_date: body.return_date,
            condition_at_return: body.condition,
            return_details: body,
            inspection_status: "Pending",
          };
          asset.status = "Pending Inspection";
          data = { id: 10 };
        } else if (p.endsWith("/inspection")) {
          custody.inspection_status = "Awaiting Approval";
          custody.inspection_approval_id = 30;
          approvals.push({
            id: 30,
            type: "asset_inspection",
            status: "Pending",
            can_decide: true,
          });
          data = approvals.at(-1);
        } else if (p.endsWith("/recovery")) {
          custody.recovery_status = "Pending";
          custody.recovery_approval_id = 31;
          approvals.push({
            id: 31,
            type: "asset_recovery",
            status: "Pending",
            can_decide: true,
          });
          data = approvals.at(-1);
        } else if (p.endsWith("/decision")) {
          const id = Number(p.split("/").at(-2));
          approvals.find((a) => a.id === id).status =
            body.decision === "approve" ? "Approved" : "Rejected";
          if (id === 30) {
            custody.inspection_status = "Approved";
            asset.status = "Available";
          } else custody.recovery_status = "Approved";
          data = approvals.find((a) => a.id === id);
        } else if (p.endsWith("/settle-recovery")) {
          custody.recovery_status = "Settled";
          data = { recovery_status: "Settled" };
        } else if (p.endsWith("/documents")) {
          data = {
            id: 99,
            name: "photo.png",
            version: 1,
            mime_type: "image/png",
          };
          documents.push(data);
        } else if (p.endsWith("/policy")) {
          policy = body;
          data = policy;
        } else if (p.endsWith("/assets/")) {
          data = { ...asset, id: 2, ...body };
        }
      }
      await route.fulfill({
        status:
          method === "POST" &&
          (p.endsWith("/assets/") ||
            p.endsWith("/assignments/batch") ||
            p.endsWith("/documents"))
            ? 201
            : 200,
        json: data,
      });
    });
    await page.route("**/assets-workflows-qa", (r) =>
      r.fulfill({
        contentType: "text/html",
        body: '<meta name="viewport" content="width=device-width,initial-scale=1"><div id="root"></div><script type="module">import R from "/@react-refresh";R.injectIntoGlobalHook(window);window.$RefreshReg$=()=>{};window.$RefreshSig$=()=>type=>type;window.__vite_plugin_react_preamble_installed__=true;await import("/scripts/fixtures/mobile-assets.tsx");</script>',
      }),
    );
    await page.goto(
      "http://127.0.0.1:" +
        server.httpServer.address().port +
        "/assets-workflows-qa",
    );
    await expect(
      page.getByRole("heading", { name: "Company Assets", exact: true }),
    ).toBeVisible();
    await page
      .getByRole("button", { name: "Register asset", exact: true })
      .click();
    let dialog = page.getByRole("dialog").last();
    await dialog
      .getByLabel("Asset name", { exact: true })
      .fill("Company scooter");
    await dialog.getByLabel("Unique company asset tag").fill("BIKE-001");
    await dialog.getByLabel("Category", { exact: true }).selectOption("2");
    await dialog
      .getByRole("button", { name: "Additional details", exact: true })
      .click();
    await dialog.getByLabel("Chassis number").fill("CHASSIS-001");
    await dialog.getByLabel("Engine number").fill("ENGINE-001");
    await dialog
      .getByRole("button", { name: "Purchase & finance", exact: true })
      .click();
    await dialog.getByLabel("Supplier", { exact: true }).fill("Fleet supplier");
    await dialog.getByLabel("Purchase cost", { exact: true }).fill("80000");
    await dialog
      .getByRole("button", { name: "Review asset", exact: true })
      .click();
    await expect(dialog).toContainText("CHASSIS-001");
    await dialog
      .getByRole("button", { name: "Save asset", exact: true })
      .click();
    await expect(page.getByRole("dialog")).toHaveCount(0);
    expect(
      writes.find((w) => w.p.endsWith("/assets/")).body.details.engine_number,
    ).toBe("ENGINE-001");
    await page
      .getByRole("button", { name: "Assign multiple assets", exact: true })
      .click();
    dialog = page.getByRole("dialog").last();
    await dialog.getByPlaceholder("Name or employee code").fill("Team");
    await dialog.locator("select").first().selectOption("2");
    await dialog.getByRole("checkbox").check();
    await dialog.getByLabel("Expected return date").fill("2026-12-10");
    await dialog
      .getByLabel("Accessories provided (comma separated)")
      .fill("Charger, Bag");
    await dialog
      .getByRole("button", { name: "Assign 1 assets", exact: true })
      .click();
    await expect(dialog).toContainText("Handover saved");
    expect(
      writes.find((w) => w.p.endsWith("/assignments/batch")).body.accessories,
    ).toEqual(["Charger", "Bag"]);
    const download = page.waitForEvent("download");
    await dialog
      .getByRole("button", { name: "Download handover receipt" })
      .click();
    expect((await download).suggestedFilename()).toBe("asset-handover.pdf");
    await dialog.getByRole("button", { name: "Done", exact: true }).click();
    await page
      .getByRole("button", { name: "Employee custody", exact: true })
      .click();
    await page
      .getByRole("button", { name: "View details", exact: true })
      .click();
    await page
      .getByRole("dialog")
      .last()
      .getByRole("button", { name: "Record return", exact: true })
      .click();
    dialog = page.getByRole("dialog").last();
    await dialog.getByLabel("Physical condition").selectOption("Good");
    await dialog.getByLabel("Charger", { exact: true }).check();
    await dialog.getByLabel("Bag", { exact: true }).check();
    await dialog.getByLabel("Upload asset evidence").setInputFiles({
      name: "photo.png",
      mimeType: "image/png",
      buffer: Buffer.from("PNG fixture"),
    });
    await expect(
      dialog.locator(".asset-document-row").filter({ hasText: "photo.png" }),
    ).toBeVisible();
    await dialog
      .getByRole("button", { name: "Confirm return", exact: true })
      .click();
    await expect
      .poll(() => writes.some((w) => w.p.endsWith("/receive")))
      .toBe(true);
    expect(
      writes.find((w) => w.p.endsWith("/receive")).body.photo_document_ids,
    ).toEqual([99]);
    await page
      .getByRole("button", { name: "Close dialog", exact: true })
      .click();
    await page
      .getByRole("button", { name: "Return history", exact: true })
      .click();
    await page
      .getByRole("button", { name: "View details", exact: true })
      .click();
    await page
      .getByRole("dialog")
      .last()
      .getByRole("button", { name: "Inspect / approve" })
      .click();
    dialog = page.getByRole("dialog").last();
    await dialog
      .getByLabel("Inspector comments / approval decision reason")
      .fill("Physical condition verified with photos");
    await dialog
      .getByRole("button", { name: "Submit inspection for approval" })
      .click();
    await page
      .getByRole("dialog")
      .last()
      .getByRole("button", { name: "Inspect / approve" })
      .click();
    dialog = page.getByRole("dialog").last();
    await dialog
      .getByLabel("Inspector comments / approval decision reason")
      .fill("Reviewed return evidence");
    await dialog.getByRole("button", { name: "Approve", exact: true }).click();
    await expect(dialog).toContainText("Inspection status: Approved");
    await dialog
      .getByRole("button", { name: "Close dialog", exact: true })
      .click();
    await page
      .getByRole("dialog")
      .last()
      .getByRole("button", { name: "Propose recovery" })
      .click();
    dialog = page.getByRole("dialog").last();
    await dialog.getByLabel("Proposed recovery amount").fill("125");
    await dialog.getByLabel("Company policy reference").fill("HR policy 42");
    await dialog
      .getByLabel("Reason / physical inspection remarks")
      .fill("Documented damage proposal");
    await dialog
      .getByRole("button", { name: "Submit recovery proposal" })
      .click();
    await expect
      .poll(() => writes.some((w) => w.p.endsWith("/recovery")))
      .toBe(true);
    expect(writes.find((w) => w.p.endsWith("/recovery")).body.amount).toBe(
      "125",
    );
    await page
      .getByRole("button", { name: "Close dialog", exact: true })
      .click();
    await page
      .getByRole("button", { name: "Asset policy", exact: true })
      .click();
    dialog = page.getByRole("dialog").last();
    await dialog.getByLabel("Days before deadline").fill("14");
    await dialog
      .getByRole("button", { name: "Save policy", exact: true })
      .click();
    await expect
      .poll(() => writes.some((w) => w.p.endsWith("/policy")))
      .toBe(true);
    expect(writes.find((w) => w.p.endsWith("/policy")).body.reminder_days).toBe(
      14,
    );
    await expect(page.getByRole("dialog")).toHaveCount(0);
    await page.setViewportSize({ width: 390, height: 844 });
    await page
      .getByRole("button", { name: "Asset policy", exact: true })
      .click();
    await expect(page.getByRole("dialog")).toBeVisible();
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth + 1,
      ),
    ).toBe(true);
    await page.screenshot({
      path: path.resolve(
        __dirname,
        "../../outputs/asset-lifecycle-qa/policy-mobile.png",
      ),
      fullPage: true,
    });
    expect(errors).toEqual([]);
    console.log(
      "PASS: UI registration with vehicle fields, reviewed save, atomic handover payload, receipt, evidence upload, return, inspection approval, recovery proposal and reminder configuration.",
    );
  } finally {
    await browser.close();
    await server.close();
  }
})().catch((e) => {
  console.error(e);
  process.exitCode = 1;
});
