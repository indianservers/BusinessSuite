import { useState } from "react";
import { platformApi as api } from "@/services/platform-api";
import { useData, useOwner, message, Loading, Alert, Bars, Dialog, Table, date, money, download, type Data } from "./shared";
export default function Reports({ overview = false }: {
    overview?: boolean;
}) {
    const { me } = useOwner();
    const [days, setDays] = useState("30");
    const [start, setStart] = useState("");
    const [end, setEnd] = useState("");
    const [schedule, setSchedule] = useState(false);
    const [error, setError] = useState("");
    const [notice, setNotice] = useState("");
    const [windowEnd] = useState(() => new Date());
    const query = new URLSearchParams();
    if (days === "custom") {
        if (start)
            query.set("start", new Date(start + "T00:00:00").toISOString());
        if (end)
            query.set("end", new Date(end + "T23:59:59").toISOString());
    }
    else {
        query.set("start", new Date(windowEnd.getTime() - Number(days) * 86400000).toISOString());
        query.set("end", windowEnd.toISOString());
    }
    const report = useData<Data>("/platform/reports?" + query.toString());
    const saved = useData<Data[]>("/platform/records/report_snapshot");
    const r = report.data;
    return <><header className="po-heading"><div><h1>{overview ? "Platform overview" : "Reports & insights"}</h1><p>Real signup, customer and subscription statistics from the Indian Servers owner database.</p></div><div className="po-actions"><button onClick={() => download("/platform/report-export?" + query.toString(), "platform-report.json").catch(e => setError(message(e)))}>Export report</button><button onClick={() => setSchedule(true)}>Schedule report</button></div></header><section className="po-panel"><div className="po-filters"><label>Period<select value={days} onChange={e => setDays(e.target.value)}><option value="7">Last 7 days</option><option value="30">Last 30 days</option><option value="90">Last 90 days</option><option value="365">Last year</option><option value="custom">Custom dates</option></select></label>{days === "custom" && <><label>From<input type="date" value={start} onChange={e => setStart(e.target.value)}/></label><label>Through<input type="date" value={end} onChange={e => setEnd(e.target.value)}/></label></>}<button onClick={report.refresh}>Refresh statistics</button></div><small>Dates display in Asia/Kolkata. Signup and conversion metrics use the same submission cohort.</small></section><Loading busy={report.busy} error={report.error}/><Alert error={error}/>{notice && <div className="po-notice">{notice}</div>}{r && <>
    <div className="po-stats">{[["Signup requests", r.summary.signups], ["Companies", r.summary.companies], ["Individuals", r.summary.individuals], ["Awaiting decision", r.summary.pending], ["Approved", r.summary.approved], ["Overdue reviews", r.summary.overdue]].map(([title, value]) => <section key={String(title)} className="po-stat"><span>{title}</span><strong>{value}</strong></section>)}</div>
    <div className="po-grid"><section className="po-panel"><h2>Acquisition by day</h2><Bars values={Object.fromEntries(r.trends.map((d: Data) => [d.date, d.signups]))}/><small>Number of submissions on days with activity · {date(r.start)} to {date(r.end)}</small></section><section className="po-panel"><h2>Signup-to-paid funnel</h2><Bars values={r.funnel}/><small>Distinct applications at each milestone in the selected submission cohort.</small></section><section className="po-panel"><h2>Application demand</h2><Bars values={Object.fromEntries(Object.entries(r.modules).map(([key, value]) => [me.modules.find((m: Data) => m.key === key)?.label || key, Number(value)]))}/><small>Requested application counts; applicants may choose several apps.</small></section><section className="po-panel"><h2>Customer lifecycle</h2><Bars values={r.customer_status}/><small>Current customer states across all permitted customer accounts.</small></section></div>
    <div className="po-stats">{[["Approval rate", r.summary.approval_rate == null ? "—" : r.summary.approval_rate + "%"], ["Rejection rate", r.summary.rejection_rate == null ? "—" : r.summary.rejection_rate + "%"], ["Median review", r.summary.median_review_hours == null ? "—" : r.summary.median_review_hours.toFixed(1) + "h"], ["90th percentile review", r.summary.p90_review_hours == null ? "—" : r.summary.p90_review_hours.toFixed(1) + "h"], ["Signup growth", r.summary.growth_pct == null ? "—" : r.summary.growth_pct + "%"], ["Paid cohort churn", r.summary.churn_pct == null ? "—" : r.summary.churn_pct + "%"]].map(([title, value]) => <section key={String(title)} className="po-stat"><span>{title}</span><strong>{value}</strong></section>)}</div>
    {!overview && <><div className="po-grid"><section className="po-panel"><h2>Lead sources</h2><Bars values={r.sources}/></section><section className="po-panel"><h2>Campaign attribution</h2><Bars values={r.campaigns}/></section><section className="po-panel"><h2>Reviewer decisions</h2><Bars values={Object.fromEntries(Object.entries(r.reviewer_decisions).map(([id, n]) => [`Reviewer #${id}`, Number(n)]))}/></section><section className="po-panel"><h2>Invitation lifecycle</h2><Bars values={r.invitations}/><small>Invitation records, including replacement invitations. “Ready local” is not an email delivery claim.</small></section></div>
      <section className="po-panel"><h2>Commercial statistics</h2><div className="po-stats">{Object.entries(r.mrr_minor_by_currency).map(([currency, value]) => <div className="po-stat" key={currency}><span>Monthly contract value · {currency}</span><strong>{money(Number(value), currency)}</strong></div>)}{Object.entries(r.offline_receipts_minor_by_currency).map(([currency, value]) => <div className="po-stat" key={"receipt" + currency}><span>Recorded receipts · {currency}</span><strong>{money(Number(value), currency)}</strong></div>)}</div><p>{r.summary.cancelled_in_period} cancellations in period · {r.summary.active_customers} current paid customers</p><small>Amounts are grouped by currency. Receipts record offline payments already received; this portal does not charge customers.</small></section>
      <section className="po-panel"><h2>Scheduled report snapshots</h2><Table rows={saved.data || []} columns={[{ label: "Report", render: r => r.title }, { label: "Generated", render: r => date(r.created_at) }, { label: "Summary", render: r => `${r.data.summary?.signups || 0} signups · ${r.data.summary?.customers || 0} customers` }]}/></section></>}
    <section className="po-panel"><h2>Operational health</h2><div className="po-status-line"><span>Failed provisioning attempts: {r.health.failed_provisioning_attempts}</span><span>Overdue reviews: {r.health.overdue_reviews}</span>{r.health.failed_logins_30d != null && <span>Failed owner logins in 30 days: {r.health.failed_logins_30d}</span>}</div><details><summary>Metric definitions</summary>{Object.entries(r.definitions).map(([key, value]) => <p key={key}><strong>{key.split("_").join(" ")}</strong> · {String(value)}</p>)}</details></section>
  </>}{schedule && <Dialog title="Schedule an owner report" onClose={() => setSchedule(false)}><form className="po-form" onSubmit={async (e) => { e.preventDefault(); const f = new FormData(e.currentTarget); try {
        await api.post("/platform/records/scheduled_report", { title: f.get("title"), data: { frequency: f.get("frequency"), next_run_at: new Date().toISOString() } });
        setNotice("Report scheduled. The local due-work runner creates snapshots and an owner notification.");
        setSchedule(false);
    }
    catch (err) {
        setError(message(err));
    } }}><label>Report name<input name="title" required minLength={2}/></label><label>Frequency<select name="frequency"><option value="daily">Daily</option><option value="weekly">Weekly</option></select></label><p>Reports use your permitted data and are saved in this local portal.</p><button className="po-primary">Schedule report</button></form></Dialog>}</>;
}
