import { PaymentRequestButton } from "@/shared/payments/PaymentRequests";
import { ActionButton } from "@/components/actions";
import RecordSections from "@/components/RecordSections";
import { NativeSelect } from "@/components/ui/native-select";
import { useMobile } from "@/components/mobile/useMobile";
import { Link, useParams } from "react-router-dom";
import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { api } from "@/services/api";
import { Input } from "@/components/ui/input";
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
  const mobile=useMobile();
  const { id } = useParams();
  const numericId = Number(id || 0);
  const query = useQuery({
    queryKey: ["srm", kind, numericId],
    queryFn: () => loaders[kind](numericId),
    enabled: numericId > 0,
  });
  const record = (query.data || {}) as SRMRecord;
  if (query.isPending) return <p role="status">Loading commercial record…</p>;
  if (query.isError || !query.data) return <div className="space-y-3"><h1 className="text-2xl font-semibold">{titles[kind]}</h1><p role="alert">This record is unavailable in the current company or outside your access. Return to the list or choose the correct company.</p><Button variant="outline" onClick={() => query.refetch()}>Retry loading record</Button></div>;
  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">{titles[kind]}</h1>
        <p className="text-sm text-muted-foreground">Linked commercial lifecycle record.</p>
      </div>
      {mobile && kind === "salesOrder" && query.data && <ol className="mobile-timeline" aria-label="Order progress">{[["Order",record.status],["Delivery",record.delivery_status],["Invoicing",record.invoice_status],["Payment",record.payment_status]].map(([label,status])=><li key={String(label)}><strong>{String(label)}</strong><small>{status ? formatValue(status) : "Status not provided"}</small></li>)}</ol>}
      {kind === "salesOrder" && query.data && <PaymentRequestButton source="srm_order" sourceId={numericId}/>}
      {!!record.customer_id && <Button variant="outline" asChild><Link to={`/srm/customers/${record.customer_id}/360`}>Open customer 360</Link></Button>}
      {kind === "engagement" && <EngagementLifecycle record={record} onChanged={() => query.refetch()} />}
      {kind === "billingPlan" && <BillingMilestones record={record} onChanged={() => query.refetch()} />}
      <RecordSections key={`${kind}-${numericId}`} label="Commercial record information" sections={[
        {id:"overview",label:"Overview",content:<>      <Card>
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
</>},
        ...((kind === "salesOrder" || kind === "engagement") ? [{id:"connections",label:"Team & projects",content:<>      {(kind === "salesOrder" || kind === "engagement") && <CommercialConnections key={`${kind}-${numericId}`} orderId={kind === "salesOrder" ? numericId : Number(record.sales_order_id || 0)} engagementId={kind === "engagement" ? numericId : undefined} engagementStatus={String(record.status || "")} />}</>}] : []),
      ]}/>

    </div>
  );
}

function CommercialConnections({ orderId, engagementId, engagementStatus }: { orderId: number; engagementId?: number; engagementStatus?: string }) {
  const [team, setTeam] = useState("");
  const related = useQuery({ queryKey: ["commercial-related", orderId, engagementId], queryFn: async () => (await api.get(`/srm/business/related-projects?${engagementId ? `engagement_id=${engagementId}` : `sales_order_id=${orderId}`}`)).data, enabled: !!(orderId || engagementId) });
  const directory = useQuery({ queryKey: ["shared-teams"], queryFn: async () => (await api.get("/srm/business/teams")).data });
  const assigned = useQuery({ queryKey: ["sales-order-team", orderId], queryFn: async () => (await api.get(`/srm/business/sales-orders/${orderId}/team`)).data, enabled: !!orderId });
  const save = useMutation({ mutationFn: () => api.put(`/srm/business/sales-orders/${orderId}/team`, { team_id: Number(team) }), onSuccess: () => assigned.refetch() });
  const createProject = useMutation({ mutationFn: async () => (await api.post(`/srm/engagements/${engagementId}/create-pms-project`)).data, onSuccess: () => related.refetch() });
  return <Card><CardHeader><CardTitle>Shared team and projects</CardTitle></CardHeader><CardContent className="space-y-4">
    {orderId > 0 && <div className="flex flex-wrap gap-2"><NativeSelect loading={directory.isFetching} error={directory.isError} aria-label="Shared sales team" className="h-10 rounded-md border bg-background px-3" value={team || String(assigned.data?.team_id || "")} onChange={e => setTeam(e.target.value)}><option value="">Choose company team</option>{(directory.data || []).map((t: any) => <option key={t.id} value={t.id}>{t.name} ({t.status})</option>)}</NativeSelect><ActionButton action="assign" loading={save.isPending} disabled={!team} disabledReason={!team ? "Choose a shared sales team first" : undefined} onClick={() => save.mutate()}>Assign team</ActionButton>{save.isError && <p role="alert">{(save.error as any)?.response?.data?.detail || "Unable to assign team"}</p>}{save.isSuccess && <p role="status">Shared team assigned.</p>}</div>}
    {related.isError ? <p>Related projects are outside your permitted scope or unavailable.</p> : (related.data || []).map((p: any) => <p key={p.id}><Link className="text-primary underline" to={`/pms/projects/${p.id}`}>{p.name} ↗</Link></p>)}
    {engagementId && <><ActionButton action="task" disabled={engagementStatus === "closed" || engagementStatus === "cancelled"} disabledReason="Closed or cancelled engagements cannot create delivery activity" loading={createProject.isPending} tooltip="Create or open the delivery project linked to this engagement" onClick={() => createProject.mutate()}>Create / open linked project</ActionButton>{createProject.isError && <p role="alert">{(createProject.error as any)?.response?.data?.detail || "Project handoff failed"}</p>}{createProject.data?.project && <p><Link className="text-primary underline" to={`/pms/projects/${createProject.data.project.id}`}>{createProject.data.project.name} ↗</Link></p>}</>}
  </CardContent></Card>;
}


