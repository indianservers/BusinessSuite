import { Navigate } from "react-router-dom";
import type { FrontendRoute } from "@/appRegistry";
import InventoryBridgePage from "./InventoryBridgePage";

export const inventoryRoutes: FrontendRoute[] = [
  { path: "inventory", element: <InventoryBridgePage />, caseSensitive: true },
  { path: "inventory/dashboard", element: <InventoryBridgePage />, caseSensitive: true },
  { path: "Inventory", element: <Navigate to="/inventory" replace />, caseSensitive: true },
  { path: "Inventory/dashboard", element: <Navigate to="/inventory/dashboard" replace />, caseSensitive: true },
];
