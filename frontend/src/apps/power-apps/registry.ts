import {
  Workflow,
  BadgeCheck,
  ClipboardList,
  Database,
  PanelsTopLeft,
  BellRing,
  Search,
  BarChart3,
  Plug,
  Files,
  Bot,
  History,
  type LucideIcon,
} from "lucide-react";
export type Environment = "development" | "testing" | "production";
export type Application = {
  id: string;
  name: string;
  icon: string;
  route: string;
  description: string;
  status: "drafts" | "planned" | "available";
  required_permissions: string[];
  feature_flags: string[];
  environments: Environment[];
};
export const applicationIcons: Record<string, LucideIcon> = {
  Workflow,
  BadgeCheck,
  ClipboardList,
  Database,
  PanelsTopLeft,
  BellRing,
  Search,
  ChartNoAxesCombined: BarChart3,
  Plug,
  Files,
  Bot,
  History,
};
export type Resource = {
  id: number;
  name: string;
  description: string;
  application_id: string;
  environment: Environment;
  status: "draft";
  version: number;
  definition: Record<string, unknown>;
  updated_at: string;
  owner_user_id?: number;
  archived_at?: string | null;
};
export type Activity = {
  id: number;
  action: string;
  resource_name: string;
  created_at: string;
};
export type Catalog = {
  applications: Application[];
  permissions: string[];
  execution_enabled: false;
  templates: {
    id: string;
    application_id: string;
    name?: string;
    version?: number;
  }[];
};
export type Overview = {
  counts: Record<string, number>;
  recent: Resource[];
  unsupported_metrics: string[];
};
export const applicationRoutes = [
  "automations",
  "approvals",
  "forms",
  "tables",
  "app-builder",
  "notifications",
  "search",
  "dashboards",
  "connectors",
  "documents",
  "ai-agents",
  "activity",
] as const;
