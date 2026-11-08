import GroupedRecords from "@/shared/data-grid/GroupedRecords";
import { standardRecordGroups } from "@/shared/data-grid/record-group-fields";
import { useState } from 'react';
import { Link } from 'react-router-dom';
import { ArrowUpRight, Search } from 'lucide-react';
const reports = [
    { name: 'Sales performance', group: 'Sales', path: '/crm/sales-performance', description: 'Compare sales results and progress across the permitted team.' },
    { name: 'Sales funnel', group: 'Sales', path: '/crm/funnel', description: 'Find where opportunities progress and where conversion drops.' },
    { name: 'Lost opportunity analysis', group: 'Sales', path: '/crm/lost-analysis', description: 'Review loss reasons and opportunities to improve qualification.' },
    { name: 'Forecast and quota', group: 'Planning', path: '/crm/forecasting', description: 'Review pipeline expectations and forecast categories.' },
    { name: 'Sales targets', group: 'Planning', path: '/crm/targets', description: 'Compare targets, ownership and actual performance.' },
    { name: 'Lead statistics', group: 'Relationships', path: '/crm/statistics/leads?period=month', description: 'Inspect lead totals and the underlying records for the selected period.' },
    { name: 'Deal statistics', group: 'Relationships', path: '/crm/statistics/open-deals?period=month', description: 'Explore open deal totals with a record-level worklist.' },
    { name: 'Customer product audiences', group: 'Relationships', path: '/crm/product-customers', description: 'Understand which customers are connected to products and services.' },
    { name: 'Follow-up commitments', group: 'Execution', path: '/crm/customer-follow-ups', description: 'Find upcoming customer commitments and overdue work.' },
    { name: 'Delivery logs', group: 'Execution', path: '/crm/delivery-logs', description: 'Investigate communication delivery results and failures.' },
    { name: 'Lead-to-cash', group: 'Execution', path: '/crm/lead-to-cash', description: 'Trace sales into quotations, delivery and accounting.' },
];
export default function CRMReportDirectory() {
    const [search, setSearch] = useState(''), [group, setGroup] = useState('All');
    const filtered = reports.filter(r => (group === 'All' || r.group === group) && `${r.name} ${r.description}`.toLowerCase().includes(search.trim().toLowerCase()));
    return <section className="space-y-4 rounded-xl border bg-card p-4 sm:p-6" aria-label="CRM report directory"><header><h1 className="text-2xl font-semibold">Reports and insights</h1><p className="mt-2 text-sm text-muted-foreground">Choose the question you want to answer. Win/loss analysis remains below.</p></header><div className="flex flex-wrap gap-3"><label className="flex min-w-0 flex-[1_1_240px] items-center gap-2 rounded-md border px-3 py-2"><Search size={16}/><input className="min-w-0 flex-1 bg-transparent outline-none" aria-label="Search report directory" placeholder="Find a report or a business question…" value={search} onChange={e => setSearch(e.target.value)}/></label><select className="rounded border bg-background p-2 text-sm" aria-label="Report category" value={group} onChange={e => setGroup(e.target.value)}>{['All', 'Sales', 'Planning', 'Relationships', 'Execution'].map(v => <option key={v}>{v}</option>)}</select></div><GroupedRecords scope="apps/crm/CRMReportDirectory:cards-1" items={(filtered) || []} fields={standardRecordGroups((filtered) || [])} gridClassName="grid gap-3 sm:grid-cols-2 xl:grid-cols-3" renderItem={r => <Link key={r.path} to={r.path} className="group rounded-lg border p-4 hover:border-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"><span className="text-xs text-muted-foreground">{r.group}</span><h2 className="mt-2 flex items-center justify-between gap-2 font-medium">{r.name}<ArrowUpRight size={15}/></h2><p className="mt-2 text-sm text-muted-foreground">{r.description}</p></Link>}/>{!filtered.length && <p role="status" className="py-4 text-sm text-muted-foreground">No matching reports. Try another search or category.</p>}</section>;
}
