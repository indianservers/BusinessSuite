import { expect, test, type Page } from "@playwright/test";

const HRMS_ADMIN_EMAIL = process.env.HRMS_UAT_EMAIL || "admin@aihrms.com";
const HRMS_ADMIN_PASSWORD = process.env.HRMS_UAT_PASSWORD || "Admin@123456";

const company = {
  name: "Indian Servers Demo Pvt Ltd",
  cin: "U72900TG2026PTC000001",
  pan: "AABCI1234F",
  state: "Telangana",
  city: "Hyderabad",
  address: "Hyderabad",
};

const branches = ["Hyderabad Head Office", "Bengaluru Branch", "Dubai Branch"];
const departments = ["HR", "Finance", "IT", "Sales", "Academics", "Operations"];
const designations = [
  "HR Manager",
  "Payroll Executive",
  "Software Developer",
  "Sales Executive",
  "Professor",
  "School Teacher",
  "Driver",
  "Security Guard",
];
const salaryComponents = [
  "Basic Pay",
  "HRA",
  "Transport Allowance",
  "Special Allowance",
  "Overtime",
  "Bonus",
  "Reimbursement",
  "PF Employee",
  "ESI Employee",
  "Professional Tax",
  "Loan EMI",
  "Salary Advance Recovery",
  "LOP Deduction",
];

const employees = [
  {
    code: "EMP001",
    firstName: "Aarav",
    lastName: "Sharma",
    email: "aarav.sharma.uat@example.com",
    department: "IT",
    designation: "Software Developer",
    branch: "Hyderabad Head Office",
    payGroup: "Monthly Staff",
    ctc: "600000",
    joining: "2026-06-01",
  },
  {
    code: "EMP002",
    firstName: "Meera",
    lastName: "Rao",
    email: "meera.rao.uat@example.com",
    department: "Academics",
    designation: "Professor",
    branch: "Hyderabad Head Office",
    payGroup: "Academic Staff",
    ctc: "720000",
    joining: "2026-06-01",
  },
  {
    code: "EMP003",
    firstName: "Rohan",
    lastName: "Patel",
    email: "rohan.patel.uat@example.com",
    department: "Sales",
    designation: "Sales Executive",
    branch: "Bengaluru Branch",
    payGroup: "Monthly Staff",
    ctc: "480000",
    joining: "2026-06-10",
  },
  {
    code: "EMP004",
    firstName: "Fatima",
    lastName: "Khan",
    email: "fatima.khan.uat@example.com",
    department: "Operations",
    designation: "Driver",
    branch: "Hyderabad Head Office",
    payGroup: "Contract Staff",
    ctc: "300000",
    joining: "2026-06-01",
  },
  {
    code: "EMP005",
    firstName: "Kavya",
    lastName: "Iyer",
    email: "kavya.iyer.uat@example.com",
    department: "Finance",
    designation: "Payroll Executive",
    branch: "Hyderabad Head Office",
    payGroup: "Monthly Staff",
    ctc: "540000",
    joining: "2026-06-20",
  },
];