function actionError(error: unknown) {
  const detail = (error as {response?: {data?: {detail?: unknown}}})?.response?.data?.detail;
  return typeof detail === "string" ? detail : "Unable to complete this action. Refresh and try again.";
}

function EngagementLifecycle({record,onChanged}:{record:SRMRecord;onChanged:()=>unknown}) {
  const [reason,setReason]=useState("");
  const id=Number(record.id);
  const timeline=useQuery({queryKey:["engagement-timeline",id,record.status],queryFn:async()=>(await api.get(`/srm/engagements/${id}/timeline`)).data});
  const action=useMutation({mutationFn:(name:string)=>api.post(`/srm/engagements/${id}/lifecycle/${name}`,{reason}),onSuccess:()=>{setReason("");onChanged();timeline.refetch();}});
  const status=String(record.status);
  return <Card><CardHeader><CardTitle>Engagement lifecycle</CardTitle></CardHeader><CardContent className="space-y-3">
    <p>Status: <strong>{status}</strong></p>
    {status!=="cancelled" && <><label className="block">Lifecycle reason<Input aria-label="Lifecycle reason" value={reason} onChange={event=>setReason(event.target.value)}/></label><div className="flex gap-2">
      {(status==="closed"?["reopen"]:["close","cancel"]).map(name=><Button key={name} variant="outline" disabled={!reason.trim() || action.isPending} onClick={()=>action.mutate(name)}>{name==="reopen"?"Reopen engagement":name==="close"?"Close engagement":"Cancel engagement"}</Button>)}
    </div></>}
    {status==="cancelled" && <p>Cancelled engagements cannot create projects or billing plans.</p>}
    {action.isError && <p role="alert">{actionError(action.error)}</p>}
    {(timeline.data?.audit || []).filter((entry:SRMRecord)=>["cancel","close","reopen"].includes(String(entry.action))).map((entry:SRMRecord)=><p key={String(entry.id)}>{String(entry.action)} · {String(entry.created_at || "")} · Actor {String(entry.user_id || entry.actor_user_id || "")} · {String((entry.after_json as SRMRecord)?.reason || (entry.after_data as SRMRecord)?.reason || "")}</p>)}
  </CardContent></Card>;
}

