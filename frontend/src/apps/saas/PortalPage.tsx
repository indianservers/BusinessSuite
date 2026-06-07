import { useMemo, useState } from "react";
import type { ReactNode } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowRight, Briefcase, FileText, Landmark, UserRound } from "lucide-react";
import { saasApi, type SaaSRecord } from "./api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

function PortalShell({ type, children }: { type: "customer" | "partner"; children: ReactNode }) {
  const nav = type === "customer"
    ? [["Home", "/portal/customer"], ["Quotes", "/portal/customer/quotes"], ["Invoices", "/portal/customer/invoices"], ["Projects", "/portal/customer/projects"], ["Profile", "/portal/customer/profile"]]
    : [["Home", "/portal/partner"], ["Leads", "/portal/partner/leads"], ["Commissions", "/portal/partner/commissions"], ["Profile", "/portal/partner/profile"]];
  return (
    <div className="min-h-screen bg-background">
      <header className="border-b px-4 py-4 sm:px-6 lg:px-8">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className="text-sm uppercase text-muted-foreground">Business Suite Portal</p>
            <h1 className="text-2xl font-semibold">{type === "customer" ? "Customer Portal" : "Partner Portal"}</h1>
          </div>
          <div className="flex flex-wrap gap-2">
            {nav.map(([label, to]) => <Button asChild key={to} variant="outline" size="sm"><Link to={to}>{label}</Link></Button>)}
          </div>
        </div>
      </header>
      <main className="px-4 py-6 sm:px-6 lg:px-8">{children}</main>
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
  const [token, setToken] = useState("");
  return (
    <div className="flex min-h-screen items-center justify-center bg-background px-4">
      <Card className="w-full max-w-md">
        <CardHeader><CardTitle>{type === "customer" ? "Customer" : "Partner"} portal login</CardTitle></CardHeader>
        <CardContent className="space-y-4">
          <p className="text-sm text-muted-foreground">Use the secure portal session token from your invite. Employee credentials do not grant portal access.</p>
          <div className="space-y-2"><Label>Portal session token</Label><Input value={token} onChange={(event) => setToken(event.target.value)} placeholder="Paste session token" /></div>
          <Button className="w-full" onClick={() => { window.localStorage.setItem("portalSessionToken", token); navigate(`/portal/${type}`); }}>Open portal <ArrowRight className="h-4 w-4" /></Button>
        </CardContent>
      </Card>
    </div>
  );
}

function CustomerPortal() {
  const location = useLocation();
  const section = location.pathname.split("/").pop() || "customer";
  const me = useQuery({ queryKey: ["portal-me"], queryFn: saasApi.customerMe, retry: false });
  const quotes = useQuery({ queryKey: ["portal-quotes"], queryFn: saasApi.customerQuotes, retry: false });
  const invoices = useQuery({ queryKey: ["portal-invoices"], queryFn: saasApi.customerInvoices, retry: false });
  const projects = useQuery({ queryKey: ["portal-projects"], queryFn: saasApi.customerProjects, retry: false });
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
      {section === "quotes" ? <RecordGrid items={quotes.data?.items || []} actionLabel="Accept quote" /> : null}
      {section === "invoices" ? <RecordGrid items={invoices.data?.items || []} /> : null}
      {section === "projects" ? <RecordGrid items={projects.data?.items || []} empty="No linked customer-visible projects." /> : null}
      {!["profile", "quotes", "invoices", "projects"].includes(section) ? <div className="grid gap-4 md:grid-cols-3">{cards.map((card) => <SummaryCard key={card.title} {...card} />)}</div> : null}
    </div>
  );
}

function PartnerPortal() {
  const location = useLocation();
  const qc = useQueryClient();
  const section = location.pathname.split("/").pop() || "partner";
  const dashboard = useQuery({ queryKey: ["partner-dashboard"], queryFn: saasApi.partnerDashboard, retry: false });
  const leads = useQuery({ queryKey: ["partner-leads"], queryFn: saasApi.partnerLeads, retry: false });
  const [lead, setLead] = useState({ company_name: "", contact_name: "", email: "", value: 0 });
  const submit = useMutation({ mutationFn: saasApi.submitPartnerLead, onSuccess: () => { qc.invalidateQueries({ queryKey: ["partner-leads"] }); qc.invalidateQueries({ queryKey: ["partner-dashboard"] }); } });
  if (dashboard.isError) return <PortalNotice />;
  if (section === "commissions") return <div className="rounded-md border bg-card p-4 text-sm text-muted-foreground">Commission tracking placeholder. No fake payout calculations are displayed.</div>;
  return (
    <div className="space-y-6">
      <div><h2 className="text-xl font-semibold">Partner dashboard</h2><p className="text-sm text-muted-foreground">Track only partner-submitted leads and permitted deal status.</p></div>
      <div className="grid gap-4 md:grid-cols-2"><SummaryCard title="Submitted leads" value={dashboard.data?.submitted_leads || 0} icon={Briefcase} /><SummaryCard title="Commission status" value={dashboard.data?.commission_status || "placeholder"} icon={Landmark} /></div>
      {section === "leads" ? <Card><CardHeader><CardTitle>Submit lead</CardTitle></CardHeader><CardContent className="grid gap-3 md:grid-cols-2"><Input placeholder="Company" value={lead.company_name} onChange={(e) => setLead({ ...lead, company_name: e.target.value })} /><Input placeholder="Contact" value={lead.contact_name} onChange={(e) => setLead({ ...lead, contact_name: e.target.value })} /><Input placeholder="Email" value={lead.email} onChange={(e) => setLead({ ...lead, email: e.target.value })} /><Input placeholder="Value" type="number" value={lead.value} onChange={(e) => setLead({ ...lead, value: Number(e.target.value) })} /><Button onClick={() => submit.mutate(lead)}>Submit lead</Button></CardContent></Card> : null}
      <RecordGrid items={leads.data?.items || []} empty="No partner-submitted leads yet." />
    </div>
  );
}

function SummaryCard({ title, value, icon: Icon }: { title: string; value: React.ReactNode; icon: typeof FileText }) {
  return <Card><CardContent className="flex items-center justify-between p-4"><div><p className="text-sm text-muted-foreground">{title}</p><p className="text-2xl font-semibold">{value}</p></div><Icon className="h-5 w-5 text-muted-foreground" /></CardContent></Card>;
}

function RecordGrid({ items, empty = "No records available.", actionLabel }: { items: SaaSRecord[]; empty?: string; actionLabel?: string }) {
  if (!items.length) return <div className="rounded-md border bg-card p-4 text-sm text-muted-foreground">{empty}</div>;
  return <div className="grid gap-3 md:grid-cols-2">{items.map((item, index) => <Card key={item.id || index}><CardContent className="space-y-2 p-4"><div className="flex items-center justify-between"><p className="font-medium">{item.name || item.quote_number || item.invoice_number || item.email || `Record ${item.id || index + 1}`}</p><Badge variant="outline">{item.status || item.portal_type || "visible"}</Badge></div><pre className="max-h-36 overflow-auto rounded bg-muted p-2 text-xs">{JSON.stringify(item, null, 2)}</pre>{actionLabel ? <Button size="sm" variant="outline">{actionLabel}</Button> : null}</CardContent></Card>)}</div>;
}

function PortalNotice() {
  return <div className="rounded-md border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">Portal session required or not authorized. Open the portal login page and enter a valid invite token.</div>;
}
