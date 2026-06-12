import { Navigate } from "react-router-dom";
import type { FrontendRoute } from "@/appRegistry";
import InventoryBridgePage from "./InventoryBridgePage";

export const inventoryRoutes: FrontendRoute[] = [
  { path: "inventory", element: <Navigate to="/Inventory" replace />, caseSensitive: true },
  { path: "inventory/dashboard", element: <Navigate to="/Inventory/dashboard" replace />, caseSensitive: true },
  { path: "Inventory", element: <InventoryBridgePage />, caseSensitive: true },
  { path: "Inventory/dashboard", element: <InventoryBridgePage />, caseSensitive: true },
];
