import GridTable from "@/shared/data-grid/GridTable";
import { NativeSelect } from "@/components/ui/native-select";
import { recordPreviewProps } from "@/components/RecordQuickPreview";
import React, { useEffect, useRef, useState } from "react";
import { useQuery } from '@tanstack/react-query';
import { useRecordScope } from '@/shared/records/Record360Workspace';
import { useRecordScopeOwner } from '@/hooks/use-record-scope-owner';
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
      <GridTable gridId="features/access/DashboardStudio:table-1">
        <tbody>
          {data.groups.map((g: any) => (
            <tr {...recordPreviewProps(g)} key={g.label}>
              <td>{g.label}</td>
              <td>{g.count}</td>
            </tr>
          ))}
        </tbody>
      </GridTable>
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

type StudioProps={
  company: number;
  mutate: (f: () => Promise<any>, isCurrent?:()=>boolean) => Promise<void>;
};
export default function DashboardStudio(props:StudioProps) {
  const scope=useRecordScope();
  const key=`${props.company}:${scope}`,current=useRef(key);
  current.current=key;
  return <ScopedDashboardStudio key={key} {...props} scope={scope} contextCurrent={()=>current.current===key}/>;
}
function ScopedDashboardStudio({company,mutate,scope,contextCurrent}:StudioProps&{scope:string;contextCurrent:()=>boolean}) {
  const ownsRecordScope=useRecordScopeOwner();
  const ownsScope=()=>contextCurrent()&&ownsRecordScope();
  const user = useAuthStore((s) => s.user);
  const draftKey=useRef<string|null>(null),cloneKey=useRef<string|null>(null);
  const [saving,setSaving]=useState(false);
  const roles=useQuery({queryKey:['dashboard-role-choices',company,scope],queryFn:()=>api.get('/access/catalog',{params:{companyId:company}}).then(r=>r.data.legacyRoles as {id:number;name:string}[]),retry:false});
  const [saved, setSaved] = useState<any[]>([]),
    [selected, setSelected] = useState<any>(null),
    [name, setName] = useState("My business dashboard"),
    [widgets, setWidgets] = useState<any[]>([]),
    [shared, setShared] = useState<number[]>([]),
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
      .then((r) => {if(ownsScope())setSaved(r.data);})
      .catch((e) => {if(ownsScope())setError(message(e));});
  }, [company]);
  function change(rows: any[]) {
    setWidgets(rows);
    setDirty(true);
  }
  function choose(id: string) {
    if (dirty && !window.confirm("Discard unsaved dashboard changes?")) return;
    const row = saved.find((r) => String(r.id) === id);
    draftKey.current=null;cloneKey.current=null;
    setSelected(row || null);
    setWidgets(row?.values_json.widgets || []);
    setName(row?.values_json.name || "My business dashboard");
    setShared(row?.values_json.sharedRoles || []);
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
    if(saving||!ownsScope())return;
    setError("");
    const newKey=()=>`user:${user?.id}:${crypto.randomUUID()}`;
    const key=clone?(cloneKey.current??=newKey()):selected?selected.scope_key.split(':dashboard:')[1]:(draftKey.current??=newKey());
    setSaving(true);
    try{await mutate(async () => {
      if(!ownsScope())throw new Error('Dashboard context changed');
      const result = await api.put(root + "/policies", {
        companyId: company,
        kind: "dashboard",
        key,
        version: clone ? 0 : selected?.version || 0,
        reason: "Save authorized enterprise dashboard layout",
        values: {
          name: clone ? name + " copy" : name,
          widgets,
          sharedRoles: shared,
        },
      });
      if(!ownsScope())return;
      if(clone)cloneKey.current=null;
      setSelected(result.data);
      setName(result.data.values_json.name);
      setDirty(false);
      setSaved((old: any[]) => [
        result.data,
        ...old.filter((r) => r.id !== result.data.id),
      ]);
    },ownsScope);}finally{if(ownsScope())setSaving(false);}
  }
  return (
    <fieldset disabled={saving} className="cc-card ec-studio min-w-0">
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
        <NativeSelect
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
        </NativeSelect>
        <input
          aria-label="Dashboard name"
          value={name}
          onChange={(e) => {
            setName(e.target.value);
            setDirty(true);
          }}
        />
        <fieldset className="min-w-0 space-y-2">
          <legend>Share dashboard with roles</legend>
          {roles.isPending&&<p role="status">Loading role choices…</p>}
          {roles.data?.map(role=><label key={role.id} className="flex items-center gap-2"><input type="checkbox" checked={shared.includes(role.id)} onChange={e=>{setShared(current=>e.target.checked?[...current,role.id]:current.filter(id=>id!==role.id));setDirty(true);}}/>{role.name}</label>)}
          {roles.isError&&<p role="alert">Role choices could not load. <Button type="button" variant="outline" onClick={()=>void roles.refetch()}>Retry role choices</Button></p>}
          {roles.data&&shared.filter(id=>!roles.data!.some(role=>role.id===id)).map(id=><p key={id}>A previously selected role is unavailable. <Button type="button" variant="outline" onClick={()=>{setShared(current=>current.filter(value=>value!==id));setDirty(true);}}>Remove unavailable role</Button></p>)}
          {!shared.length&&<p className="text-xs text-muted-foreground">Private to you until roles are selected.</p>}
        </fieldset>
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
              <NativeSelect
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
              </NativeSelect>
              <NativeSelect
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
              </NativeSelect>
              <NativeSelect
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
              </NativeSelect>
            </div>
            <Widget widget={widget} company={company} />
          </article>
        ))}
      </div>
    </fieldset>
  );
}