function BillingMilestones({record,onChanged}:{record:SRMRecord;onChanged:()=>unknown}) {
  const [from,setFrom]=useState(new Date().toISOString().slice(0,10));
  const [to,setTo]=useState(new Date().toISOString().slice(0,10));
  const id=Number(record.id);
  const activate=useMutation({mutationFn:()=>api.post(`/srm/billing-plans/${id}/activate`),onSuccess:()=>onChanged()});
  const eligibility=useMutation({mutationFn:async()=>(await api.get(`/srm/billing-plans/${id}/eligibility`,{params:{date_from:from,date_to:to}})).data});
  return <Card><CardHeader><CardTitle>Billing milestones</CardTitle></CardHeader><CardContent className="space-y-4">
    <p>Plan total: {String(record.total_amount)} {String(record.currency)} · {String(record.status)}</p>
    {record.status==="draft" && <Button disabled={activate.isPending} onClick={()=>activate.mutate()}>Activate billing plan</Button>}
    {activate.isError && <p role="alert">{actionError(activate.error)}</p>}
    <div className="flex flex-wrap items-end gap-2"><label>Eligibility from<Input type="date" aria-label="Eligibility from" value={from} onInput={event=>{setFrom(event.currentTarget.value);eligibility.reset();}} onChange={event=>{setFrom(event.target.value);eligibility.reset();}}/></label><label>Eligibility to<Input type="date" aria-label="Eligibility to" value={to} onInput={event=>{setTo(event.currentTarget.value);eligibility.reset();}} onChange={event=>{setTo(event.target.value);eligibility.reset();}}/></label><Button variant="outline" disabled={eligibility.isPending || !from || !to} onClick={()=>eligibility.mutate()}>Check billing eligibility</Button></div>
    {eligibility.data && <p role="status">{eligibility.data.milestones.length} eligible milestones in this period.</p>}
    {eligibility.isError && <p role="alert">{actionError(eligibility.error)}</p>}
    {((record.invoices || []) as SRMRecord[]).map(invoice=><p key={String(invoice.id)}><Link className="text-primary underline" to={`/srm/invoices/${invoice.id}`}>Invoice {String(invoice.invoice_number || invoice.id)} · {String(invoice.total_amount)}</Link></p>)}
    {((record.milestones || []) as SRMRecord[]).map(milestone=><BillingMilestone key={`${milestone.id}-${milestone.amount}-${milestone.due_date}-${milestone.status}`} milestone={milestone} onChanged={()=>{eligibility.reset();onChanged();}}/>)}
  </CardContent></Card>;
}

function BillingMilestone({milestone,onChanged}:{milestone:SRMRecord;onChanged:()=>unknown}) {
  const [amount,setAmount]=useState(String(milestone.amount));
  const [due,setDue]=useState(String(milestone.due_date || ""));
  const [reason,setReason]=useState("");
  const id=Number(milestone.id);
  const amend=useMutation({mutationFn:()=>api.patch(`/srm/billing-milestones/${id}`,{amount,due_date:due || null,reason,expected_amount:String(milestone.amount),expected_due_date:milestone.due_date || null}),onSuccess:()=>onChanged()});
  const approve=useMutation({mutationFn:()=>api.post(`/srm/billing-milestones/${id}/approve`),onSuccess:()=>onChanged()});
  const draft=useMutation({mutationFn:async()=>(await api.post(`/srm/invoices/draft-from-billing-milestone/${id}`)).data,onSuccess:()=>onChanged()});
  const billed=!!milestone.invoice_draft_id || milestone.status==="invoiced";
  return <section className="space-y-2 rounded-lg border p-3" aria-label={`Milestone ${String(milestone.name)}`}>
    <h3 className="font-semibold">{String(milestone.name)} · {String(milestone.status)}</h3>
    <p>Agreed amount: {String(milestone.amount)} · Due: {String(milestone.due_date || "Not scheduled")}</p>
    {!billed && <><div className="flex flex-wrap gap-2"><label>Milestone amount<Input aria-label="Milestone amount" type="number" min="0" step="0.01" value={amount} onChange={event=>setAmount(event.target.value)}/></label><label>Milestone due date<Input aria-label="Milestone due date" type="date" value={due} onInput={event=>setDue(event.currentTarget.value)} onChange={event=>setDue(event.target.value)}/></label><label>Amendment reason<Input aria-label="Amendment reason" value={reason} onChange={event=>setReason(event.target.value)}/></label></div>
    <div className="flex flex-wrap gap-2"><Button variant="outline" disabled={!reason.trim() || amend.isPending} onClick={()=>amend.mutate()}>Save milestone amendment</Button><Button variant="outline" disabled={approve.isPending} onClick={()=>approve.mutate()}>Approve milestone</Button><Button disabled={draft.isPending || !["approved","ready","completed"].includes(String(milestone.status))} onClick={()=>draft.mutate()}>Generate milestone invoice</Button></div></>}
    {billed && <p>This milestone is invoiced and cannot be amended or billed again.</p>}
    {draft.data && <Link className="text-primary underline" to={`/srm/invoices/${draft.data.id}`}>Open generated invoice</Link>}
    {[amend,approve,draft].filter(action=>action.isError).map((action,index)=><p role="alert" key={index}>{actionError(action.error)}</p>)}
  </section>;
}
