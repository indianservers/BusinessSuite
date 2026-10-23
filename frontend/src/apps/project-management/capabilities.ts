export type Tier = "Core" | "Business" | "Business Plus" | "Enterprise";
export type Capability = { name: string; status: "Available" | "Partial" | "Not implemented"; detail: string; href?: string };
export const capabilityTiers: { name: Tier; description: string; features: Capability[] }[] = [
  { name: "Core", description: "Task execution and everyday collaboration", features: [
    { name: "Custom fields and task types", status: "Partial", detail: "12 field types and a project field manager; task types remain limited. Formula, file, relationship and signature fields are pending.", href: "/pms/custom-fields" },
    { name: "Storage and workspace hierarchy", status: "Partial", detail: "Workspaces, projects and files exist. Unlimited storage and a Space/Folder/List hierarchy are not implemented.", href: "/pms/workspaces" },
    { name: "Forms", status: "Partial", detail: "Authenticated intake creates tasks. A general form builder, public submissions and unlimited usage are not implemented.", href: "/pms/forms" },
    { name: "Gantt charts", status: "Available", detail: "Project schedules and dependencies with lag are available; this does not imply unlimited usage or advanced scheduling parity.", href: "/pms/gantt" },
    { name: "Chat", status: "Partial", detail: "Shared workspace chat and private messages exist. Channels, threads, unread notifications and media remain pending.", href: "/pms/messages" },
    { name: "Task automation", status: "Partial", detail: "Creation/status triggers, priority and assignee actions, rule editing and paused duplication. Monthly usage accounting is not implemented.", href: "/pms/automation" },
  ] },
  { name: "Business", description: "Visibility, integrations and resource planning", features: [
    { name: "Advanced dashboards", status: "Partial", detail: "Portfolio and fixed reports exist. Saved widget dashboards, layout editing and dashboard sharing are pending.", href: "/pms/portfolio" },
    { name: "Webhooks and automation integrations", status: "Partial", detail: "GitHub/GitLab webhooks and an n8n event-feed integration exist. Generic action webhooks, delivery retries and connector management are pending.", href: "/pms/settings" },
    { name: "Resource management", status: "Partial", detail: "Workload and estimates exist. Dated capacity, holidays, leave-aware scheduling and configurable shared effort need completion.", href: "/pms/workload" },
    { name: "Google SSO and SMS 2FA", status: "Not implemented", detail: "PMS workspace policy setup and enforcement are not verified or exposed as completed capabilities." },
    { name: "Private views", status: "Partial", detail: "Saved task views support visibility. Equivalent private saved views across every view type are pending.", href: "/pms/tasks" },
    { name: "Higher automation allowances", status: "Not implemented", detail: "No tier-specific monthly quotas, reset periods or usage ledger are implemented." },
  ] },
  { name: "Business Plus", description: "Advanced processes and team administration", features: [
    { name: "Tag Manager", status: "Available", detail: "Organization tag search, location filters, accessible usage, rename/color editing and confirmed bulk deletion.", href: "/pms/tags" },
    { name: "Meeting notes and recordings", status: "Partial", detail: "Shared notes and meeting outlines exist. Meeting auto-join, recording, transcription and SyncUp equivalents are pending." },
    { name: "Advanced time tracking", status: "Partial", detail: "Time logs and timesheet flows exist. Unified timer journeys, advanced billing export and full acceptance verification remain pending.", href: "/pms/time-tracking" },
    { name: "Advanced forms", status: "Not implemented", detail: "Conditional questions, typed answer mapping, attachment questions and visual form routing are pending." },
    { name: "Custom permissions", status: "Partial", detail: "Fixed workspace/project roles are enforced. User-defined roles, field permissions and an editable permission matrix are pending.", href: "/pms/teams" },
    { name: "Advanced Custom Field Manager", status: "Partial", detail: "Search, grouping, project filters and editing exist. Workspace/task-type scope, field reuse, archive/restore and computed fields are pending.", href: "/pms/custom-fields" },
    { name: "Doc wikis", status: "Partial", detail: "Project documents, Markdown/table preview, task links, revision history and conflict protection exist. Live coediting, rich-text editing, comments, nested pages and wiki permissions remain pending.", href: "/pms/docs" },
    { name: "Scaled automation allowances", status: "Not implemented", detail: "Usage metering and tier-specific execution allowances are pending." },
  ] },
  { name: "Enterprise", description: "Identity, governance and operational controls", features: [
    { name: "White labeling", status: "Not implemented", detail: "Workspace branding, custom domains and outbound-message branding controls are pending." },
    { name: "Custom roles at scale", status: "Not implemented", detail: "Fixed roles exist; an unlimited custom role system does not." },
    { name: "Enterprise permissions and governance", status: "Partial", detail: "Project/workspace access checks exist. Policy administration, delegated controls and access request workflows remain pending." },
    { name: "SSO, SCIM and SAML", status: "Not implemented", detail: "Enterprise identity provisioning and workspace enforcement have not been implemented as a complete supported flow." },
    { name: "Audit logs", status: "Partial", detail: "Task/project activities and workflow feeds exist. Comprehensive security/configuration audit coverage, export and retention are pending." },
    { name: "Session management", status: "Not implemented", detail: "Workspace-configurable session lifetime, idle limits and session revocation administration are pending." },
    { name: "MSA, HIPAA and data residency", status: "Not implemented", detail: "These require contractual, infrastructure and operational verification; a product setting cannot establish compliance." },
    { name: "Enterprise API and integrations", status: "Partial", detail: "Application APIs exist. Enterprise service accounts, scoped credentials, documented rate limits and support guarantees are pending." },
    { name: "Connected search", status: "Not implemented", detail: "Permission-aware search across external document, mail and collaboration systems is pending." },
    { name: "Enterprise automation scale", status: "Not implemented", detail: "Queueing, execution metering and verified large-volume processing are pending." },
  ] },
];
