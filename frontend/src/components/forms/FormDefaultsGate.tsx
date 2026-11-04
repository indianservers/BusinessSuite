import { useQuery } from "@tanstack/react-query";
import { type ReactNode } from "react";
import { api } from "@/services/api";
import { defaultsScope, installFormDefaults, type DefaultsPayload } from "@/lib/form-defaults";

/** Load starting values before mounting forms; later refreshes never reset a draft. */
export default function FormDefaultsGate({ children }: { children: ReactNode }) {
  const query = useQuery({ queryKey: ["form-defaults", defaultsScope()], queryFn: async () => {
    const { data } = await api.get<DefaultsPayload>("/access/settings/defaults/effective", { progress: false });
    installFormDefaults(data); return data;
  }, staleTime: 60_000, refetchOnWindowFocus: true, retry: 1 });
  if (query.data) { installFormDefaults(query.data); return <>{children}</>; }
  if (query.isError) return <div role="alert" className="p-6">Could not load form defaults. <button type="button" onClick={() => void query.refetch()} className="underline">Retry</button></div>;
  return <div role="status" className="p-6 text-sm text-muted-foreground">Loading workspace preferences…</div>;
}
