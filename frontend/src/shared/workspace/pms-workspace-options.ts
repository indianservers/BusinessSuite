import { api } from "@/services/api";

export type PmsWorkspaceOption = { id: number; name: string; role: string; member_count?: number; created_at?: string };

/** One access-scoped cache for legacy workspace selectors and the workspace page. */
export function pmsWorkspaceOptions(scope: string) {
  return {
    queryKey: ["pms-project-workspace-options", scope],
    queryFn: ({signal}: {signal: AbortSignal}) => api.get<PmsWorkspaceOption[]>("/project-management/workspaces", {signal, timeout:15000}).then(response=>response.data),
    staleTime: 30000,
    retry: false as const,
  };
}
