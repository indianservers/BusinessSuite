import { useRefreshableEffect } from "@/lib/page-refresh";
import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import * as Dialog from "@radix-ui/react-dialog";
import { api } from "@/services/api";
import { workspaceError } from "./workspaceTypes";
import {
  CARD_H,
  CARD_W,
  chartSVG,
  colors,
  exportFile,
  initials,
  layoutChart,
  type OrgData,
  type OrgPerson,
} from "./orgChartLayout";
import "./OrgChartPage.css";
export default function OrgChartPage() {
  const [params] = useSearchParams();
  const [workspaces, setWorkspaces] = useState<{ id: number; name: string }[]>(
    [],
  );
  const [wid, setWid] = useState(0);
  const [data, setData] = useState<OrgData>({
    revision: 0,
    can_manage: false,
    people: [],
    teams: [],
  });
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [mode, setMode] = useState("classic");
  const [zoom, setZoom] = useState(0.85);
  const [collapsed, setCollapsed] = useState<Set<number>>(new Set());
  const [search, setSearch] = useState("");
  const [team, setTeam] = useState(0);
  const [focus, setFocus] = useState<number | null>(null);
  const [person, setPerson] = useState<OrgPerson | null>(null);
  const [draft, setDraft] = useState({
    manager_id: "",
    display_name: "",
    job_title: "",
  });
  const [retry, setRetry] = useState(0);
  const viewport = useRef<HTMLDivElement>(null);
  const pan = useRef<{
    x: number;
    y: number;
    left: number;
    top: number;
  } | null>(null);
  const base = `/project-management/workspaces/${wid}/org-chart`;
  useRefreshableEffect(() => {
    let active = true;
    void api
      .get("/project-management/workspaces")
      .then((r) => {
        if (active) {
          setWorkspaces(r.data);
          setWid(
            r.data.some(
              (w: { id: number }) => w.id === Number(params.get("workspace")),
            )
              ? Number(params.get("workspace"))
              : r.data[0]?.id || 0,
          );
          if (!r.data.length) setLoading(false);
        }
      })
      .catch((e) => {
        if (active) {
          setError(workspaceError(e));
          setLoading(false);
        }
      });
    return () => {
      active = false;
    };
  }, [retry]);
  useEffect(() => {
    if (!wid) return;
    let active = true;
    setLoading(true);
    setError("");
    setData({ revision: 0, can_manage: false, people: [], teams: [] });
    setPerson(null);
    setTeam(0);
    setSearch("");
    setCollapsed(new Set());
    setNotice("");
    void api
      .get<OrgData>(base)
      .then((r) => {
        if (active) setData(r.data);
      })
      .catch((e) => {
        if (active) setError(workspaceError(e));
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [wid, retry]);
  const [positions, setPositions] = useState<Record<string, {x:number;y:number}>>({});
  const cardDrag = useRef<{id:number;x:number;y:number;left:number;top:number}|null>(null);
  useEffect(()=>setPositions(data.positions || {}),[data.positions]);
  async function savePositions(next: Record<string,{x:number;y:number}>) {
    setBusy(true);setError("");
    try { const response=await api.put<OrgData>(`${base}/layout`,{revision:data.revision,positions:next});setData(response.data);setNotice("Chart layout saved"); }
    catch(e){setPositions(data.positions||{});setError(workspaceError(e));}
    finally{setBusy(false);}
  }
  const graph = useMemo(() => {
    const result=layoutChart(data.people,collapsed,mode,team);
    result.nodes=result.nodes.map(n=>({...n,...positions[String(n.person.id)]}));
    result.width=Math.max(result.width,...result.nodes.map(n=>n.x+CARD_W+40));
    result.height=Math.max(result.height,...result.nodes.map(n=>n.y+CARD_H+40));
    return result;
  },[data,collapsed,mode,team,positions]);
  const nodeMap = useMemo(
    () => new Map(graph.nodes.map((n) => [n.person.id, n])),
    [graph],
  );
  const searchResults = data.people
    .filter((p) =>
      `${p.name} ${p.email} ${p.job_title}`
        .toLowerCase()
        .includes(search.trim().toLowerCase()),
    )
    .slice(0, 12);
  const levels = Math.max(0, ...graph.nodes.map((n) => n.depth + 1));
  const managers = data.people.filter((p) =>
    data.people.some((x) => x.manager_id === p.id),
  ).length;
  function center(id: number) {
    const n = nodeMap.get(id);
    const el = viewport.current;
    if (n && el)
      el.scrollTo({
        left: (n.x + CARD_W / 2) * zoom - el.clientWidth / 2,
        top: (n.y + CARD_H / 2) * zoom - el.clientHeight / 2,
        behavior: "smooth",
      });
  }
  useEffect(() => {
    if (focus !== null) {
      const frame = requestAnimationFrame(() => center(focus));
      return () => cancelAnimationFrame(frame);
    }
  }, [focus, graph, zoom]);
  function fit() {
    const el = viewport.current;
    if (!el) return;
    setZoom(
      Math.max(
        0.2,
        Math.min(
          1,
          (el.clientWidth - 24) / graph.width,
          (el.clientHeight - 24) / graph.height,
        ),
      ),
    );
    el.scrollTo({ left: 0, top: 0 });
  }
  function adjustZoom(next: number) {
    const el = viewport.current;
    const value = Math.max(0.2, Math.min(1.6, next));
    if (!el) {
      setZoom(value);
      return;
    }
    const x = (el.scrollLeft + el.clientWidth / 2) / zoom,
      y = (el.scrollTop + el.clientHeight / 2) / zoom;
    setZoom(value);
    requestAnimationFrame(() =>
      el.scrollTo({
        left: x * value - el.clientWidth / 2,
        top: y * value - el.clientHeight / 2,
      }),
    );
  }
  function jump(p: OrgPerson) {
    setTeam(0);
    setCollapsed((current) => {
      const next = new Set(current);
      let cursor = p.manager_id;
      const seen = new Set<number>();
      while (cursor != null && !seen.has(cursor)) {
        next.delete(cursor);
        seen.add(cursor);
        cursor = data.people.find((v) => v.id === cursor)?.manager_id ?? null;
      }
      return next;
    });
    setFocus(p.id);
    setSearch("");
  }
  function openPerson(p: OrgPerson) {
    setPerson(p);
    setDraft({
      manager_id: p.manager_id ? String(p.manager_id) : "",
      display_name: p.display_name,
      job_title: p.job_title,
    });
    setNotice("");
  }
  function invalidManager(id: number) {
    if (!person) return false;
    const seen = new Set<number>([person.id]);
    let cursor: number | null = id;
    while (cursor !== null) {
      if (seen.has(cursor)) return true;
      seen.add(cursor);
      cursor = data.people.find((p) => p.id === cursor)?.manager_id ?? null;
    }
    return false;
  }
  async function save() {
    if (!person || busy) return;
    setBusy(true);
    setError("");
    try {
      const r = await api.put<OrgData>(`${base}/${person.id}`, {
        revision: data.revision,
        manager_id: Number(draft.manager_id) || null,
        display_name: draft.display_name,
        job_title: draft.job_title,
      });
      setData(r.data);
      setPerson(null);
      setNotice(
        "Reporting relationship saved. Workspace permissions are unchanged.",
      );
    } catch (e) {
      setError(workspaceError(e));
    } finally {
      setBusy(false);
    }
  }
  function exportCSV() {
    const cell = (v: unknown) => {
      let s = String(v ?? "");
      if (/^[\s]*[=+@-]/.test(s)) s = "'" + s;
      return '"' + s.replace(/"/g, '""') + '"';
    };
    const rows = [
      [
        "User ID",
        "Name",
        "Email",
        "Job title",
        "Workspace role",
        "Manager",
        "Teams",
      ],
      ...data.people.map((p) => [
        p.id,
        p.name,
        p.email,
        p.job_title,
        p.role,
        data.people.find((x) => x.id === p.manager_id)?.name || "",
        p.teams.map((t) => t.name).join("; "),
      ]),
    ];
    exportFile(
      "\ufeff" + rows.map((row) => row.map(cell).join(",")).join("\r\n"),
      "organization-chart.csv",
      "text/csv",
    );
  }
  return (
    <div className="org-page">
      <header className="org-page-heading">
        <div>
          <span className="org-eyebrow">PEOPLE & CONNECTIONS</span>
          <h1>Organization chart</h1>
          <p>A clear view of your people, teams and reporting lines.</p>
        </div>
        <label>
          Workspace
          <select
            aria-label="Organization workspace"
            disabled={busy}
            value={wid}
            onChange={(e) => setWid(Number(e.target.value))}
          >
            {workspaces.map((w) => (
              <option key={w.id} value={w.id}>
                {w.name}
              </option>
            ))}
          </select>
        </label>
      </header>
      <nav className="org-navigation">
        <Link to={`/pms/teams?workspace=${wid}`}>All teams</Link>
        <span aria-current="page">Organization chart</span>
        <Link to={`/pms/analytics/team?workspace=${wid}`}>Team analytics</Link>
      </nav>
      {error && (
        <div role="alert" className="org-alert">
          {error}
          <button disabled={busy} onClick={() => setRetry((v) => v + 1)}>
            Reload chart
          </button>
        </div>
      )}
      {notice && (
        <p role="status" className="org-notice">
          {notice}
        </p>
      )}
      <div className="org-stats">
        <span>
          <strong>{data.people.length}</strong> people
        </span>
        <span>
          <strong>{data.teams.length}</strong> teams
        </span>
        <span>
          <strong>{managers}</strong> managers
        </span>
        <span>
          <strong>{levels}</strong> visible levels
        </span>
        <small>
          {data.can_manage ? "You can manage reporting lines" : "View only"} ·
          Active collaborators
        </small>
      </div>
      <section className="org-board">
        <div className="org-toolbar">
          <div className="org-view-tabs" aria-label="Chart view">
            <button
              aria-pressed={mode === "classic"}
              onClick={() => setMode("classic")}
            >
              ⑂ Classic
            </button>
            <button
              aria-pressed={mode === "levels"}
              onClick={() => setMode("levels")}
            >
              ▤ By levels
            </button>
          </div>
          <div className="org-person-search">
            <input
              aria-label="Jump to person"
              placeholder="Search a name, title or email…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && searchResults[0])
                  jump(searchResults[0]);
                if (e.key === "Escape") setSearch("");
              }}
            />
            {search.trim() && (
              <div
                className="org-search-results"
                role="list"
                aria-label="Matching people"
              >
                {searchResults.map((p) => (
                  <button role="listitem" key={p.id} onClick={() => jump(p)}>
                    <strong>{p.name}</strong>
                    <small>{p.job_title || p.email}</small>
                  </button>
                ))}
                {!searchResults.length && <p>No people match your search.</p>}
              </div>
            )}
          </div>
          <select
            aria-label="Filter chart by team"
            value={team}
            onChange={(e) => {
              setTeam(Number(e.target.value));
              setFocus(null);
            }}
          >
            <option value={0}>All teams</option>
            {data.teams.map((t) => (
              <option key={t.id} value={t.id}>
                {t.name}
              </option>
            ))}
          </select>
          <details
            className="org-export"
            onClick={(e) => {
              if ((e.target as HTMLElement).closest("button"))
                e.currentTarget.removeAttribute("open");
            }}
          >
            <summary>Export ↓</summary>
            <div>
              <button onClick={exportCSV}>People CSV</button>
              <button
                onClick={() =>
                  exportFile(
                    JSON.stringify(data.people, null, 2),
                    "organization-chart.json",
                    "application/json",
                  )
                }
              >
                People JSON
              </button>
              <button
                onClick={() =>
                  exportFile(
                    chartSVG(graph.nodes, graph.width, graph.height),
                    "organization-chart.svg",
                    "image/svg+xml",
                  )
                }
              >
                Visible chart SVG
              </button>
              <button onClick={() => window.print()}>Print / Save PDF</button>
            </div>
          </details>
        </div>
        {loading ? (
          <p role="status" className="org-empty">
            Loading organization chart…
          </p>
        ) : !wid ? (
          <p className="org-empty">
            Create or join a workspace to view its people.
          </p>
        ) : !data.people.length ? (
          <p className="org-empty">
            No active collaborators yet. Invite people to your workspace to get
            started.
          </p>
        ) : (
          <>
            <div
              className="org-viewport"
              ref={viewport}
              tabIndex={0}
              aria-label="Organization chart canvas. Scroll to pan; select a person for details."
              onPointerDown={(e) => {
                if (
                  e.pointerType !== "mouse" ||
                  e.button !== 0 ||
                  (e.target as HTMLElement).closest("button")
                )
                  return;
                const el = viewport.current!;
                pan.current = {
                  x: e.clientX,
                  y: e.clientY,
                  left: el.scrollLeft,
                  top: el.scrollTop,
                };
                el.setPointerCapture(e.pointerId);
              }}
              onPointerMove={(e) => {
                if (!pan.current || !viewport.current) return;
                viewport.current.scrollLeft =
                  pan.current.left - (e.clientX - pan.current.x);
                viewport.current.scrollTop =
                  pan.current.top - (e.clientY - pan.current.y);
              }}
              onPointerUp={() => (pan.current = null)}
              onPointerCancel={() => (pan.current = null)}
              onLostPointerCapture={() => (pan.current = null)}
            >
              <div
                style={{
                  width: graph.width * zoom,
                  height: graph.height * zoom,
                  minWidth: "100%",
                  position: "relative",
                }}
              >
                <div
                  className="org-stage"
                  style={{
                    width: graph.width,
                    height: graph.height,
                    transform: `scale(${zoom})`,
                    left: `max(0px, calc((100% - ${graph.width * zoom}px) / 2))`,
                  }}
                >
                  <svg
                    className="org-connectors"
                    width={graph.width}
                    height={graph.height}
                    aria-hidden="true"
                  >
                    {mode === "classic" &&
                      graph.nodes.map((n) => {
                        const parent = nodeMap.get(n.person.manager_id!);
                        return parent ? (
                          <path
                            key={n.person.id}
                            d={`M${parent.x + CARD_W / 2} ${parent.y + CARD_H}V${n.y - 35}H${n.x + CARD_W / 2}V${n.y}`}
                            fill="none"
                            stroke="#c4b5fd"
                            strokeWidth={2}
                          />
                        ) : null;
                      })}
                  </svg>
                  {graph.nodes.map((n) => (
                    <article
                      key={n.person.id}
                      className={
                        "org-person-card " +
                        (focus === n.person.id ? "org-focused" : "") +
                        (team && !n.person.teams.some((t) => t.id === team)
                          ? " org-ancestor"
                          : "")
                      }
                      style={{
                        left: n.x,
                        top: n.y,
                        width: CARD_W,
                        height: CARD_H,
                      }}
                    >
                      {data.can_manage && <button type="button" disabled={busy} aria-label={`Reposition ${n.person.name}`} title="Drag to arrange; arrow keys move 20 pixels" style={{position:"absolute",right:4,top:2,zIndex:2,touchAction:"none",cursor:"grab"}}
                        onPointerDown={e=>{e.stopPropagation();e.currentTarget.setPointerCapture(e.pointerId);cardDrag.current={id:n.person.id,x:e.clientX,y:e.clientY,left:n.x,top:n.y};}}
                        onPointerMove={e=>{const d=cardDrag.current;if(!d)return;setPositions(p=>({...p,[d.id]:{x:Math.max(0,Math.min(20000,d.left+(e.clientX-d.x)/zoom)),y:Math.max(0,Math.min(20000,d.top+(e.clientY-d.y)/zoom))}}));}}
                        onPointerUp={e=>{if(!cardDrag.current)return;e.currentTarget.releasePointerCapture(e.pointerId);cardDrag.current=null;void savePositions(positions);}}
                        onPointerCancel={()=>{cardDrag.current=null;setPositions(data.positions||{});}}
                        onKeyDown={e=>{if(!["ArrowLeft","ArrowRight","ArrowUp","ArrowDown"].includes(e.key))return;e.preventDefault();const next={...positions,[n.person.id]:{x:Math.max(0,Math.min(20000,n.x+(e.key==="ArrowLeft"?-20:e.key==="ArrowRight"?20:0))),y:Math.max(0,Math.min(20000,n.y+(e.key==="ArrowUp"?-20:e.key==="ArrowDown"?20:0)))}};setPositions(next);void savePositions(next);}}>⠿</button>}
                      <button
                        className="org-person-main"
                        onClick={() => openPerson(n.person)}
                        aria-label={`View ${n.person.name}`}
                      >
                        <span
                          className="org-avatar"
                          style={{
                            background: colors[n.person.id % colors.length],
                          }}
                        >
                          {initials(n.person.name)}
                        </span>
                        <span>
                          <strong>{n.person.name}</strong>
                          <small>
                            {n.person.job_title || "Job title not set"}
                          </small>
                        </span>
                      </button>
                      <div className="org-person-meta">
                        <span>
                          {n.person.teams.map((t) => t.name).join(" · ") ||
                            n.person.role}
                        </span>
                        <span>{n.children.length} reports</span>
                      </div>
                      {n.children.length > 0 && (
                        <button
                          className="org-collapse"
                          aria-label={`${collapsed.has(n.person.id) ? "Expand" : "Collapse"} reports for ${n.person.name}`}
                          aria-expanded={!collapsed.has(n.person.id)}
                          onClick={() =>
                            setCollapsed((old) => {
                              const next = new Set(old);
                              if (next.has(n.person.id))
                                next.delete(n.person.id);
                              else next.add(n.person.id);
                              return next;
                            })
                          }
                        >
                          {collapsed.has(n.person.id)
                            ? `+${n.children.length}`
                            : "−"}
                        </button>
                      )}
                    </article>
                  ))}
                </div>
              </div>
            </div>
            <footer className="org-canvas-footer">
              <div>
                <button
                  aria-label="Zoom out"
                  onClick={() => adjustZoom(zoom - 0.1)}
                >
                  −
                </button>
                <span>{Math.round(zoom * 100)}%</span>
                <button
                  aria-label="Zoom in"
                  onClick={() => adjustZoom(zoom + 0.1)}
                >
                  ＋
                </button>
                <button onClick={fit}>Fit chart</button>
              </div>
              <small>
                Drag the background or scroll to pan · Select a person to view
                details
              </small>
              <div>
                <button
                  onClick={() =>
                    setCollapsed(
                      new Set(
                        data.people
                          .filter((p) =>
                            data.people.some((c) => c.manager_id === p.id),
                          )
                          .map((p) => p.id),
                      ),
                    )
                  }
                >
                  Collapse all
                </button>
                <button onClick={() => setCollapsed(new Set())}>
                  Expand all
                </button>
              </div>
            </footer>
          </>
        )}
      </section>
      {!loading &&
        data.people.length > 0 &&
        data.people.every((p) => p.manager_id === null) && (
          <p className="org-setup-hint">
            Reporting lines have not been configured.{" "}
            {data.can_manage
              ? "Select a person and choose their manager to build your chart."
              : "Ask a workspace admin to configure your reporting lines."}
          </p>
        )}
      <Dialog.Root
        open={!!person}
        onOpenChange={(open) => {
          if (!open && !busy) setPerson(null);
        }}
      >
        <Dialog.Portal>
          <Dialog.Overlay className="org-dialog-overlay" />
          <Dialog.Content className="org-person-dialog">
            <Dialog.Title>Person & reporting line</Dialog.Title>
            <Dialog.Description>
              Reporting relationships organize this workspace. They do not grant
              access or change roles.
            </Dialog.Description>
            {person && (
              <>
                <div className="org-profile">
                  <span
                    className="org-avatar"
                    style={{ background: colors[person.id % colors.length] }}
                  >
                    {initials(person.name)}
                  </span>
                  <div>
                    <strong>{person.name}</strong>
                    <p>{person.email}</p>
                    <small>
                      {person.role} ·{" "}
                      {person.teams.map((t) => t.name).join(", ") ||
                        "No team assigned"}
                    </small>
                  </div>
                </div>
                <form
                  onSubmit={(e) => {
                    e.preventDefault();
                    void save();
                  }}
                >
                  <fieldset disabled={busy || !data.can_manage}>
                    <label>
                      Display name
                      <input
                        maxLength={120}
                        placeholder={person.name}
                        value={draft.display_name}
                        onChange={(e) =>
                          setDraft({ ...draft, display_name: e.target.value })
                        }
                      />
                    </label>
                    <label>
                      Job title
                      <input
                        maxLength={120}
                        value={draft.job_title}
                        placeholder="e.g. Operations Manager"
                        onChange={(e) =>
                          setDraft({ ...draft, job_title: e.target.value })
                        }
                      />
                    </label>
                    <label>
                      Reports to
                      <select
                        aria-label="Reports to"
                        value={draft.manager_id}
                        onChange={(e) =>
                          setDraft({ ...draft, manager_id: e.target.value })
                        }
                      >
                        <option value="">No manager / top level</option>
                        {data.people
                          .filter((p) => !invalidManager(p.id))
                          .map((p) => (
                            <option key={p.id} value={p.id}>
                              {p.name} · {p.email}
                            </option>
                          ))}
                      </select>
                    </label>
                  </fieldset>
                  <p className="org-direct-reports">
                    Direct reports:{" "}
                    {data.people
                      .filter((p) => p.manager_id === person.id)
                      .map((p) => p.name)
                      .join(", ") || "None"}
                  </p>
                  {error && (
                    <p role="alert" className="org-alert">
                      {error}
                    </p>
                  )}
                  <div className="org-dialog-actions">
                    <button
                      type="button"
                      disabled={busy}
                      onClick={() => setPerson(null)}
                    >
                      {data.can_manage ? "Cancel" : "Close"}
                    </button>
                    {data.can_manage && (
                      <button
                        className="org-primary"
                        disabled={busy}
                        type="submit"
                      >
                        {busy ? "Saving…" : "Save reporting line"}
                      </button>
                    )}
                  </div>
                </form>
              </>
            )}
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>
    </div>
  );
}
