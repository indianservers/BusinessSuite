import { useQuery } from "@tanstack/react-query";
import { useAuthStore } from "@/store/authStore";
import { selectedBranch } from "@/lib/branch-context";
import { api } from "@/services/api";
/** Subscribe to the existing branch discovery query; never invent a destination. */
export function useWorkspaceContext(enabled = true) {
  const user = useAuthStore(state => state.user);
  const branch = selectedBranch();
  const query = useQuery({ queryKey: ["suite-branch-context", user?.id, user?.access?.companyId], enabled: enabled && Boolean(user) && !branch, queryFn: ({ signal }) => api.get<{ selected: number | null; branches: { id: number; name: string }[] }>("/branches/context", { signal, readOnlyPreview: true }).then(response => response.data), retry: false });
  return { branch, ready: Boolean(branch), loading: !branch && query.isPending, error: !branch && query.isError, retry: () => void query.refetch() };
}
