import { expect, test, type Page } from "../frontend/node_modules/playwright/test";
import { authenticateCrm } from "./crm-core-test-utils";

function initialProfile() {
  return { userId: 100, employeeId: 2, personId: 100, displayName: "Ananya Rao", loginEmail: "ananya@example.com", kind: "intern", accountActive: true, version: "version-1", completeness: 78, missingFields: ["bio", "emergency_contact_number"], canEdit: true, canManage: true, requiresApprovalFields: [] as string[], pendingRequests: [] as any[],
    values: { first_name: "Ananya", middle_name: "", last_name: "Rao", guardian_name: "Parent Rao", personal_email: "ananya@example.com", phone_number: "9876543210", phone_number_country_code: "+91", present_address: "Example Road", present_city: "Hyderabad", present_state: "Telangana", degree: "B.Tech", college: "Example University", specialization: "Computer Science", current_year: "3rd Year", passout_year: 2027, tenth_marks: 92, twelfth_marks: 88, bio: "", interests: "Software Development", skills: ["Python", "React"], education: [{ id: 1, degree: "B.Tech", institution: "Example University", pass_year: 2027 }], experience: [] as any[], requested_role: "Software Development Intern", duration: "3 Months", preferred_mode: "Remote", linkedin_url: "https://linkedin.com/in/ananya", github_url: "https://github.com/ananya", portfolio_url: "https://example.com/portfolio", timezone: "Asia/Kolkata" } as Record<string, any>,
    employment: { employee_id: "IH-001", employment_type: "Intern", department: "Engineering", manager: "HR Manager", status: "Active" },
    application: { reference: "APP-TEST-001", full_name: "Ananya Rao", email: "ananya@example.com", identity_last4: "1234", values: { parent_name: "Parent Rao", current_year: "3rd Year", area_of_interest: "Software Development", skills: "Python, React", duration: "3 Months" } },
    documents: [{ id: 1, name: "Resume.pdf", source: "Application", status: "Submitted" }] };
}

async function setup(page: Page, selfService = false) {
  await authenticateCrm(page);
  let profile = initialProfile();
  if (selfService) { profile.canManage = false; profile.requiresApprovalFields = ["personal_email", "phone_number", "education"]; }
  const changes: { path: string; data: any }[] = [];
  await page.route("**/api/v1/profiles/**", async route => {
    const path = new URL(route.request().url()).pathname.split("/profiles")[1];
    let payload: any;
    if (path === "/directory") payload = { items: [{ userId: 100, displayName: profile.displayName, email: profile.loginEmail, employeeCode: "IH-001", kind: "intern", active: true }], total: 1 };
    else if (path.endsWith("/connect-preview")) payload = { email: profile.loginEmail, candidates: [{ employeeId: 2, employeeCode: "IH-001", name: "Ananya Rao" }], message: "Email matching never bypasses application approval." };
    else if (path.endsWith("/connect-email")) { changes.push({ path, data: route.request().postDataJSON() }); payload = profile; }
    else if (route.request().method() === "PATCH") {
      const data = route.request().postDataJSON(); changes.push({ path, data });
      const protectedValues: Record<string, any> = {};
      for (const [key, value] of Object.entries(data.values)) {
        if (profile.requiresApprovalFields.includes(key)) protectedValues[key] = value;
        else profile.values[key] = value;
      }
      if (Object.keys(protectedValues).length) profile.pendingRequests = [{ id: 1, status: "Pending", reason: "Profile update", values: protectedValues }];
      profile.version = "version-2";
      payload = { profile, pendingRequestId: profile.pendingRequests.length ? 1 : null, message: profile.pendingRequests.length ? "Employee record changes are awaiting HR approval." : "Profile saved across connected modules." };
    } else payload = profile;
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(payload) });
  });
  await page.goto("/hrms/profile");
  await expect(page.getByRole("heading", { name: "Ananya Rao", exact: true })).toBeVisible();
  return changes;
}

