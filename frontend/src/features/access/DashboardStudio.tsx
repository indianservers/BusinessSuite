import React, { useEffect, useState } from "react";
import { api } from "@/services/api";
import { useAuthStore } from "@/store/authStore";
import { Button } from "@/components/ui/button";
const sources = [
  ["crm_leads", "CRM leads"],
  ["crm_pipeline", "Sales pipeline"],
  ["projects", "PMS projects"],
  ["tasks", "PMS tasks"],
  ["invoices", "Invoices"],
  ["employees", "Employees"],
];
const kinds = ["kpi", "table", "bar", "line", "donut", "funnel", "trend"];
const root = "/access/enterprise";
const message = (e: any) =>
  typeof e?.response?.data?.detail === "string"
    ? e.response.data.detail
    : e.message;

function Widget({ widget, company }: { widget: any; company: number }) {
  const [data, setData] = useState<any>(null),
    [error, setError] = useState("");
  useEffect(() => {
    let live = true;
    setData(null);
    setError("");
    api
      .get(root + "/analytics", {
        params: { companyId: company, source: widget.source },
        progress: false,
      })
      .then((r) => {
        if (live) setData(r.data);
      })
      .catch((e) => {
        if (live) setError(message(e));
      });
    return () => {
      live = false;
    };
  }, [company, widget.source]);
  if (error) return <p role="status">{error}</p>;
  if (!data) return <p>Loading authorized metric…</p>;
  if (widget.type === "kpi")
    return <strong className="ec-total">{data.count.toLocaleString()}</strong>;
  if (widget.type === "line" || widget.type === "trend") {
    const series = data.series || [];
    const max = Math.max(1, ...series.map((p: any) => p.count));
    return (
      <>
        <svg
          viewBox="0 0 300 110"
          role="img"
          aria-label="Actual records created by day"
        >
          <polyline
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            points={series
              .map(
                (p: any, i: number) =>
                  `${series.length > 1 ? (i / (series.length - 1)) * 280 + 10 : 150},${95 - (p.count / max) * 80}`,
              )
              .join(" ")}
          />
          {series.map((p: any, i: number) => (
            <circle
              key={p.date}
              cx={
                series.length > 1 ? (i / (series.length - 1)) * 280 + 10 : 150
              }
              cy={95 - (p.count / max) * 80}
              r="3"
            >
              <title>
                {p.date}: {p.count}
              </title>
            </circle>
          ))}
        </svg>
        <small>
          Records created by day · {series[0]?.date || "No observations"} to{" "}
          {series.at(-1)?.date || "—"}
        </small>
      </>
    );
  }
  if (widget.type === "donut") {
    let offset = 0;
    return (
      <div className="ec-donut">
        <svg
          viewBox="0 0 100 100"
          role="img"
          aria-label="Authorized records by status"
        >
          {data.groups.map((g: any, i: number) => {
            const size = (g.count / Math.max(1, data.count)) * 251.33;
            const start = offset;
            offset += size;
            return (
              <circle
                key={g.label}
                cx="50"
                cy="50"
                r="40"
                fill="none"
                stroke={
                  ["#6d28d9", "#0f766e", "#b45309", "#2563eb", "#be185d"][i % 5]
                }
                strokeWidth="13"
                strokeDasharray={`${size} ${251.33 - size}`}
                strokeDashoffset={-start}
              >
                <title>
                  {g.label}: {g.count}
                </title>
              </circle>
            );
          })}
        </svg>
        <div>
          {data.groups.map((g: any) => (
            <p key={g.label}>
              {g.label}: {g.count}
            </p>
          ))}
        </div>
      </div>
    );
  }
  if (widget.type === "table")
    return (
      <table>
        <tbody>
          {data.groups.map((g: any) => (
            <tr key={g.label}>
              <td>{g.label}</td>
              <td>{g.count}</td>
            </tr>
          ))}
        </tbody>
      </table>
    );
  return (
    <div className="cc-bars">
      {data.groups.map((g: any) => (
        <div className="cc-bar" key={g.label}>
          <span>{g.label}</span>
          <meter
            min={0}
            max={Math.max(1, data.count)}
            value={g.count}
            aria-label={`${g.label}: ${g.count}`}
          />
          <strong>{g.count}</strong>
        </div>
      ))}
      {widget.type === "funnel" && (
        <small>
          Status distribution; not an inferred lifecycle conversion.
        </small>
      )}
    </div>
  );
}