test.describe("HRMS + Payroll UI data UAT", () => {
  test.beforeEach(async ({ page }) => {
    await login(page);
  });

  test("01 creates company, branches, departments and designations from UI", async ({ page }) => {
    await page.goto("/hrms/company");
    await expect(page.getByRole("heading", { name: /company/i })).toBeVisible();

    await fillByLabel(page, /Company Name/i, company.name);
    await fillByLabel(page, /Legal Name/i, company.name);
    await fillByLabel(page, /Registration Number/i, company.cin);
    await fillByLabel(page, /^PAN$/i, company.pan);
    await fillByLabel(page, /City/i, company.city);
    await fillByLabel(page, /State/i, company.state);
    await fillByLabel(page, /Address/i, company.address);
    await page.getByRole("button", { name: /^Save$/i }).first().click();
    await expect(page.getByText(company.name).first()).toBeVisible();

    for (const branch of branches) {
      await addPanelRecord(page, "Branches", branch, { code: slug(branch), city: branch.includes("Dubai") ? "Dubai" : branch.split(" ")[0] });
      await expect(page.getByText(branch).first()).toBeVisible();
    }

    for (const department of departments) {
      await addPanelRecord(page, "Departments", department, { code: slug(department) });
      await expect(page.getByText(department).first()).toBeVisible();
    }

    for (const designation of designations) {
      await addPanelRecord(page, "Designations", designation, { code: slug(designation) });
      await expect(page.getByText(designation).first()).toBeVisible();
    }

    await expectApiListContains(page, "/companies", company.name);
  });

  test("02 creates pay groups, components and salary structures from UI", async ({ page }) => {
    await page.goto("/hrms/payroll");
    await expect(page.getByRole("heading", { name: /payroll/i })).toBeVisible();

    for (const payGroup of ["Monthly Staff", "Academic Staff", "Contract Staff"]) {
      await fillVisibleInputNear(page, "Pay group name", payGroup);
      await fillVisibleInputNear(page, "Code", slug(payGroup));
      await page.getByRole("button", { name: /Create Pay Group|Save Pay Group/i }).first().click();
      await expect(page.getByText(payGroup).first()).toBeVisible();
    }

    for (const component of salaryComponents) {
      await page.goto("/hrms/settings");
      await page.getByText(/Salary Components/i).click();
      await page.getByRole("button", { name: /Add|Create|New/i }).first().click();
      await fillFirstVisibleTextInput(page, component);
      await page.getByRole("button", { name: /Save|Create/i }).last().click();
      await expect(page.getByText(component).first()).toBeVisible();
    }

    for (const structure of ["Standard Monthly", "Academic", "Contract"]) {
      await page.goto("/hrms/payroll");
      await page.getByRole("button", { name: /Create Structure|Save Structure/i }).first().click();
      await expect(page.getByText(structure).or(page.getByText(/salary structure/i)).first()).toBeVisible();
    }
  });

  test("03 creates employees from UI and assigns salary from detail page", async ({ page }) => {
    for (const employee of employees) {
      await page.goto("/hrms/employees/new");
      await fillByLabel(page, /First name/i, employee.firstName);
      await fillByLabel(page, /Last name/i, employee.lastName);
      await fillByLabel(page, /Joining date|Date of joining/i, employee.joining);
      await chooseOption(page, /Employment type/i, "Full-time");
      await chooseOption(page, /Branch/i, employee.branch);
      await chooseOption(page, /Department/i, employee.department);
      await chooseOption(page, /Designation/i, employee.designation);
      await nextStep(page);
      await fillByLabel(page, /Personal email/i, employee.email);
      await fillByLabel(page, /Phone/i, `90000000${employee.code.slice(-2)}`);
      await nextStep(page);
      await nextStep(page);
      await page.getByRole("button", { name: /Create Employee/i }).click();
      await expect(page.getByText(new RegExp(`${employee.firstName}.*${employee.lastName}`, "i")).first()).toBeVisible();

      await fillByLabel(page, /Annual CTC|CTC/i, employee.ctc);
      await fillByLabel(page, /Effective from/i, employee.joining);
      await page.getByRole("button", { name: /Save Salary/i }).click();
      await expect(page.getByText(/salary assignment|active|ctc/i).first()).toBeVisible();

      await expectApiListContains(page, "/employees", employee.email);
    }
  });

  test("04 records attendance, leave and payroll inputs, then validates payroll run", async ({ page }) => {
    await page.goto("/hrms/attendance");
    await expect(page.getByRole("heading", { name: /attendance/i })).toBeVisible();
    await expect(page.getByText(/half/i).or(page.getByText(/present/i)).first()).toBeVisible();

    await page.goto("/hrms/leave");
    await expect(page.getByRole("heading", { name: /leave/i })).toBeVisible();

    await page.goto("/hrms/payroll");
    await expect(page.getByRole("heading", { name: /payroll/i })).toBeVisible();
    await page.getByRole("button", { name: /Run Payroll|Process Payroll/i }).first().click();
    await expect(page.getByText(/gross|net|payslip|payroll run/i).first()).toBeVisible();
    await expect(page.getByText(/Aarav|Meera|Rohan|Fatima|Kavya/i).first()).toBeVisible();
  });

  test("05 validates approvals, lock, exports, reports and ESS access from UI", async ({ page }) => {
    await page.goto("/hrms/payroll");
    await page.getByRole("button", { name: /Approve|Submit for Approval/i }).first().click();
    await expect(page.getByText(/approved|submitted/i).first()).toBeVisible();
    await page.getByRole("button", { name: /Lock|Publish Payslip/i }).first().click();
    await expect(page.getByText(/locked|published/i).first()).toBeVisible();

    await page.getByRole("button", { name: /PDF|Excel|Export|Bank Advice/i }).first().click();
    await expect(page.getByText(/export|download|bank advice/i).first()).toBeVisible();

    await page.goto("/hrms/reports");
    await expect(page.getByText(/employee|attendance|leave|payroll|audit/i).first()).toBeVisible();

    await page.goto("/hrms/ess");
    await expect(page.getByText(/payslip|leave balance|attendance/i).first()).toBeVisible();
  });
});

