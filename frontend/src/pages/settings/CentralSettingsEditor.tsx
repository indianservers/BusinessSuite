import { lazy, Suspense } from "react";
const BusinessProfile = lazy(() => import("./BusinessProfileSettings"));
const Defaults = lazy(() => import("./DefaultsSettings"));
const FilesStorage = lazy(() => import("./FilesStorageSettings"));
const Companies = lazy(() => import("@/shared/master-data/CompaniesPage"));
const CRM = lazy(() => import("@/apps/crm/CRMWorkspacePage"));
const Sales = lazy(() => import("@/apps/srm/pages/SRMWorkspacePage"));
const Finance = lazy(() => import("@/apps/fam/FAMWorkspacePage"));
const Projects = lazy(() => import("@/apps/project-management/pages/SettingsPage"));
const Documents = lazy(() => import("@/apps/hrms/pages/documents/DocumentStudioPage"));
const Control = lazy(() => import("@/features/access/ControlCenter"));
const Services = lazy(() => import("@/features/access/SharedServicesPage"));
const AI = lazy(() => import("@/apps/ai-copilot/AICopilotPage"));
const Developer = lazy(() => import("@/apps/saas/SaaSWorkspacePage"));
const Users = lazy(() => import("@/features/access/UsersAccessPage"));

export const centralEditorKeys = new Set(["business-defaults", "files-storage", "shared-companies", "api-credentials", "webhooks", "crm-webhooks", "crm-scoring", "crm-territories", "crm-automation", "crm", "crm-pipelines", "crm-approvals", "sales", "finance", "pms", "documents", "security", "audit", "modules", "connections", "communication", "global", "ai", "financial-years", "cost-centers", "accounting-branches", "voucher-types", "payment-modes", "tax-settings", "roles"]);

centralEditorKeys.add("business-profile");

export default function CentralSettingsEditor({ section }: { section: string }) {
  let editor;
  switch (section) {
    case "business-profile": editor = <BusinessProfile/>; break;
    case "business-defaults": editor = <Defaults/>; break;
    case "files-storage": editor = <FilesStorage/>; break;
    case "shared-companies": editor = <Companies/>; break;
    case "api-credentials": editor = <Developer section="api-keys"/>; break;
    case "webhooks": editor = <><Developer section="webhooks"/><Services section="webhooks" embedded/></>; break;
    case "crm-webhooks": editor = <CRM kind="webhooks"/>; break;
    case "crm-scoring": editor = <CRM kind="leadScoring"/>; break;
    case "crm-territories": editor = <CRM kind="territories"/>; break;
    case "crm-automation": editor = <CRM kind="automation"/>; break;
    case "crm": editor = <CRM kind="settings"/>; break;
    case "crm-pipelines": editor = <CRM kind="pipelineSettings"/>; break;
    case "crm-approvals": editor = <CRM kind="approvalSettings"/>; break;
    case "sales": editor = <Sales kind="settings"/>; break;
    case "finance": editor = <Finance kind="settings"/>; break;
    case "financial-years": editor = <Finance kind="financialYears"/>; break;
    case "cost-centers": editor = <Finance kind="costCenters"/>; break;
    case "accounting-branches": editor = <Finance kind="branches"/>; break;
    case "voucher-types": editor = <Finance kind="voucherTypes"/>; break;
    case "payment-modes": editor = <Finance kind="paymentModes"/>; break;
    case "tax-settings": editor = <Finance kind="gstSettings"/>; break;
    case "pms": editor = <Projects/>; break;
    case "documents": editor = <Documents settingsOnly/>; break;
    case "security": case "audit": case "modules": editor = <Control section={section} embedded/>; break;
    case "connections": editor = <Services section="connections" embedded/>; break;
    case "communication": editor = <Services section="delivery" embedded/>; break;
    case "global": editor = <Services section="settings" embedded/>; break;
    case "ai": editor = <AI section="provider-settings"/>; break;
    case "roles": editor = <Users embedded initialTab="Roles"/>; break;
    default: return null;
  }
  return <div className="settings-native-editor"><Suspense fallback={<p role="status">Loading configuration…</p>}>{editor}</Suspense></div>;
}
