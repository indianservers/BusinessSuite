import { expect, test } from "../frontend/node_modules/playwright/test";
test("admin previews, soft-deletes and restores workspaces on mobile", async ({
  page,
  request,
}) => {
  const base = "http://127.0.0.1:8775/api/v1/project-management";
  const session = await (
    await request.get("http://127.0.0.1:8775/qa-session")
  ).json();
  const headers = { Authorization: `Bearer ${session.token}` };
  const name = `Reset UI ${Date.now()}`;
  const created = await request.post(`${base}/workspaces`, {
    headers,
    data: { name },
  });
  expect(created.ok()).toBeTruthy();
  const wid = (await created.json()).id;
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.goto(
    `/__commercial-browser-qa.html?path=${encodeURIComponent("/pms/admin/workspaces")}`,
  );
  const reset = page.getByRole("button", {
    name: "Reset all workspaces",
    exact: true,
  });
  await expect(reset).toBeDisabled();
  await page
    .getByLabel("Confirm reset", { exact: true })
    .fill("RESET ALL WORKSPACES");
  await expect(reset).toBeEnabled();
  await reset.click();
  await expect(page.getByRole("status")).toContainText(
    "workspaces soft-deleted",
  );
  expect(
    await (await request.get(`${base}/workspaces`, { headers })).json(),
  ).toEqual([]);
  await page.setViewportSize({ width: 375, height: 812 });
  await page
    .getByRole("button", { name: `Restore ${name}`, exact: true })
    .click();
  await expect(page.getByRole("status")).toContainText(
    "restored with its existing data",
  );
  const active = await (
    await request.get(`${base}/workspaces`, { headers })
  ).json();
  expect(active.some((item: { id: number }) => item.id === wid)).toBeTruthy();
  expect(
    await page.evaluate(() => document.documentElement.scrollWidth),
  ).toBeLessThanOrEqual(375);
  expect(errors).toEqual([]);
});
