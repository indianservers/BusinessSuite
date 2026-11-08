import { lazyRoute } from "@/lib/lazy-route";
import React from "react";
import type { FrontendRoute } from "@/appRegistry";

const AiAgentsDashboard = lazyRoute(() => import("./AiAgentsDashboard"));
const AiAgentChatPage = lazyRoute(() => import("./AiAgentChatPage"));
const AiAgentConfigPage = lazyRoute(() => import("./AiAgentConfigPage"));
const AiApprovalsPage = lazyRoute(() => import("./AiApprovalsPage"));
const AiAuditLogsPage = lazyRoute(() => import("./AiAuditLogsPage"));
const AiAgentAnalyticsPage = lazyRoute(() => import("./AiAgentAnalyticsPage"));
const AiAgentUsagePage = lazyRoute(() => import("./AiAgentUsagePage"));
const AiAgentSecurityPage = lazyRoute(() => import("./AiAgentSecurityPage"));
const AiAgentPermissionsPage = lazyRoute(() => import("./AiAgentPermissionsPage"));
const AiAgentFeedbackPage = lazyRoute(() => import("./AiAgentFeedbackPage"));
const AiAgentHandoffPage = lazyRoute(() => import("./AiAgentHandoffPage"));
const SuiteOperatorPage = lazyRoute(() => import("./SuiteOperatorPage"));

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
