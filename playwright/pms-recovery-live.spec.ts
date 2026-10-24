import { expect, test } from "../frontend/node_modules/playwright/test";

test("recovery saves, previews, restores and exports real workspace data on mobile", async ({
  page,
  request,
}) => {
  const origin = "http://127.0.0.1:8775";
  const session = await (await request.get(`${origin}/qa-session`)).json();
  const headers = { Authorization: `Bearer ${session.token}` };
  const base = `${origin}/api/v1/project-management`;
  const suffix = Date.now().toString().slice(-8);
  const workspace = await request.post(`${base}/workspaces`, {
    headers,
    data: { name: `Recovery QA ${suffix}` },
  });
  expect(workspace.ok()).toBeTruthy();
  const wid = (await workspace.json()).id;
  const project = await request.post(`${base}/projects`, {
    headers,
    data: {
      name: "Recovery test project",
      project_key: `R${suffix}`,
      workspace_id: wid,
    },
  });
  expect(project.ok()).toBeTruthy();
  const pid = (await project.json()).id;
  const task = await request.post(`${base}/projects/${pid}/tasks`, {
    headers,
    data: { task_key: `R-${suffix}`, title: "Recover this title" },
  });
  expect(task.ok()).toBeTruthy();
  const tid = (await task.json()).id;
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto(
    `/__commercial-browser-qa.html?path=${encodeURIComponent(`/pms/recovery?workspace=${wid}`)}`,
  );
  await expect(
    page.getByRole("heading", { name: "Backup & recovery", exact: true }),
  ).toBeVisible();
  await page
    .getByLabel("Savepoint name", { exact: true })
    .fill("Before change");
  await page
    .getByRole("button", { name: "Create savepoint", exact: true })
    .click();
  await expect(
    page.getByText("Savepoint created.", { exact: true }),
  ).toBeVisible();
  await page.getByLabel("Every (hours)", { exact: true }).first().fill("0");
  await page
    .getByRole("button", { name: "Save workspace schedule", exact: true })
    .click();
  await expect(page.getByRole("alert")).toContainText(
    "greater than or equal to 1",
  );
  await page.getByLabel("Every (hours)", { exact: true }).first().fill("24");
  await page
    .getByRole("button", { name: "Save workspace schedule", exact: true })
    .click();
  await expect(page.getByRole("status").first()).toContainText("policy saved");
  const edit = await request.patch(`${base}/tasks/${tid}`, {
    headers,
    data: { title: "Changed title", estimated_hours: "4.50" },
  });
  expect(edit.ok()).toBeTruthy();
  await page.reload();
  await page.getByRole("button", { name: "Undo", exact: true }).click();
  await expect(
    page.getByText("Task undo completed.", { exact: true }),
  ).toBeVisible();
  expect(
    (await (await request.get(`${base}/tasks/${tid}`, { headers })).json())
      .title,
  ).toBe("Recover this title");
  await page.getByRole("button", { name: "Redo", exact: true }).click();
  await expect(
    page.getByText("Task redo completed.", { exact: true }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Preview restore", exact: true })
    .click();
  const preview = page.getByRole("region", { name: "Restore preview" });
  await expect(preview.getByText(/1 tasks will change/)).toBeVisible();
  await page.getByLabel("Confirm workspace name").fill(`Recovery QA ${suffix}`);
  await page
    .getByRole("button", { name: "Restore task content", exact: true })
    .click();
  await expect(page.getByText(/Task content restored/)).toBeVisible();
  expect(
    (await (await request.get(`${base}/tasks/${tid}`, { headers })).json())
      .title,
  ).toBe("Recover this title");
  const download = page.waitForEvent("download");
  await page
    .getByRole("button", { name: "Export", exact: true })
    .last()
    .click();
  expect((await download).suggestedFilename()).toContain(
    `workspace-${wid}-savepoint-`,
  );
  await page
    .getByRole("button", { name: "Back up entire system now", exact: true })
    .click();
  await expect(
    page.getByText("Full-system archive created and verified.", {
      exact: true,
    }),
  ).toBeVisible();
  const archives = await (
    await request.get(`${base}/data-backups`, { headers })
  ).json();
  expect(archives.archives.length).toBeGreaterThan(0);
  const archiveDownload = page.waitForEvent("download");
  await page
    .getByRole("button", { name: "Download archive", exact: true })
    .first()
    .click();
  expect((await archiveDownload).suggestedFilename()).toMatch(
    /^businesssuite-[a-f0-9]{32}\.zip$/,
  );
  await page.setViewportSize({ width: 375, height: 812 });
  await expect(
    page.getByRole("heading", { name: "Backup & recovery", exact: true }),
  ).toBeVisible();
  expect(
    await page.evaluate(() => document.documentElement.scrollWidth),
  ).toBeLessThanOrEqual(375);
  await page.screenshot({
    path: "docs/qa/connected-commercial-2026-10-24/recovery-mobile.png",
    fullPage: true,
  });
  expect(errors).toEqual([]);
  await page.setViewportSize({ width: 1440, height: 900 });
  const keyboardEdit = await request.patch(`${base}/tasks/${tid}`, {
    headers,
    data: { title: "Keyboard recovery" },
  });
  expect(keyboardEdit.ok()).toBeTruthy();
  await page.goto(
    `/__commercial-browser-qa.html?path=${encodeURIComponent(`/pms?workspace=${wid}`)}`,
  );
  await expect(
    page.getByRole("button", { name: "Undo task edit", exact: true }),
  ).toBeEnabled();
  await page.locator("body").press("Control+z");
  await expect
    .poll(
      async () =>
        (await (await request.get(`${base}/tasks/${tid}`, { headers })).json())
          .title,
    )
    .toBe("Recover this title");
  await expect(
    page.getByRole("button", { name: "Redo task edit", exact: true }),
  ).toBeEnabled();
  await page.locator("body").press("Control+Shift+z");
  await expect
    .poll(
      async () =>
        (await (await request.get(`${base}/tasks/${tid}`, { headers })).json())
          .title,
    )
    .toBe("Keyboard recovery");
  expect(errors).toEqual([]);
});
