import { useQuery, useQueryClient } from "@tanstack/react-query";
import { type ReactNode } from "react";
import { api } from "@/services/api";
import { defaultsScope, installFormDefaults, type DefaultsPayload } from "@/lib/form-defaults";

/** Load starting values before mounting forms; later refreshes never reset a draft. */
export default function FormDefaultsGate({ children, required = true, unavailableMessage = "Workspace preferences are unavailable. Helpdesk remains available." }: { children: ReactNode; required?: boolean; unavailableMessage?: string }) {
  const client=useQueryClient(),scope=defaultsScope();
  const query = useQuery({ queryKey: ["form-defaults", scope], queryFn: async () => {
    const { data } = await api.get<DefaultsPayload>("/access/settings/defaults/effective", { progress: false });
    if (!data || typeof data !== "object" || !data.values || typeof data.values !== "object" || Array.isArray(data.values) || !data.modules || typeof data.modules !== "object" || Array.isArray(data.modules)) {
      throw new Error("Invalid form defaults response");
    }
    // Resolving the initial branch must not start an identical second request.
    // Ignore installation if the user switched company/branch during this read.
    if(defaultsScope()===scope){
      installFormDefaults(data);
      const resolvedScope=defaultsScope();
      if(resolvedScope!==scope)client.setQueryData(["form-defaults",resolvedScope],data);
    }
    return data;
  }, staleTime: 60_000, refetchOnWindowFocus: true, retry: 1 });
  if (!required) {
    if(query.data)installFormDefaults(query.data);
    return <>{query.isError&&<div role="status" className="px-4 py-2 text-sm">{unavailableMessage} <button type="button" onClick={()=>void query.refetch()} className="underline">Retry preferences</button></div>}{children}</>;
  }
  if (query.data) { installFormDefaults(query.data); return <>{children}</>; }
  if (query.isError) return <div role="alert" className="p-6">Could not load form defaults. <button type="button" onClick={() => void query.refetch()} className="underline">Retry</button></div>;
  return <div role="status" className="p-6 text-sm text-muted-foreground">Loading workspace preferences…</div>;
}
