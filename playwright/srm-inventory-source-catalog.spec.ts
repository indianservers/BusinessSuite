import { expect, test } from "../frontend/node_modules/playwright/test";
import { inventorySourceAppPaths, inventorySourceFeatureCount, mappedInventorySourceFeatureCount } from "../frontend/src/apps/inventory/sourceCatalog";
import { srmRoutes } from "../frontend/src/apps/srm/routes";

test.describe("Sales & Inventory source catalogue", () => {
  test("all mapped source catalogue paths are registered as SRM routes", () => {
    const registeredPaths = new Set(srmRoutes.map((route) => `/${route.path}`));

    expect(inventorySourceFeatureCount).toBeGreaterThan(50);
    expect(mappedInventorySourceFeatureCount).toBe(inventorySourceAppPaths.length);
    expect(inventorySourceAppPaths).toHaveLength(new Set(inventorySourceAppPaths).size);

    for (const appPath of inventorySourceAppPaths) {
      expect(registeredPaths.has(appPath), `${appPath} should be registered in srmRoutes`).toBe(true);
    }
  });
});
