import { toast } from "@/hooks/use-toast";
import { useEffect, useRef } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useAuthStore } from "@/store/authStore";
import { canAccessRoute } from "@/lib/roles";
import { api } from "@/services/api";
import { useWorkspaceContext } from "./useWorkspaceContext";
import { WorkspaceEditor } from "./WorkspaceEditor";
import { workspaceApiBase, workspaceDataScope, type WorkspaceModule, type WorkspaceDraft, type SavedWorkspace } from "./workspace-management-types";
import { operationalWorkspaceDefinitions, workspaceDomainViewIds as ids } from "./workspace-domains";
import { pmsWorkspaceViews } from "@/apps/project-management/pages/pms-workspace-views";
type Props = { module: WorkspaceModule; onCreated: (workspace: SavedWorkspace) => void; onClose: () => void; onBusyChange?: (busy: boolean) => void };
export default function WorkspaceCreateContent(props: Props) {
  const user = useAuthStore(state => state.user);
  return <ScopedWorkspaceCreateContent key={`${props.module}:${workspaceDataScope(user)}`} {...props} />;
}
function ScopedWorkspaceCreateContent({ module, onCreated, onClose, onBusyChange }: Props) {
  const user = useAuthStore(state => state.user);
  const base = workspaceApiBase(module);
  const qc = useQueryClient();
  const context = useWorkspaceContext();
  const scope = workspaceDataScope(user);
  const active = useRef(true);
  useEffect(() => { active.current = true; return () => { active.current = false; }; }, []);
  const owns = () => active.current && scope === workspaceDataScope(useAuthStore.getState().user);
  const permission = useQuery({ queryKey: ["managed-workspaces", module, scope], enabled: context.ready, queryFn: ({ signal }) => api.get<{ can_create: boolean; branch_name?: string }>(base, { signal }).then(response => response.data), retry: false });
  const people = useQuery({ queryKey: ["workspace-create-people", module, scope], enabled: module !== "pms" && permission.data?.can_create, queryFn: ({ signal }) => api.get<{ user_id: number; email: string }[]>(`${base}/eligible-people`, { signal }).then(response => response.data), retry: false });
  const create = useMutation({ mutationFn: (draft: WorkspaceDraft) => {
    if (!owns()) throw new Error("The workspace context changed. Reopen this form.");
    return api.post<SavedWorkspace>(base, draft).then(response => response.data);
  }, onSuccess: workspace => { if (!owns()) return; toast({ title: "Workspace created", description: workspace.name }); void qc.invalidateQueries({ queryKey: ["managed-workspaces", module, scope] }, { cancelRefetch: false }); onCreated(workspace); } });
  useEffect(() => { onBusyChange?.(create.isPending); }, [create.isPending, onBusyChange]);
  const views = (module === "pms" ? pmsWorkspaceViews : operationalWorkspaceDefinitions[module].domains.map((domain, index) => ({ id: ids[module][index], label: domain.name, href: domain.path }))).filter(view => canAccessRoute(view.href.split(/[?#]/)[0], user?.role, user?.is_superuser));
  if (!context.ready) return <p role={context.error ? "alert" : "status"}>{context.loading ? "Loading workspace branch context…" : "Select an available branch before creating a workspace."}</p>;
  if (permission.isPending) return <p role="status">Loading workspace creation…</p>;
  if (permission.isError || !permission.data?.can_create) return <p role="alert">Workspace creation is unavailable for your current access.</p>;
  const detail = (create.error as { response?: { data?: { detail?: unknown } } } | null)?.response?.data?.detail;
  return <WorkspaceEditor views={views} moduleLabel={module === "pms" ? "Project workspaces" : operationalWorkspaceDefinitions[module].title} company={user?.access?.companyName} branchLabel={permission.data.branch_name} pms={module === "pms"} people={(people.data || []).filter(person => person.user_id !== user?.id)} loadingPeople={people.isFetching} busy={create.isPending} error={create.isError ? typeof detail === "string" ? detail : "Workspace could not be created. Please retry." : undefined} onSave={draft => create.mutate(draft)} onClose={onClose} />;
}
