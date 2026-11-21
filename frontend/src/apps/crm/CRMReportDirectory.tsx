import CRMPageHeader from "./CRMPageHeader";
import { NativeSelect } from "@/components/ui/native-select";
import CRMReportBuilder from "./CRMReportBuilder";
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
    return (
        <section className="min-w-0 space-y-4" aria-label="CRM report directory">
            <CRMPageHeader title="Reports and insights" description="Explore sales performance, customer activity, and revenue forecasts." />
            <div className="flex flex-wrap gap-2 rounded-xl border bg-card p-3">
                <label className="flex min-w-0 flex-[1_1_220px] items-center gap-2 rounded-md border bg-background px-3 py-2">
                    <Search size={16} aria-hidden="true" className="shrink-0 text-muted-foreground" />
                    <input className="min-w-0 flex-1 bg-transparent outline-none" aria-label="Search report directory"
                        placeholder="Find a report…" value={search} onChange={event => setSearch(event.target.value)} />
                </label>
                <NativeSelect className="min-h-11 rounded-md border bg-background px-3 text-sm" aria-label="Report category"
                    value={group} onChange={event => setGroup(event.target.value)}>
                    {["All", "Sales", "Planning", "Relationships", "Execution"].map(value =>
                        <option key={value} value={value}>{value === "All" ? "All categories" : value}</option>)}
                </NativeSelect>
            </div>
            {filtered.length ? (
                <GroupedRecords scope="apps/crm/CRMReportDirectory:cards-1" items={filtered}
                    fields={standardRecordGroups(filtered)} gridClassName="grid gap-3 sm:grid-cols-2 xl:grid-cols-3"
                    renderItem={report => (
                        <Link key={report.path} to={report.path} className="crm-report-link">
                            <span className="text-xs font-medium text-primary">{report.group}</span>
                            <h2 className="flex items-start justify-between gap-2 font-semibold">
                                {report.name}<ArrowUpRight size={16} aria-hidden="true" className="shrink-0 text-muted-foreground" />
                            </h2>
                            <p className="text-sm leading-relaxed text-muted-foreground">{report.description}</p>
                        </Link>
                    )}
                />
            ) : <p role="status" className="rounded-xl border border-dashed p-5 text-sm text-muted-foreground">No reports match. Try another search or category.</p>}
            <CRMReportBuilder />
        </section>
    );
}
