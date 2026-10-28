import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/services/api";
import { useAuthStore } from "@/store/authStore";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { toast } from "@/hooks/use-toast";
import { formatDate } from "@/lib/utils";
export default function MyAssetsPanel() {
  const userId = useAuthStore(s => s.user?.id), qc = useQueryClient();
  const query = useQuery({ queryKey: ["my-assets", userId], queryFn: () => api.get<{ id: number; asset_name: string; asset_tag: string; serial_number: string | null; assigned_date: string; acknowledgement_signed: boolean; remarks: string | null; acknowledged_at: string | null }[]>("/assets/my").then(r => r.data) });
  const acknowledge = useMutation({ mutationFn: (id: number) => api.put(`/assets/assignments/${id}/acknowledge`), onSuccess: () => { qc.invalidateQueries({ queryKey: ["my-assets"] }); qc.invalidateQueries({ queryKey: ["employee-360"] }); toast({ title: "Asset receipt acknowledged" }); }, onError: () => toast({ title: "Could not acknowledge receipt. Refresh and retry.", variant: "destructive" }) });
  return <Card><CardHeader><CardTitle className="text-base">My company assets</CardTitle></CardHeader><CardContent className="space-y-3">{query.isPending && <p role="status">Loading assigned equipment…</p>}{query.isError && <p role="alert">Assigned assets could not load. <button className="underline" onClick={() => query.refetch()}>Retry assets</button></p>}{query.data?.map(row => <article className="space-y-2 rounded border p-3" key={row.id}><p className="font-medium">{row.asset_name} · {row.asset_tag}</p><p className="text-xs text-muted-foreground">Assigned {formatDate(row.assigned_date)} · Serial / registration: {row.serial_number || "Not recorded"}</p>{row.remarks && <p className="break-words text-sm">Handover notes: {row.remarks}</p>}{row.acknowledged_at && <p className="text-xs text-muted-foreground">Acknowledged {formatDate(row.acknowledged_at)}</p>}{row.acknowledgement_signed ? <Badge variant="outline">Acknowledged</Badge> : <><p className="text-xs text-muted-foreground">Confirm only after you have physically received this item.</p><Button size="sm" variant="outline" disabled={acknowledge.isPending} onClick={() => acknowledge.mutate(row.id)}>I received this asset</Button></>}</article>)}{query.data?.length === 0 && <p className="text-sm text-muted-foreground">No company assets are currently assigned to you.</p>}</CardContent></Card>;
}
