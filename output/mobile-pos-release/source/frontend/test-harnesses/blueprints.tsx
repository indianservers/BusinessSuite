// Development-only entry for the isolated Playwright workflow tests; not a build entry.
import React from "react";
import { createRoot } from "react-dom/client";
import { MemoryRouter } from "react-router-dom";
import WorkspaceToolsPage from "../src/apps/project-management/pages/WorkspaceToolsPage";
import "../src/index.css";
import "../src/design-system/premium.css";

createRoot(document.getElementById("root")!).render(
  <MemoryRouter initialEntries={["/pms/blueprints"]}>
    <main className="kf-main p-4"><WorkspaceToolsPage /></main>
  </MemoryRouter>,
);
