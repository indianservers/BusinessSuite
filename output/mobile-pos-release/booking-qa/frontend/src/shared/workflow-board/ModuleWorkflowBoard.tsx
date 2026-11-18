import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useAuthStore } from "@/store/authStore";
import { usePageRefresh } from "@/lib/page-refresh";
import CRMStageDialog from "@/apps/crm/CRMStageDialog";
import { useDefinitionPermission } from "@/components/RecordDefinitionActions";
import { moduleActionAllowed } from "@/hooks/use-module-action";
import { WorkflowBoard } from "./WorkflowBoard";
import { WorkflowStageReview } from "./WorkflowStageReview";
import { loadWorkflow, workflowTitles } from "./adapters";
import type { WorkflowModule, WorkflowRecord } from "./model";

export default function ModuleWorkflowBoard({ module, environment = "development", workspaceId }: { module: WorkflowModule; environment?: string; workspaceId?: number }) {
  const user = useAuthStore(s => s.user);
  const [transition, setTransition] = useState<WorkflowRecord>();
  const [day, setDay] = useState(() => new Date().toDateString());
  useEffect(() => { const timer = window.setInterval(() => setDay(new Date().toDateString()), 60_000); return () => window.clearInterval(timer); }, []);
  const branch = sessionStorage.getItem("suite-branch");
  const canManageHiring = useDefinitionPermission(["recruitment_manage"], "edit");
  const canManageOrders = useDefinitionPermission(["srm_manage", "srm_admin"], "create");
  const query = useQuery({
    queryKey: ["dashboard-workflow", module, user?.id, user?.access?.companyId, branch, environment, workspaceId, day],
    queryFn: ({ signal }) => loadWorkflow(module, signal, environment, workspaceId),
    enabled: !!user, retry: false, staleTime: 30_000,
  });
  usePageRefresh(() => query.refetch());
  const detail = (query.error as { response?: { status?: number; data?: { detail?: unknown } } } | null)?.response;
  const error = query.isError ? detail?.status === 403 ? "You do not have permission to view this workflow." : typeof detail?.data?.detail === "string" ? detail.data.detail : "Workflow could not be loaded. Retry to refresh its records." : undefined;
  const data = query.data && { ...query.data, records: query.data.records.map(r => ({ ...r, canChangeStage: module === "crm" ? moduleActionAllowed(user, "/crm", "edit") && r.canChangeStage : module === "hrms" ? canManageHiring && !!r.jobId : module === "pms" ? moduleActionAllowed(user, "/pms", "edit") : module === "srm" ? canManageOrders && r.canChangeStage : r.canChangeStage })) };
  return <>
    <WorkflowBoard key={`${module}:${environment}:${workspaceId || "all"}:${branch}`} title={workflowTitles[module]} data={data} loading={query.isPending} error={error} onRefresh={() => { void query.refetch(); }} onChangeStage={setTransition} />
    {module === "crm" && transition && <CRMStageDialog id={Number(transition.id)} close={() => setTransition(undefined)} saved={() => { void query.refetch(); }} />}
    {(module === "hrms" || module === "pms" || module === "srm") && transition && <WorkflowStageReview key={transition.id} module={module} record={transition} close={() => setTransition(undefined)} saved={() => { void query.refetch(); }} />}
  </>;
}
