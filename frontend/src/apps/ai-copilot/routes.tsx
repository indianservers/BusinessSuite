import React from "react";
import type { FrontendRoute } from "@/appRegistry";

const AICopilotPage = React.lazy(() => import("./AICopilotPage"));

export const aiCopilotRoutes: FrontendRoute[] = [
  { path: "ai/copilot", element: <AICopilotPage /> },
  { path: "ai/record-summary", element: <AICopilotPage /> },
  { path: "ai/deal-coach", element: <AICopilotPage /> },
  { path: "ai/forecast", element: <AICopilotPage /> },
  { path: "ai/collection-risk", element: <AICopilotPage /> },
  { path: "ai/workflow-builder", element: <AICopilotPage /> },
  { path: "ai/report-explainer", element: <AICopilotPage /> },
  { path: "ai/prompt-templates", element: <AICopilotPage /> },
  { path: "ai/provider-settings", element: <AICopilotPage /> },
  { path: "ai/action-log", element: <AICopilotPage /> },
];

