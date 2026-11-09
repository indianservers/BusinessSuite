import {SmartCreateSection} from "@/shared/creation/SmartCreateSection";
import {collectionColumns} from "@/shared/data-grid/collection-columns";
import CommissionClaims from "./CommissionClaims";
import { useNewRecordFocus } from "@/hooks/use-new-record-focus";
import GroupedRecords from "@/shared/data-grid/GroupedRecords";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";
import PageWorkTools from "@/components/app/PageWorkTools";
import { useMemo, useState } from "react";
import type { ReactNode } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowRight, Briefcase, FileText, Landmark, UserRound, Plus } from "lucide-react";
import { saasApi, portalSessionScope, type SaaSRecord } from "./api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

function PortalShell({ type, children }: { type: "customer" | "partner"; children: ReactNode }) {
  const nav = type === "customer"
    ? [["Home", "/portal/customer"], ["Quotes", "/portal/customer/quotes"], ["Invoices", "/portal/customer/invoices"], ["Projects", "/portal/customer/projects"], ["Profile", "/portal/customer/profile"]]
    : [["Home", "/portal/partner"], ["Leads", "/portal/partner/leads"], ["Commissions", "/portal/partner/commissions"], ["Profile", "/portal/partner/profile"]];
  const tokenScope = portalSessionScope();
  const capabilities = useQuery({queryKey:["partner-dashboard", tokenScope], queryFn:saasApi.partnerDashboard, enabled:type === "partner", retry:false});
  return (
    <div className="min-h-screen bg-background">
      <header className="border-b px-4 py-4 sm:px-6 lg:px-8">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className="text-sm uppercase text-muted-foreground">Business Suite Portal</p>
            <h1 className="text-2xl font-semibold">{type === "customer" ? "Customer Portal" : "Partner Portal"}</h1>
          </div>
          <div className="flex flex-wrap gap-2">
            {nav.map(([label, to]) => <span key={to} className="inline-flex items-center gap-1"><Button asChild variant="outline" size="sm"><Link to={to}>{label}</Link></Button>{to === "/portal/partner/leads" && capabilities.data?.permissions?.includes("submit_lead") && <Button asChild variant="outline" size="icon" className="h-8 w-8"><Link to={`${to}#new-record`} aria-label="Create partner lead" title="Submit a lead"><Plus size={14}/></Link></Button>}</span>)}
          </div>
        </div>
      </header>
      <main className="px-4 py-6 sm:px-6 lg:px-8"><PageWorkTools portalScope={`portal:${type}:${tokenScope}`}/>{children}</main>
    </div>
  );
}

export default function PortalPage() {
  const location = useLocation();
  const type = location.pathname.startsWith("/portal/partner") ? "partner" : "customer";
  const isLogin = location.pathname.endsWith("/login");
  if (isLogin) return <PortalLogin type={type} />;
  return <PortalShell type={type}>{type === "customer" ? <CustomerPortal /> : <PartnerPortal />}</PortalShell>;
}

function PortalLogin({ type }: { type: "customer" | "partner" }) {
  const navigate = useNavigate();
  const client = useQueryClient();
  const [token, setToken] = useState("");
  const [error,setError] = useState("");
  return (
    <div className="flex min-h-screen items-center justify-center bg-background px-4">
      <Card className="w-full max-w-md">
        <CardHeader><CardTitle>{type === "customer" ? "Customer" : "Partner"} portal login</CardTitle></CardHeader>
        <CardContent className="space-y-4">
          <p className="text-sm text-muted-foreground">Use the secure portal session token from your invite. Employee credentials do not grant portal access.</p>
          <div className="space-y-2"><Label htmlFor="portal-session-token">Portal session token</Label><Input id="portal-session-token" type="password" autoComplete="off" aria-describedby="portal-token-help" value={token} onChange={(event) => setToken(event.target.value)} placeholder="Paste session token" /></div>
          <p id="portal-token-help" className="text-xs text-muted-foreground">Paste your invite token. It is hidden while you type.</p>{error && <p role="alert">{error}</p>}<Button className="w-full" disabled={!token.trim()} onClick={() => { if(!token.trim()){setError("Enter your invite token.");return;} window.localStorage.setItem("portalSessionToken", token.trim()); client.removeQueries({predicate:query=>/^(portal-|partner-)/.test(String(query.queryKey[0]))}); navigate(`/portal/${type}`); }}>Open portal <ArrowRight className="h-4 w-4" /></Button>
        </CardContent>
      </Card>
    </div>
  );
}

