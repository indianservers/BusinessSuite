import type { FrontendRoute } from "@/appRegistry";
import InventoryBridgePage from "./InventoryBridgePage";

export const inventoryRoutes: FrontendRoute[] = [
  { path: "inventory", element: <InventoryBridgePage /> },
  { path: "inventory/dashboard", element: <InventoryBridgePage /> },
];