test("approved intern form data is present in the shared profile and original application", async ({ page }) => {
  await setup(page);
  await page.getByRole("button", { name: "Academic", exact: true }).click();
  await expect(page.getByText("Example University", { exact: true })).toBeVisible();
  await expect(page.getByText("3rd Year", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Professional", exact: true }).click();
  await expect(page.getByText("3 Months", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Application", exact: true }).click();
  await expect(page.getByText("Parent Rao", { exact: true })).toBeVisible();
  await expect(page.getByText("•••• 1234", { exact: true })).toBeVisible();
  await page.screenshot({ path: "../docs/qa/shared-profiles/application-desktop.png", fullPage: true, animations: "disabled" });
});

test("profile edit saves only changed fields and keeps login identity read-only", async ({ page }) => {
  const changes = await setup(page);
  await page.getByRole("button", { name: "Edit profile", exact: true }).click();
  await page.getByRole("button", { name: "Personal", exact: true }).click();
  await page.getByLabel("About me", { exact: true }).fill("Building reliable software");
  await page.getByRole("button", { name: "Save profile", exact: true }).click();
  await expect(page.getByRole("status").filter({ hasText: "Profile saved" })).toBeVisible();
  expect(changes[0].data.values).toEqual({ bio: "Building reliable software" });
  await expect(page.getByText("Building reliable software", { exact: true })).toBeVisible();
  await expect(page.locator('input[value="ananya@example.com"]')).toHaveCount(0);
});

test("employee contact edits show pending approval without changing current data", async ({ page }) => {
  await setup(page, true);
  await page.getByRole("button", { name: "Edit profile", exact: true }).click();
  await page.getByRole("button", { name: "Contact", exact: true }).click();
  await page.getByLabel("Personal email", { exact: false }).fill("updated@example.com");
  await page.getByRole("button", { name: "Save profile", exact: true }).click();
  await expect(page.getByRole("status").filter({ hasText: "awaiting HR approval" })).toBeVisible();
  await expect(page.locator(".up-field").filter({ hasText: "Personal email" }).getByText("ananya@example.com", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Pending changes", exact: true }).click();
  await expect(page.getByText("updated@example.com", { exact: true })).toBeVisible();
});

test("education management preserves existing records and supports additions", async ({ page }) => {
  const changes = await setup(page);
  await page.getByRole("button", { name: "Edit profile", exact: true }).click();
  await page.getByRole("button", { name: "Education", exact: true }).click();
  await page.getByRole("button", { name: "Add qualification", exact: true }).click();
  await page.getByLabel("Qualification", { exact: true }).last().fill("Certification");
  await page.getByLabel("Institution", { exact: true }).last().fill("Learning Institute");
  await page.getByRole("button", { name: "Save profile", exact: true }).click();
  expect(changes[0].data.values.education).toHaveLength(2);
  expect(changes[0].data.values.education[0].id).toBe(1);
});

test("HR profile management previews email linkage before connecting", async ({ page }) => {
  const changes = await setup(page);
  await page.goto("/hrms/profile-management");
  await page.getByRole("button", { name: /Ananya Rao.*IH-001/ }).click();
  await page.getByRole("button", { name: "Connect by email", exact: true }).click();
  await expect(page.getByRole("dialog")).toBeVisible();
  expect(changes.some(change => change.path.endsWith("/connect-email"))).toBe(false);
  await page.getByRole("button", { name: "Confirm employee connection", exact: true }).click();
  await expect.poll(() => changes.some(change => change.path.endsWith("/connect-email"))).toBe(true);
});

test("profile validation errors preserve an unsaved draft", async ({ page }) => {
  await setup(page);
  await page.route("**/api/v1/profiles/me", async route => { if (route.request().method() === "PATCH") await route.fulfill({ status: 409, contentType: "application/json", body: JSON.stringify({ detail: "This profile has changed. Reload it before saving" }) }); else await route.fallback(); });
  await page.getByRole("button", { name: "Edit profile", exact: true }).click();
  await page.getByRole("button", { name: "Personal", exact: true }).click();
  await page.getByLabel("About me", { exact: true }).fill("Keep my draft");
  await page.getByRole("button", { name: "Save profile", exact: true }).click();
  await expect(page.getByRole("alert").filter({ hasText: "This profile has changed" })).toBeVisible();
  await expect(page.getByLabel("About me", { exact: true })).toHaveValue("Keep my draft");
});

test("complete profile remains usable on mobile", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await setup(page);
  await page.getByRole("button", { name: "Edit profile", exact: true }).click();
  await page.getByRole("button", { name: "Contact", exact: true }).click();
  await expect(page.getByLabel("Current address", { exact: true })).toBeVisible();
  const sizes = await page.evaluate(() => [document.documentElement.scrollWidth, document.documentElement.clientWidth]);
  expect(sizes[0]).toBeLessThanOrEqual(sizes[1] + 1);
  await page.screenshot({ path: "../docs/qa/shared-profiles/profile-mobile.png", fullPage: true, animations: "disabled" });
});

test("Interns Hub uses the same profile editor through portal-scoped endpoints", async ({ page }) => {
  const errors: string[] = []; page.on("pageerror", error => errors.push(error.message));
  const paths: string[] = [];
  await page.addInitScript(() => sessionStorage.setItem("internhub.session", "intern-profile-token"));
  await page.route("**/api/v1/interns-hub/**", async route => {
    const path = new URL(route.request().url()).pathname.split("/interns-hub")[1]; paths.push(path);
    const profile = { ...initialProfile(), canManage: false, requiresApprovalFields: ["personal_email", "phone_number", "education"] };
    const payload = path === "/profile" ? profile : path === "/me" ? { id: 2, first_name: "Ananya", last_name: "Rao", employee_id: "IH-001", education: [], skills: [], documents: [], status: "Active", personal_email: "ananya@example.com" } : path === "/overview" ? {} : [];
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(payload) });
  });
  await page.goto("http://127.0.0.1:5178/profile");
  await expect(page.getByRole("heading", { name: "Ananya Rao", exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Academic", exact: true }).click();
  await expect(page.getByText("Example University", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Edit profile", exact: true }).click();
  expect(paths).toContain("/profile");
  expect(errors).toEqual([]);
  await page.screenshot({ path: "../docs/qa/shared-profiles/intern-profile-desktop.png", fullPage: true, animations: "disabled" });
});