export default function DashboardStudio({
  company,
  mutate,
}: {
  company: number;
  mutate: (f: () => Promise<any>) => Promise<void>;
}) {
  const user = useAuthStore((s) => s.user);
  const [saved, setSaved] = useState<any[]>([]),
    [selected, setSelected] = useState<any>(null),
    [name, setName] = useState("My business dashboard"),
    [widgets, setWidgets] = useState<any[]>([]),
    [shared, setShared] = useState(""),
    [dirty, setDirty] = useState(false),
    [error, setError] = useState("");
  useEffect(() => {
    setSelected(null);
    setWidgets([]);
    setDirty(false);
    api
      .get(root + "/policies", {
        params: { companyId: company, kind: "dashboard" },
      })
      .then((r) => setSaved(r.data))
      .catch((e) => setError(message(e)));
  }, [company]);
  function change(rows: any[]) {
    setWidgets(rows);
    setDirty(true);
  }
  function choose(id: string) {
    if (dirty && !window.confirm("Discard unsaved dashboard changes?")) return;
    const row = saved.find((r) => String(r.id) === id);
    setSelected(row || null);
    setWidgets(row?.values_json.widgets || []);
    setName(row?.values_json.name || "My business dashboard");
    setShared((row?.values_json.sharedRoles || []).join(","));
    setDirty(false);
  }
  function move(index: number, direction: number) {
    const next = [...widgets];
    const target = index + direction;
    if (target < 0 || target >= next.length) return;
    [next[index], next[target]] = [next[target], next[index]];
    change(next);
  }
  async function save(clone = false) {
    setError("");
    let roles: number[] = [];
    try {
      roles = shared
        ? shared.split(",").map((v) => {
            if (!/^\d+$/.test(v.trim()))
              throw new Error("Enter comma-separated numeric role IDs");
            return Number(v.trim());
          })
        : [];
    } catch (e) {
      setError(message(e));
      return;
    }
    await mutate(async () => {
      const key =
        clone || !selected
          ? `user:${user?.id}:${Date.now()}`
          : selected.scope_key.split(":dashboard:")[1];
      const result = await api.put(root + "/policies", {
        companyId: company,
        kind: "dashboard",
        key,
        version: clone ? 0 : selected?.version || 0,
        reason: "Save authorized enterprise dashboard layout",
        values: {
          name: clone ? name + " copy" : name,
          widgets,
          sharedRoles: roles,
        },
      });
      setSelected(result.data);
      setName(result.data.values_json.name);
      setDirty(false);
      setSaved((old: any[]) => [
        result.data,
        ...old.filter((r) => r.id !== result.data.id),
      ]);
    });
  }
  return (
    <section className="cc-card ec-studio">
      <div className="cc-heading">
        <div>
          <h2>Dashboard studio</h2>
          <p>
            Saved layouts share presentation only. Every widget rechecks the
            viewer’s record permissions.
          </p>
        </div>
        <span>{dirty ? "Unsaved changes" : "Saved / new layout"}</span>
      </div>
      <div className="ec-toolbar">
        <select
          aria-label="Saved dashboard"
          value={selected?.id || ""}
          onChange={(e) => choose(e.target.value)}
        >
          <option value="">New dashboard</option>
          {saved.map((d) => (
            <option key={d.id} value={d.id}>
              {d.values_json.name}
            </option>
          ))}
        </select>
        <input
          aria-label="Dashboard name"
          value={name}
          onChange={(e) => {
            setName(e.target.value);
            setDirty(true);
          }}
        />
        <input
          aria-label="Share dashboard with role IDs"
          value={shared}
          placeholder="Role IDs to share"
          onChange={(e) => {
            setShared(e.target.value);
            setDirty(true);
          }}
        />
        <Button
          variant="outline"
          disabled={widgets.length >= 24}
          onClick={() =>
            change([
              ...widgets,
              {
                source: "crm_leads",
                type: "kpi",
                width: 1,
                title: "CRM leads",
              },
            ])
          }
        >
          Add widget
        </Button>
        <Button onClick={() => save()}>Save layout</Button>
        <Button variant="outline" onClick={() => save(true)}>
          Clone
        </Button>
      </div>
      {error && <p role="alert">{error}</p>}
      <div className="ec-dashboard-grid">
        {widgets.map((widget, index) => (
          <article
            className="cc-card ec-widget"
            key={index}
            style={{ gridColumn: `span ${widget.width}` }}
          >
            <div className="ec-toolbar">
              <input
                aria-label={`Widget ${index + 1} title`}
                value={widget.title}
                onChange={(e) =>
                  change(
                    widgets.map((w, i) =>
                      i === index ? { ...w, title: e.target.value } : w,
                    ),
                  )
                }
              />
              <button
                aria-label={`Move widget ${index + 1} up`}
                onClick={() => move(index, -1)}
              >
                ↑
              </button>
              <button
                aria-label={`Move widget ${index + 1} down`}
                onClick={() => move(index, 1)}
              >
                ↓
              </button>
              <button
                aria-label={`Remove widget ${index + 1}`}
                onClick={() => change(widgets.filter((_, i) => i !== index))}
              >
                ×
              </button>
            </div>
            <div className="ec-toolbar">
              <select
                aria-label={`Widget ${index + 1} source`}
                value={widget.source}
                onChange={(e) =>
                  change(
                    widgets.map((w, i) =>
                      i === index ? { ...w, source: e.target.value } : w,
                    ),
                  )
                }
              >
                {sources.map(([id, label]) => (
                  <option key={id} value={id}>
                    {label}
                  </option>
                ))}
              </select>
              <select
                aria-label={`Widget ${index + 1} chart`}
                value={widget.type}
                onChange={(e) =>
                  change(
                    widgets.map((w, i) =>
                      i === index ? { ...w, type: e.target.value } : w,
                    ),
                  )
                }
              >
                {kinds.map((k) => (
                  <option key={k} value={k}>
                    {k}
                  </option>
                ))}
              </select>
              <select
                aria-label={`Widget ${index + 1} width`}
                value={widget.width}
                onChange={(e) =>
                  change(
                    widgets.map((w, i) =>
                      i === index ? { ...w, width: Number(e.target.value) } : w,
                    ),
                  )
                }
              >
                {[1, 2, 3].map((w) => (
                  <option key={w} value={w}>
                    {w} columns
                  </option>
                ))}
              </select>
            </div>
            <Widget widget={widget} company={company} />
          </article>
        ))}
      </div>
    </section>
  );
}
