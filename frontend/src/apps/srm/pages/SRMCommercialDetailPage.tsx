import { Link, useParams } from "react-router-dom";
import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { api } from "@/services/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { srmApi } from "../api";
import type { SRMRecord } from "../types";

type DetailKind = "salesOrder" | "contract" | "engagement" | "billingPlan";

const loaders: Record<DetailKind, (id: number) => Promise<SRMRecord>> = {
  salesOrder: srmApi.salesOrder,
  contract: srmApi.contract,
  engagement: srmApi.engagement,
  billingPlan: srmApi.billingPlan,
};

const titles: Record<DetailKind, string> = {
  salesOrder: "Sales Order Detail",
  contract: "Contract Detail",
  engagement: "Engagement Detail",
  billingPlan: "Billing Plan Detail",
};

function formatValue(value: unknown) {
  if (value === null || value === undefined || value === "") return "-";
  if (typeof value === "object") return Array.isArray(value) ? `${value.length}` : "Linked";
  return String(value).replace(/_/g, " ");
}

export default function SRMCommercialDetailPage({ kind }: { kind: DetailKind }) {
  const { id } = useParams();
  const numericId = Number(id || 0);
  const query = useQuery({
    queryKey: ["srm", kind, numericId],
    queryFn: () => loaders[kind](numericId),
    enabled: numericId > 0,
  });
  const record = (query.data || {}) as SRMRecord;
  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">{titles[kind]}</h1>
        <p className="text-sm text-muted-foreground">Linked commercial lifecycle record.</p>
      </div>
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            {formatValue(record.order_number || record.contract_number || record.engagement_number || record.name || record.title || `Record ${numericId}`)}
            {record.status ? <Badge>{formatValue(record.status)}</Badge> : null}
          </CardTitle>
        </CardHeader>
        <CardContent className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {["customer_id", "crm_deal_id", "sales_order_id", "engagement_id", "contract_value", "total_amount", "budget_amount", "pms_project_id"].map((key) => (
            <div key={key} className="rounded-lg border p-3">
              <p className="text-xs uppercase text-muted-foreground">{key.replace(/_/g, " ")}</p>
              <p className="mt-1 text-sm font-medium">{formatValue(record[key])}</p>
            </div>
          ))}
        </CardContent>
      </Card>
      {(kind === "salesOrder" || kind === "engagement") && <CommercialConnections key={`${kind}-${numericId}`} orderId={kind === "salesOrder" ? numericId : Number(record.sales_order_id || 0)} engagementId={kind === "engagement" ? numericId : undefined} />}
    </div>
  );
}

function CommercialConnections({ orderId, engagementId }: { orderId: number; engagementId?: number }) {
  const [team, setTeam] = useState("");
  const related = useQuery({ queryKey: ["commercial-related", orderId, engagementId], queryFn: async () => (await api.get(`/srm/business/related-projects?${engagementId ? `engagement_id=${engagementId}` : `sales_order_id=${orderId}`}`)).data, enabled: !!(orderId || engagementId) });
  const directory = useQuery({ queryKey: ["shared-teams"], queryFn: async () => (await api.get("/srm/business/teams")).data });
  const assigned = useQuery({ queryKey: ["sales-order-team", orderId], queryFn: async () => (await api.get(`/srm/business/sales-orders/${orderId}/team`)).data, enabled: !!orderId });
  const save = useMutation({ mutationFn: () => api.put(`/srm/business/sales-orders/${orderId}/team`, { team_id: Number(team) }), onSuccess: () => assigned.refetch() });
  const createProject = useMutation({ mutationFn: async () => (await api.post(`/srm/engagements/${engagementId}/create-pms-project`)).data, onSuccess: () => related.refetch() });
  return <Card><CardHeader><CardTitle>Shared team and projects</CardTitle></CardHeader><CardContent className="space-y-4">
    {orderId > 0 && <div className="flex flex-wrap gap-2"><select aria-label="Shared sales team" className="h-10 rounded-md border bg-background px-3" value={team || String(assigned.data?.team_id || "")} onChange={e => setTeam(e.target.value)}><option value="">Choose company team</option>{(directory.data || []).map((t: any) => <option key={t.id} value={t.id}>{t.name} ({t.status})</option>)}</select><Button disabled={!team || save.isPending} onClick={() => save.mutate()}>Assign team</Button>{save.isError && <p role="alert">{(save.error as any)?.response?.data?.detail || "Unable to assign team"}</p>}{save.isSuccess && <p role="status">Shared team assigned.</p>}</div>}
    {related.isError ? <p>Related projects are outside your permitted scope or unavailable.</p> : (related.data || []).map((p: any) => <p key={p.id}><Link className="text-primary underline" to={`/pms/projects/${p.id}`}>{p.name} ↗</Link></p>)}
    {engagementId && <><Button disabled={createProject.isPending} onClick={() => createProject.mutate()}>Create / open linked project</Button>{createProject.isError && <p role="alert">{(createProject.error as any)?.response?.data?.detail || "Project handoff failed"}</p>}{createProject.data?.project && <p><Link className="text-primary underline" to={`/pms/projects/${createProject.data.project.id}`}>{createProject.data.project.name} ↗</Link></p>}</>}
  </CardContent></Card>;
}