function CustomerPortal() {
  const location = useLocation();
  const section = location.pathname.split("/").pop() || "customer";
  const me = useQuery({ queryKey: ["portal-me", portalSessionScope()], queryFn: saasApi.customerMe, retry: false });
  const quotes = useQuery({ queryKey: ["portal-quotes", portalSessionScope()], queryFn: saasApi.customerQuotes, retry: false });
  const invoices = useQuery({ queryKey: ["portal-invoices", portalSessionScope()], queryFn: saasApi.customerInvoices, retry: false });
  const projects = useQuery({ queryKey: ["portal-projects", portalSessionScope()], queryFn: saasApi.customerProjects, retry: false });
  const cards = [
    { title: "Quotes", value: quotes.data?.total ?? 0, icon: FileText },
    { title: "Invoices", value: invoices.data?.total ?? 0, icon: Landmark },
    { title: "Projects", value: projects.data?.total ?? 0, icon: Briefcase },
  ];
  if (me.isError) return <PortalNotice />;
  return (
    <div className="space-y-6">
      <div><h2 className="text-xl font-semibold">Welcome {me.data?.user?.display_name || "customer"}</h2><p className="text-sm text-muted-foreground">Only linked customer-safe records are shown here.</p></div>
      {section === "profile" ? <RecordGrid items={[me.data?.user || {}]} /> : null}
      {section === "quotes" ? <RecordGrid items={quotes.data?.items || []} actionLabel={me.data?.user?.permissions_json?.includes("accept_quote") ? "Accept quote" : undefined} /> : null}
      {section === "invoices" ? <RecordGrid items={invoices.data?.items || []} /> : null}
      {section === "projects" ? <RecordGrid items={projects.data?.items || []} empty="No linked customer-visible projects." /> : null}
      {!["profile", "quotes", "invoices", "projects"].includes(section) ? <div className="grid gap-4 md:grid-cols-3">{cards.map((card) => <SummaryCard key={card.title} {...card} />)}</div> : null}
    </div>
  );
}

function PartnerPortal() {
  const createRef = useNewRecordFocus();
  const location = useLocation();
  const qc = useQueryClient();
  const section = location.pathname.split("/").pop() || "partner";
  const me = useQuery({queryKey:["partner-me",portalSessionScope()],queryFn:saasApi.partnerMe,retry:false});
  const dashboard = useQuery({ queryKey: ["partner-dashboard", portalSessionScope()], queryFn: saasApi.partnerDashboard, retry: false });
  const leads = useQuery({ queryKey: ["partner-leads", portalSessionScope()], queryFn: saasApi.partnerLeads, retry: false });
  const [lead, setLead] = useState({ company_name: "", contact_name: "", email: "", value: 0 });
  const submit = useMutation({ mutationFn: saasApi.submitPartnerLead, onSuccess: () => { setLead({company_name:"",contact_name:"",email:"",value:0}); qc.invalidateQueries({ queryKey: ["partner-leads"] }); qc.invalidateQueries({ queryKey: ["partner-dashboard"] }); } });
  if (dashboard.isError || me.isError) return <PortalNotice />;
  if (section === "profile") return <section><h2 className="text-xl font-semibold">Partner profile</h2><RecordGrid items={me.data?.user ? [me.data.user] : []}/></section>;
  if (section === "commissions") return <CommissionClaims canManage={!!dashboard.data?.permissions?.includes("manage_commissions")}/>;
  return (
    <div className="space-y-6">
      <div><h2 className="text-xl font-semibold">Partner dashboard</h2><p className="text-sm text-muted-foreground">Track only partner-submitted leads and permitted deal status.</p></div>
      <div className="grid gap-4 md:grid-cols-2"><SummaryCard title="Submitted leads" value={dashboard.data?.submitted_leads || 0} icon={Briefcase} /><SummaryCard title="Commission status" value={dashboard.data?.commission_status || "Claims tracking"} icon={Landmark} /></div>
      {section === "leads" && dashboard.data?.permissions?.includes("submit_lead") ? <SmartCreateSection title="Submit lead"><Card ref={createRef}><CardHeader><CardTitle>Submit lead</CardTitle></CardHeader><CardContent><form className="grid gap-3 md:grid-cols-2" onSubmit={event=>{event.preventDefault();if(!submit.isPending)submit.mutate(lead);}}>
        <Input aria-label="Company" required maxLength={180} placeholder="Company" value={lead.company_name} onChange={e=>setLead({...lead,company_name:e.target.value})}/>
        <Input aria-label="Contact" required maxLength={180} placeholder="Contact" value={lead.contact_name} onChange={e=>setLead({...lead,contact_name:e.target.value})}/>
        <Input aria-label="Email" required type="email" placeholder="Email" value={lead.email} onChange={e=>setLead({...lead,email:e.target.value})}/>
        <Input aria-label="Value" type="number" min={0} placeholder="Value" value={lead.value} onChange={e=>setLead({...lead,value:Number(e.target.value)})}/>
        <Button type="submit" disabled={submit.isPending || !lead.company_name.trim() || !lead.contact_name.trim() || !lead.email.trim()}>{submit.isPending?"Submitting…":"Submit lead"}</Button>
        {submit.isError && <p role="alert">Could not submit the lead. Your details are kept for retry.</p>}
      </form></CardContent></Card></SmartCreateSection> : section === "leads" ? <p className="text-sm text-muted-foreground">This portal session can view submitted leads. Lead submission permission is required to add one.</p> : null}
      {section === "leads" && submit.isSuccess && <p role="status">Lead submitted</p>}
      <RecordGrid items={leads.data?.items || []} empty="No partner-submitted leads yet." />
    </div>
  );
}

