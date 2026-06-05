import { expect, test } from "../frontend/node_modules/playwright/test";
import { authenticate } from "./srm-test-utils";

test.describe("SRM contracts commercial UI", () => {
  test("lists, opens detail, and verifies contract lifecycle actions", async ({ page }) => {
    await authenticate(page, "srm_admin");

    await page.goto("/srm/contracts", { waitUntil: "domcontentloaded" });
    await expect(page.getByRole("heading", { name: "Contracts" })).toBeVisible();
    await expect(page.getByText("Managed Services")).toBeVisible();
    await expect(page.getByText("active")).toBeVisible();

    await page.goto("/srm/contracts/1", { waitUntil: "domcontentloaded" });
    await expect(page.getByRole("heading", { name: "Contract Detail" })).toBeVisible();
    await expect(page.getByText("CTR-000001")).toBeVisible();
    await expect(page.getByText("sales order id")).toBeVisible();
    await expect(page.getByText("engagement id")).toBeVisible();
    await expect(page.getByText("contract value")).toBeVisible();

    const lifecycle = await page.evaluate(async () => {
      const post = (path: string) => fetch(`/api/v1${path}`, { method: "POST" }).then((res) => res.json());
      const created = await post("/srm/contracts");
      const activated = await post("/srm/contracts/1/activate");
      const expired = await post("/srm/contracts/1/expire");
      const terminated = await post("/srm/contracts/1/terminate");
      const renewed = await post("/srm/contracts/1/renew");
      return { created, activated, expired, terminated, renewed };
    });

    expect(lifecycle.created.contract_number).toBe("CTR-000001");
    expect(lifecycle.activated.status).toBe("updated");
    expect(lifecycle.expired.status).toBe("updated");
    expect(lifecycle.terminated.status).toBe("updated");
    expect(lifecycle.renewed.status).toBe("updated");
  });
});
