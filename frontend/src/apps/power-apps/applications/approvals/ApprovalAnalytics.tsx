import { useEffect, useState } from "react";
import {
  approvalApi as api,
  errorMessage,
  duration,
  type Analytics,
  type Policy,
} from "./api";
function Bars({
  title,
  items,
}: {
  title: string;
  items: { label: string; value: number }[];
}) {
  const max = Math.max(1, ...items.map((i) => i.value));
  return (
    <section className="ap-panel">
      <h3>{title}</h3>
      {items.length ? (
        items.slice(0, 20).map((i, n) => (
          <div className="ap-bar" key={n}>
            <span>{i.label}</span>
            <div>
              <i style={{ width: `${(i.value / max) * 100}%` }} />
            </div>
            <b>{Number.isInteger(i.value) ? i.value : i.value.toFixed(1)}</b>
          </div>
        ))
      ) : (
        <p className="ap-empty">No persisted records for these filters.</p>
      )}
    </section>
  );
}
export function ApprovalAnalytics({
  data,
  environment,
  policies,
}: {
  data: Analytics | null;
  environment: string;
  policies: Policy[];
}) {
  const [result, setResult] = useState(data),
    [filters, setFilters] = useState({
      start: "",
      end: "",
      policy_id: "",
      status: "",
    }),
    [error, setError] = useState("");
  useEffect(() => setResult(data), [data]);
  const percent = (n: number | null | undefined) =>
    n == null ? "—" : `${(n * 100).toFixed(1)}%`;
  return (
    <>
      <form
        className="ap-panel ap-actions"
        onSubmit={async (e) => {
          e.preventDefault();
          try {
            setResult(
              await api.get<Analytics>("/analytics", environment, {
                start: filters.start
                  ? new Date(filters.start + "T00:00:00Z").toISOString()
                  : undefined,
                end: filters.end
                  ? new Date(
                      new Date(filters.end + "T00:00:00Z").getTime() + 86400000,
                    ).toISOString()
                  : undefined,
                policy_id: filters.policy_id || undefined,
                status: filters.status || undefined,
              }),
            );
            setError("");
          } catch (e) {
            setError(errorMessage(e));
          }
        }}
      >
        <label>
          From
          <input
            type="date"
            value={filters.start}
            onChange={(e) => setFilters({ ...filters, start: e.target.value })}
          />
        </label>
        <label>
          Through
          <input
            type="date"
            value={filters.end}
            onChange={(e) => setFilters({ ...filters, end: e.target.value })}
          />
        </label>
        <label>
          Approval process
          <select
            value={filters.policy_id}
            onChange={(e) =>
              setFilters({ ...filters, policy_id: e.target.value })
            }
          >
            <option value="">All authorized processes</option>
            {policies.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name}
              </option>
            ))}
          </select>
        </label>
        <label>
          Status
          <select
            value={filters.status}
            onChange={(e) => setFilters({ ...filters, status: e.target.value })}
          >
            <option value="">All statuses</option>
            {[
              "Pending",
              "Approved",
              "Rejected",
              "Changes Requested",
              "Resolution Required",
              "Cancelled",
              "Expired",
              "Failed",
            ].map((s) => (
              <option key={s}>{s}</option>
            ))}
          </select>
        </label>
        <button className="ap-primary">Apply filters</button>
      </form>
      {error && (
        <p className="ap-error" role="alert">
          {error}
        </p>
      )}
      {result ? (
        <>
          <div className="ap-metrics">
            {[
              [
                "Average approval time",
                duration(result.counts.average_seconds),
              ],
              ["Overdue requests", String(result.counts.overdue ?? 0)],
              ["Rejection rate", percent(result.rejection_rate)],
              ["SLA compliance", percent(result.sla_compliance)],
            ].map(([label, value]) => (
              <div className="ap-metric" key={label}>
                <small>{label}</small>
                <strong>{value}</strong>
                <span>From authorized persisted history</span>
              </div>
            ))}
          </div>
          <div className="ap-chart-grid">
            <Bars
              title="Requests by status"
              items={Object.entries(result.by_status).map(([label, value]) => ({
                label,
                value,
              }))}
            />
            <Bars
              title="Stage decision time (hours)"
              items={result.stage_times.map((s) => ({
                label: s.stage,
                value: s.average_seconds / 3600,
              }))}
            />
            <Bars
              title="Requests by department"
              items={result.by_department.map((s) => ({
                label: s.department,
                value: s.count,
              }))}
            />
            <Bars
              title="Daily request volume · latest 14 active days"
              items={result.volume_trend
                .slice(-14)
                .map((s) => ({ label: s.date, value: s.count }))}
            />
            <Bars
              title="Approver workload"
              items={result.workload.map((s) => ({
                label: `User #${s.user_id}`,
                value: s.pending,
              }))}
            />
            <Bars
              title="Workflow bottlenecks · pending seats"
              items={result.bottlenecks.map((s) => ({
                label: `${s.stage} (${s.overdue} overdue)`,
                value: s.pending,
              }))}
            />
          </div>
        </>
      ) : (
        <p>Loading analytics…</p>
      )}
    </>
  );
}
