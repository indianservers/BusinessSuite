import React from "react";
import type { FrontendRoute } from "@/appRegistry";

const AiAgentsDashboard = React.lazy(() => import("./AiAgentsDashboard"));
const AiAgentChatPage = React.lazy(() => import("./AiAgentChatPage"));
const AiAgentConfigPage = React.lazy(() => import("./AiAgentConfigPage"));
const AiApprovalsPage = React.lazy(() => import("./AiApprovalsPage"));
const AiAuditLogsPage = React.lazy(() => import("./AiAuditLogsPage"));
const AiAgentAnalyticsPage = React.lazy(() => import("./AiAgentAnalyticsPage"));
const AiAgentUsagePage = React.lazy(() => import("./AiAgentUsagePage"));
const AiAgentSecurityPage = React.lazy(() => import("./AiAgentSecurityPage"));
const AiAgentPermissionsPage = React.lazy(() => import("./AiAgentPermissionsPage"));
const AiAgentFeedbackPage = React.lazy(() => import("./AiAgentFeedbackPage"));
const AiAgentHandoffPage = React.lazy(() => import("./AiAgentHandoffPage"));
const SuiteOperatorPage = React.lazy(() => import("./SuiteOperatorPage"));

export const aiAgentRoutes: FrontendRoute[] = [
  { path: "ai-agents/operator", element: <SuiteOperatorPage /> },
  { path: "ai-agents", element: <AiAgentsDashboard /> },
  { path: "ai-agents/chat/:agentId", element: <AiAgentChatPage /> },
  { path: "ai-agents/config", element: <AiAgentConfigPage /> },
  { path: "ai-agents/approvals", element: <AiApprovalsPage /> },
  { path: "ai-agents/analytics", element: <AiAgentAnalyticsPage /> },
  { path: "ai-agents/usage", element: <AiAgentUsagePage /> },
  { path: "ai-agents/security", element: <AiAgentSecurityPage /> },
  { path: "ai-agents/security/permissions", element: <AiAgentPermissionsPage /> },
  { path: "ai-agents/feedback", element: <AiAgentFeedbackPage /> },
  { path: "ai-agents/handoff", element: <AiAgentHandoffPage /> },
  { path: "ai-agents/logs", element: <AiAuditLogsPage /> },
];
