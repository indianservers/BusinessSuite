import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useLayoutEffect, useMemo, useRef, type ReactNode } from "react";
import { api } from "@/services/api";
import { defaultsScope, defaultsWorkspaceScope, installFormDefaults, cachedFormDefaults, cacheFormDefaults, type DefaultsPayload } from "@/lib/form-defaults";
import { useRecordScope } from "@/lib/record-scope";

/** Load starting values before mounting forms; later refreshes never reset a draft. */
export default function FormDefaultsGate({ children, required = true, unavailableMessage = "Workspace preferences are unavailable. Helpdesk remains available." }: { children: ReactNode; required?: boolean; unavailableMessage?: string }) {
  // Context selection changes browser storage without changing the auth user.
  // Subscribe so the gate cannot keep installing the previous context's data.
  useRecordScope();
  const client=useQueryClient(),scope=defaultsScope();
  const cached = useMemo(() => cachedFormDefaults(scope), [scope]);
  const query = useQuery({ queryKey: ["form-defaults", scope], queryFn: async ({ signal }) => {
    const { data } = await api.get<DefaultsPayload>("/access/settings/defaults/effective", { signal, progress: false });
    if (!data || typeof data !== "object" || !data.values || typeof data.values !== "object" || Array.isArray(data.values) || !data.modules || typeof data.modules !== "object" || Array.isArray(data.modules)) {
      throw new Error("Invalid form defaults response");
    }
    // Resolving the initial branch must not start an identical second request.
    // Ignore installation if the user switched company/branch during this read.
    if(defaultsScope()===scope){
      installFormDefaults(data);
      cacheFormDefaults(data);
      const resolvedScope=defaultsScope();
      if(resolvedScope!==scope)client.setQueryData(["form-defaults",resolvedScope],data);
    }
    return data;
  }, initialData:cached?.payload, initialDataUpdatedAt:cached?.savedAt, staleTime: 60_000, refetchOnWindowFocus: false, retry: 1 });
  const workspace = defaultsWorkspaceScope(query.data);
  const readyWorkspace = useRef<string>();
  const alreadyMounted = readyWorkspace.current === workspace;
  useLayoutEffect(() => {
    if (query.data) readyWorkspace.current = workspace;
    else if (!alreadyMounted) readyWorkspace.current = undefined;
  }, [query.data, workspace, alreadyMounted]);

  // A refreshed grant snapshot changes the query key. Keep existing forms for
  // this workspace mounted while the new, independently scoped read completes.
  if (!required || query.data || alreadyMounted) {
    if(query.data)installFormDefaults(query.data);
    return <>{query.isError&&<div role="status" className="px-4 py-2 text-sm">{unavailableMessage} <button type="button" onClick={()=>void query.refetch()} className="underline">Retry preferences</button></div>}{children}</>;
  }
  if (query.isError) return <div role="alert" className="p-6">Could not load form defaults. <button type="button" onClick={() => void query.refetch()} className="underline">Retry</button></div>;
  return <div role="status" className="p-6 text-sm text-muted-foreground">Loading workspace preferences…</div>;
}