function SummaryCard({ title, value, icon: Icon }: { title: string; value: React.ReactNode; icon: typeof FileText }) {
  return <Card><CardContent className="flex items-center justify-between p-4"><div><p className="text-sm text-muted-foreground">{title}</p><p className="text-2xl font-semibold">{value}</p></div><Icon className="h-5 w-5 text-muted-foreground" /></CardContent></Card>;
}

function RecordGrid({ items, empty = "No records available.", actionLabel }: { items: SaaSRecord[]; empty?: string; actionLabel?: string }) {
  const client=useQueryClient();
  const location=useLocation();
  const section=location.pathname.split("/").pop()||"";
  const entityLabel: string = ({quotes:"Quote",invoices:"Invoice",projects:"Project",leads:"Lead",profile:"Person"} as Record<string,string>)[section]||"Record";
  const fields=[{id:"status",label:"Status",value:(item:SaaSRecord)=>item.status||"Visible"},{id:"type",label:"Type",value:(item:SaaSRecord)=>item.portal_type||(item.invoice_number?"Invoice":item.quote_number?"Quote":entityLabel)}];
  const columns=collectionColumns(items,fields,location.pathname).map(column=>column.id==="name"?{...column,title:entityLabel}:column.id==="code"&&["Quote","Invoice"].includes(entityLabel)?{...column,title:`${entityLabel} number`}:column);
  const [review,setReview]=useState<SaaSRecord|null>(null),[error,setError]=useState("");
  const accept=useMutation({mutationFn:(id:number)=>saasApi.acceptQuote(id),onSuccess:()=>{setReview(null);void client.invalidateQueries({queryKey:["portal-quotes"]});},onError:()=>setError("Could not accept this quote. Your selection is kept; check your session and retry.")});
  if (!items.length) return <div className="rounded-md border bg-card p-4 text-sm text-muted-foreground">{empty}</div>;
  return <><GroupedRecords scope="portal-records" items={items} gridClassName="grid gap-3 md:grid-cols-2" fields={fields} tableColumns={columns} renderItem={(item,index)=><Card key={item.id || index}><CardContent className="space-y-2 p-4"><div className="flex items-center justify-between"><p className="font-medium">{item.name || item.quote_number || item.invoice_number || item.email || `Record ${item.id || index + 1}`}</p><Badge variant="outline">{item.status || item.portal_type || "visible"}</Badge></div><dl className="grid gap-2 text-sm">{Object.entries(item).filter(([key,value])=>!["id","name","status"].includes(key)&&value!==null&&["string","number","boolean"].includes(typeof value)).map(([key,value])=><div key={key}><dt className="text-xs capitalize text-muted-foreground">{key.replace(/_/g," ")}</dt><dd>{String(value)}</dd></div>)}</dl>{actionLabel ? <Button size="sm" variant="outline" disabled={!item.id || accept.isPending || ["accepted","approved","cancelled","rejected"].includes(String(item.status).toLowerCase())} onClick={()=>{setError("");setReview(item);}}>{actionLabel}</Button> : null}</CardContent></Card>}/>
    <Dialog open={!!review} onOpenChange={v=>{if(!v&&!accept.isPending)setReview(null);}}><DialogContent><DialogTitle>Review quote acceptance</DialogTitle><p>Accept {review?.quote_number || review?.name || "this quote"}?</p>{error&&<p role="alert">{error}</p>}<Button disabled={accept.isPending} onClick={()=>{if(review?.id)accept.mutate(Number(review.id));}}>{accept.isPending?"Accepting…":"Confirm acceptance"}</Button><Button variant="outline" disabled={accept.isPending} onClick={()=>setReview(null)}>Cancel</Button></DialogContent></Dialog></>;
}

function PortalNotice() {
  return <div className="rounded-md border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">Portal session required or not authorized. Open the portal login page and enter a valid invite token.</div>;
}