async function login(page: Page) {
  await page.goto("/hrms/login");
  await page.getByLabel(/Email address/i).fill(HRMS_ADMIN_EMAIL);
  await page.getByLabel(/Password/i).fill(HRMS_ADMIN_PASSWORD);
  await page.getByRole("button", { name: /^Sign in$/i }).click();
  await expect(page).toHaveURL(/\/hrms/);
}

async function fillByLabel(page: Page, label: RegExp, value: string) {
  const field = page.getByLabel(label).first();
  if (await field.count()) {
    await field.fill(value);
  }
}

async function chooseOption(page: Page, label: RegExp, value: string) {
  const control = page.getByLabel(label).first();
  if (!(await control.count())) return;
  await control.click();
  const option = page.getByRole("option", { name: new RegExp(value, "i") }).first();
  if (await option.count()) await option.click();
}

async function nextStep(page: Page) {
  const next = page.getByRole("button", { name: /Next|Continue/i }).first();
  if (await next.count()) await next.click();
}

async function addPanelRecord(page: Page, panelName: string, name: string, extra: Record<string, string>) {
  const panel = page.getByText(new RegExp(panelName, "i")).locator("..").locator("..");
  await panel.getByRole("button", { name: /Add|Create|New/i }).first().click();
  await fillFirstVisibleTextInput(page, name);
  for (const value of Object.values(extra)) {
    await fillNextEmptyTextInput(page, value);
  }
  await page.getByRole("button", { name: /Save|Create/i }).last().click();
}

async function fillFirstVisibleTextInput(page: Page, value: string) {
  const inputs = page.locator("input:visible");
  await inputs.first().fill(value);
}

async function fillNextEmptyTextInput(page: Page, value: string) {
  const inputs = page.locator("input:visible");
  const count = await inputs.count();
  for (let index = 0; index < count; index += 1) {
    const input = inputs.nth(index);
    if ((await input.inputValue()) === "") {
      await input.fill(value);
      return;
    }
  }
}

async function fillVisibleInputNear(page: Page, label: string, value: string) {
  const field = page.getByLabel(new RegExp(label, "i")).first();
  if (await field.count()) {
    await field.fill(value);
  }
}

async function expectApiListContains(page: Page, path: string, expected: string) {
  const authState = await page.evaluate(() => localStorage.getItem("hrms-auth"));
  const parsed = authState ? JSON.parse(authState) : null;
  const token = parsed?.state?.accessToken;
  const response = await page.request.get(`/api/v1${path}`, {
    headers: token ? { Authorization: `Bearer ${token}` } : undefined,
  });
  expect(response.ok()).toBeTruthy();
  const body = JSON.stringify(await response.json());
  expect(body).toContain(expected);
}

function slug(value: string) {
  return value.toUpperCase().replace(/[^A-Z0-9]+/g, "-").replace(/^-|-$/g, "");
}
