import { test, expect } from "../frontend/node_modules/playwright/test";
import { setupPowerApps, fixtureRow, makeGraph } from "./power-apps-fixtures";
test.use({ viewport: { width: 1600, height: 1000 } });

test("context menus provide node, connection and canvas submenus", async ({ page }, info) => {
  await setupPowerApps(page, { records: [fixtureRow(41, makeGraph(3))] });
  await page.goto("/power-apps/automations/41/edit");
  await expect(page.getByTestId("graph-count")).toHaveText("3 nodes / 2 connections");
  const canvas = page.locator(".react-flow__pane");
  await canvas.click({ button: "right", position: { x: 50, y: 100 } });
  await expect(page.getByRole("menu", { name: "Workflow canvas", exact: true })).toBeVisible();
  await page.getByRole("menuitem", { name: "View", exact: true }).focus();
  await page.keyboard.press("ArrowRight");
  await page.getByRole("menuitem", { name: "Hide grid", exact: true }).click();
  await expect(page.locator(".react-flow__background")).toHaveCount(0);
  await expect(page.getByRole("menu")).toHaveCount(0);
  await page.locator(".as-node").first().click({ button: "right" });
  await expect(page.getByRole("menuitem", { name: "Configure node", exact: true })).toBeVisible();
  await page.getByRole("menuitem", { name: "Add next step", exact: true }).hover();
  await expect(page.getByRole("menuitem", { name: "Next", exact: true })).toBeVisible();
  await page.keyboard.press("Escape");
  await page.keyboard.press("Escape");
  await expect(page.getByRole("menu")).toHaveCount(0);
  await page.locator(".as-node").first().click({ button: "right" });
  await page.getByRole("menuitem", { name: "Selection", exact: true }).hover();
  await page.getByRole("menuitem", { name: "Copy selection", exact: true }).click();
  await canvas.click({ button: "right", position: { x: 50, y: 100 } });
  await page.getByRole("menuitem", { name: "Paste", exact: true }).click();
  await expect(page.getByTestId("graph-count")).toHaveText("4 nodes / 2 connections");
  await page.getByRole("button", { name: "Fit to screen", exact: true }).click();
  let previousTransform:string|null=null;
  await expect.poll(async()=>{const transform=await page.locator(".react-flow__viewport").getAttribute("style");const settled=transform===previousTransform;previousTransform=transform;return settled;},{intervals:[100,100,100],timeout:5000}).toBe(true);
  const midpoint = await page.locator(".react-flow__edge-interaction").evaluateAll(elements => {
    for (const element of elements) {
      const path = element as SVGPathElement;
      for (const ratio of [0.2, 0.35, 0.5, 0.65, 0.8]) {
        const point = path.getPointAtLength(path.getTotalLength() * ratio);
        const screen = new DOMPoint(point.x, point.y).matrixTransform(path.getScreenCTM()!);
        if (document.elementFromPoint(screen.x, screen.y)?.closest(".react-flow__edge") === path.closest(".react-flow__edge")) return { x: screen.x, y: screen.y };
      }
    }
    throw new Error("No unobstructed connection segment to right-click");
  });
  await page.mouse.click(midpoint.x, midpoint.y, { button: "right" });
  await expect(page.getByRole("menu", { name: "Connection", exact: true })).toBeVisible();
  await page.getByRole("menuitem", { name: "Delete connection", exact: true }).click();
  await expect(page.getByTestId("graph-count")).toHaveText("4 nodes / 1 connections");
  await canvas.click({ button: "right", position: { x: 50, y: 100 } });
  await canvas.click({ position: { x: 25, y: 300 } });
  await expect(page.getByRole("menu")).toHaveCount(0);
  const bounds = await canvas.boundingBox();
  await canvas.click({ button: "right", position: { x: 50, y: bounds!.height - 120 } });
  await page.getByRole("menuitem", { name: "Add", exact: true }).hover();
  await page.getByRole("menuitem", { name: "Sticky note", exact: true }).click();
  await expect(page.locator(".as-annotation")).toHaveCount(1);
  await canvas.click({ button: "right", position: { x: 50, y: 100 } });
  await page.getByRole("menuitem", { name: "View", exact: true }).hover();
  await expect(page.getByRole("menuitem", { name: "Show grid", exact: true })).toBeVisible();
  await page.screenshot({ path: info.outputPath("workflow-context-menu.png"), fullPage: true });
});

test("read-only context menus block mutations", async ({ page }) => {
  const state = await setupPowerApps(page, { readOnly: true, records: [fixtureRow()] });
  await page.goto("/power-apps/automations/41/edit");
  await expect(page.getByTestId("graph-count")).toHaveText("4 nodes / 3 connections");
  await page.locator(".as-node").first().click({ button: "right" });
  await expect(page.getByRole("menuitem", { name: "Disable node", exact: true })).toHaveAttribute("aria-disabled", "true");
  await expect(page.getByRole("menuitem", { name: "Delete selection", exact: true })).toHaveAttribute("aria-disabled", "true");
  await page.keyboard.press("Escape");
  await page.locator(".react-flow__pane").click({ button: "right", position: { x: 50, y: 100 } });
  await expect(page.getByRole("menuitem", { name: "Add", exact: true })).toHaveAttribute("aria-disabled", "true");
  await page.getByRole("menuitem", { name: "View", exact: true }).hover();
  await expect(page.getByRole("menuitem", { name: "Fit to screen", exact: true })).not.toHaveAttribute("aria-disabled", "true");
  expect(state.writes.filter((w) => w.method === "PUT" || w.method === "DELETE")).toHaveLength(0);
});
