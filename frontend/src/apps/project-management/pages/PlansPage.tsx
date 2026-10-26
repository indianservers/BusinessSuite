import { RichTextContent } from "@/components/rich-text/RichTextContent";
import { useState } from "react";
import { Link } from "react-router-dom";
import { capabilityTiers } from "../capabilities";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";

export default function PlansPage() {
  const [search, setSearch] = useState("");
  const [pendingOnly, setPendingOnly] = useState(false);
  const [tier, setTier] = useState("");
  const all = capabilityTiers.flatMap(tier => tier.features);
  return <main className="space-y-6">
    <header><h1 className="page-title">Plans and capabilities</h1><p className="page-description">Core, Business, Business Plus and Enterprise capability groups. Each higher tier includes the preceding groups.</p></header>
    <div className="rounded-lg border bg-muted/30 p-4 text-sm">This page shows implementation status, not a paid subscription. Pricing, checkout, plan assignment, feature gating and usage allowances are not configured. “Available” describes implemented functionality; deployment and verification requirements still apply.</div>
    <div className="flex flex-wrap items-center gap-3"><Input aria-label="Search plan features" placeholder="Search features and remaining work…" className="max-w-md" value={search} onChange={event => setSearch(event.target.value)} /><select aria-label="Filter capability tier" className="h-10 rounded-md border bg-background px-3" value={tier} onChange={event => setTier(event.target.value)}><option value="">All tiers</option>{capabilityTiers.map(tier => <option key={tier.name}>{tier.name}</option>)}</select><label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={pendingOnly} onChange={event => setPendingOnly(event.target.checked)} />Show remaining work only</label></div>
    <p className="text-sm text-muted-foreground">{all.filter(feature => feature.status === "Available").length} available · {all.filter(feature => feature.status === "Partial").length} partial · {all.filter(feature => feature.status === "Not implemented").length} not implemented. Counts cover the catalogue entries, not percentage parity with ClickUp.</p>
    <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
      {capabilityTiers.filter(group => !tier || group.name === tier).map((group, index) => {
        const features = group.features.filter(feature => (!pendingOnly || feature.status !== "Available") && `${feature.name} ${feature.detail}`.toLowerCase().includes(search.trim().toLowerCase()));
        return <section key={group.name} aria-label={`${group.name} capabilities`} className="space-y-4 rounded-xl border p-5"><header><h2 className="text-xl font-semibold">{group.name}</h2><div className="mt-1 text-sm text-muted-foreground"><RichTextContent value={group.description}/></div>{index > 0 && !tier && <p className="mt-2 text-xs text-muted-foreground">Also includes the earlier capability groups.</p>}</header>{!features.length ? <p className="text-sm text-muted-foreground">No features match these filters.</p> : <ul className="space-y-4">{features.map(feature => <li key={feature.name} className="space-y-2 border-t pt-3"><div className="flex flex-wrap items-center gap-2"><h3 className="text-sm font-semibold">{feature.name}</h3><Badge variant={feature.status === "Available" ? "default" : "outline"}>{feature.status}</Badge></div><p className="text-xs leading-relaxed text-muted-foreground">{feature.detail}</p>{feature.href && <Link className="inline-block text-xs text-primary underline" to={feature.href}>Open existing tools</Link>}</li>)}</ul>}</section>;
      })}
    </div>
    <section className="space-y-3 border-t pt-5"><h2 className="text-lg font-semibold">Other unfinished PMS foundations</h2><p className="text-sm text-muted-foreground">Configurable statuses/workflows, recurrence execution, field-aware task creation and table filtering, task-view consolidation, team assignment/sharing, full trash retention, accessibility and scale acceptance tests also remain on the implementation roadmap.</p><p className="text-sm text-muted-foreground">AI agents exist separately in the suite, but premium-model quotas, pooled credits and the AI bundles shown in the reference are not implemented by these tiers.</p></section>
  </main>;
}
