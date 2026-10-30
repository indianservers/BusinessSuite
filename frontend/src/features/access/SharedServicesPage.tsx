import AdminVerification, { administratorStepUp } from "./AdminVerification";
import React, { useEffect, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { DndContext, useDraggable, DragEndEvent } from "@dnd-kit/core";
import {
  GitBranch,
  Plus,
  Play,
  Save,
  Upload,
  ZoomIn,
  ZoomOut,
  Move,
  X,
  Link2,
} from "lucide-react";
import { api } from "@/services/api";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";
import { useAuthStore } from "@/store/authStore";
import { canAccessRoute } from "@/lib/roles";
import { ControlNav } from "./ControlCenter";
import "./control.css";
import "./shared.css";

type Node = {
  id: string;
  type: string;
  x: number;
  y: number;
  config: Record<string, any>;
};
type Graph = {
  nodes: Node[];
  edges: { source: string; target: string; when?: string }[];
};
const empty: Graph = {
  nodes: [
    { id: "start", type: "start", x: 80, y: 160, config: {} },
    { id: "end", type: "end", x: 600, y: 160, config: {} },
  ],
  edges: [{ source: "start", target: "end" }],
};
const base = "/access/services";
const sections = [
  ["services", "Shared Services"],
  ["workflows", "Workflow Builder"],
  ["executions", "Execution History"],
  ["connections", "Connected Applications"],
  ["webhooks", "Webhooks"],
  ["ai", "AI Management"],
  ["delivery", "Delivery Logs"],
  ["documents", "Documents & Storage"],
  ["settings", "Global Settings"],
];
const message = (e: any) =>
  typeof e?.response?.data?.detail === "string"
    ? e.response.data.detail
    : JSON.stringify(e?.response?.data?.detail || e.message);

function DraggableNode({
  node,
  selected,
  choose,
  connect,
}: {
  node: Node;
  selected: boolean;
  choose: () => void;
  connect: () => void;
}) {
  const { attributes, listeners, setNodeRef, transform } = useDraggable({
    id: node.id,
  });
  return (
    <div
      ref={setNodeRef}
      className={`ss-node ${selected ? "ss-selected" : ""}`}
      style={{
        left: node.x,
        top: node.y,
        transform: transform
          ? `translate(${transform.x}px,${transform.y}px)`
          : undefined,
      }}
    >
      <button
        {...attributes}
        {...listeners}
        className="ss-node-grip"
        aria-label={`Move ${node.id}`}
      >
        <Move size={13} />
      </button>
      <button className="ss-node-label" onClick={choose}>
        {node.type.replace(/_/g, " ")}
        <small>{node.id}</small>
      </button>
      <button
        onClick={connect}
        className="ss-port"
        aria-label={`Connect ${node.id}`}
      >
        <Link2 size={13} />
      </button>
    </div>
  );
}

export default function SharedServicesPage() {
  const actor = useAuthStore((s) => s.user);
  const section = useLocation().pathname.split("/").pop() || "services";
  const [company, setCompany] = useState(
    Number(
      sessionStorage.getItem("suite-organization") ||
        actor?.access?.companyId ||
        1,
    ),
  );
  const [catalog, setCatalog] = useState<any>();
  const [organizations, setOrganizations] = useState<any[]>([]);
  const [users, setUsers] = useState<any[]>([]);
  const [result, setData] = useState<any>();
  const [dataKey,setDataKey]=useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [loading, setLoading] = useState(false);
  const [revision, setRevision] = useState(0);
  const [definition, setDefinition] = useState<any>();
  const [graph, setGraph] = useState<Graph>(structuredClone(empty));
  const [name, setName] = useState("");
  const [module, setModule] = useState("crm");
  const [entity, setEntity] = useState("lead");
  const [event, setEvent] = useState("record.created");
  const [identity, setIdentity] = useState("");
  const [selected, setSelected] = useState<string>();
  const [connection, setConnection] = useState<string>();
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [panning, setPanning] = useState(false);
  const [dirty, setDirty] = useState(false);
  const [configText, setConfigText] = useState("{}");
  const [command, setCommand] = useState<any>();
  const [reason, setReason] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [settingText, setSettingText] = useState("{}");
  const [settingsScope,setSettingsScope]=useState("company");
  const [settingsModule,setSettingsModule]=useState("crm");
  const [webhookForm,setWebhookForm]=useState({name:"",module:"crm",entity:"lead",events:"webhook.received",runAsUserId:"",secret:""});
  const [connectionForm, setConnectionForm] = useState({
    name: "",
    provider: "Signed HTTPS",
    modules: "crm",
    operations:
      '{"notify":{"url":"https://example.com/hook","fields":["recordId"]}}',
    secret: "",
  });
  const [inspect, setInspect] = useState<any>();
  const [file, setFile] = useState<File>();
  const [documentEntityId, setDocumentEntityId] = useState("");
  const [folder, setFolder] = useState("/");
  const keyForData=`${section}:${company}:${section==="settings"?settingsScope+":"+settingsModule:""}`;
  const data=dataKey===keyForData?result:undefined;
  const admin = actor?.is_superuser || actor?.access?.isAccessAdmin;
  const load = () => setRevision((x) => x + 1);
  useEffect(() => {
    if (!admin) return;
    let active = true;
    setLoading(true);
    setError("");
    const endpoint = section === "services" ? "overview" : section;
    Promise.all([
      api.get(`${base}/catalog`, { params: { companyId: company } }),
      api.get("/access/control/organizations"),
      api.get("/access/users", {
        params: { companyId: company, perPage: 200 },
      }),
      api.get(`${base}/${endpoint}`, { params: { companyId: company, ...(section==="settings"?{platform:settingsScope==="platform",module:settingsScope==="module"?settingsModule:"*"}:{}) } }),
    ])
      .then(([c, o, u, d]) => {
        if (active) {
          setCatalog(c.data);
          setOrganizations(o.data);
          setUsers(u.data.items);
          setData(d.data);
          setDataKey(keyForData);
          if (section === "settings")
            setSettingText(
              JSON.stringify(d.data.override?.values_json || {}, null, 2),
            );
        }
      })
      .catch((e) => active && setError(message(e)))
      .finally(() => active && setLoading(false));
    return () => {
      active = false;
    };
  }, [section, company, revision, admin,settingsScope,settingsModule]);
  useEffect(() => {
    const protect = (e: BeforeUnloadEvent) => {
      if (dirty) {
        e.preventDefault();
        e.returnValue = "";
      }
    };
    window.addEventListener("beforeunload", protect);
    return () => window.removeEventListener("beforeunload", protect);
  }, [dirty]);
  if (!admin) return <p role="alert">Access administrator required.</p>;
  const stage = (action: any) => {
    setCommand(action);
    setReason("");
    setPassword("");
    setError("");
  };
  const confirm = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    try {
      const token = (await administratorStepUp(password)).data
        .token;
      const body = command.body ? command.body() : {};
      const result = await api.request({
        method: command.method || "post",
        url: command.url,
        data: { ...body, companyId: company, reason },
        headers: { "X-Access-Step-Up": token },
      });
      if (command.saved) {
        setDefinition(result.data);
        setDirty(false);
      }
      setNotice(command.success || "Change saved.");
      setCommand(undefined);
      setPassword("");
      setConnectionForm((v) => ({ ...v, secret: "" }));
      setWebhookForm(v=>({...v,secret:""}));
      load();
    } catch (e) {
      setError(message(e));
    } finally {
      setBusy(false);
    }
  };
  const openWorkflow = (row?: any) => {
    if (dirty && !window.confirm("Discard the unsaved workflow draft?")) return;
    setDefinition(row);
    setGraph(structuredClone(row?.graph_json || empty));
    setName(row?.name || "");
    setModule(row?.module_name || "crm");
    setEntity(row?.record_type || "lead");
    setEvent(row?.trigger_type || "record.created");
    setIdentity(String(row?.run_as_user_id || ""));
    setSelected(undefined);
    setDirty(false);
  };
  const editGraph = (g: Graph) => {
    setGraph(g);
    setDirty(true);
  };
  const add = (type: string) => {
    const id = `${type}_${Date.now().toString(36)}`;
    editGraph({
      ...graph,
      nodes: [
        ...graph.nodes,
        {
          id,
          type,
          x: 200 + (graph.nodes.length % 4) * 180,
          y: 80 + Math.floor(graph.nodes.length / 4) * 110,
          config:
            type === "delay"
              ? { seconds: 60 }
              : type === "condition"
                ? {
                    condition: {
                      field: "status",
                      operator: "equals",
                      value: "Approved",
                    },
                  }
                : {},
        },
      ],
    });
    setSelected(id);
    setConfigText("{}");
  };
  const connect = (id: string) => {
    if (!connection) {
      setConnection(id);
      return;
    }
    if (connection === id) {
      setConnection(undefined);
      return;
    }
    editGraph({
      ...graph,
      edges: [...graph.edges, { source: connection, target: id }],
    });
    setConnection(undefined);
  };
  const drag = (e: DragEndEvent) => {
    editGraph({
      ...graph,
      nodes: graph.nodes.map((n) =>
        n.id === e.active.id
          ? {
              ...n,
              x: Math.max(0, n.x + e.delta.x / zoom),
              y: Math.max(0, n.y + e.delta.y / zoom),
            }
          : n,
      ),
    });
  };
  const save = () =>
    stage({
      title: "Save workflow draft",
      url: `${base}/workflows${definition ? "/" + definition.id : ""}`,
      method: definition ? "put" : "post",
      saved: true,
      body: () => ({
        name,
        module,
        entity,
        event,
        runAsUserId: Number(identity),
        graph,
        version: definition?.draft_version || 0,
      }),
    });
  const selectedNode = graph.nodes.find((n) => n.id === selected);
  const configField = (key: string, label: string, type = "text") => (
    <label className="cc-field">
      {label}
      <input
        type={type}
        value={selectedNode?.config[key] ?? ""}
        onChange={(e) =>
          editGraph({
            ...graph,
            nodes: graph.nodes.map((n) =>
              n.id === selected
                ? {
                    ...n,
                    config: {
                      ...n.config,
                      [key]:
                        type === "number"
                          ? Number(e.target.value)
                          : e.target.value,
                    },
                  }
                : n,
            ),
          })
        }
      />
    </label>
  );
  return (
    <main className="ua-root cc-root ss-root">
      <div className="cc-heading">
        <div>
          <p className="cc-eyebrow">MASTER SUITE / CENTRAL SHARED SERVICES</p>
          <h1>
            <GitBranch size={22} />
            {sections.find((s) => s[0] === section)?.[1] || "Shared Services"}
          </h1>
        </div>
        <Button variant="outline" onClick={load}>
          Refresh
        </Button>
      </div>
      <ControlNav />
      <nav className="cc-nav" aria-label="Shared services">
        {sections.map(([key, label]) => (
          <Link
            key={key}
            to={`/admin/control/services/${key}`}
            aria-current={section === key ? "page" : undefined}
          >
            {label}
          </Link>
        ))}
      </nav>
      <label className="cc-company">
        Company
        <select
          value={company}
          aria-label="Shared service company"
          onChange={(e) => {
            if (
              dirty &&
              !window.confirm("Discard unsaved changes and switch company?")
            )
              return;
            setCompany(Number(e.target.value));
            setDefinition(undefined);
            setDirty(false);
          }}
        >
          {organizations.map((o) => (
            <option key={o.id} value={o.id}>
              {o.name}
            </option>
          ))}
        </select>
      </label>
      {error && (
        <p role="alert" className="cc-error">
          {error}
        </p>
      )}
      {notice && <p role="status">{notice}</p>}
      {loading && (
        <div className="cc-skeleton" aria-label="Loading shared services" />
      )}
      {data && section === "services" && (
        <>
          <div className="cc-stats">
            <section className="cc-card">
              <span>Versioned workflows</span>
              <strong>{data.workflows}</strong>
            </section>
            <section className="cc-card">
              <span>Pending events</span>
              <strong>{data.pendingEvents}</strong>
            </section>
            <section className="cc-card">
              <span>Registered modules</span>
              <strong>{catalog?.modules.length}</strong>
            </section>
            <section className="cc-card">
              <span>Execution history shown</span>
              <strong>{data.executions.length}</strong>
            </section>
          </div>
          <section className="cc-card">
            <h2>Existing shared administration</h2>
            <div className="cc-actions">
              {catalog?.navigation
                .filter((n: any) =>
                  canAccessRoute(n.route, actor?.role, actor?.is_superuser),
                )
                .map((n: any) => (
                  <Link key={n.route} to={n.route}>
                    {n.label}
                  </Link>
                ))}
            </div>
          </section>
          <section className="cc-card">
            <h2>Module service contracts</h2>
            <div className="cc-scroll">
              <table>
                <thead>
                  <tr>
                    <th>Module</th>
                    <th>Shared capabilities</th>
                    <th>Record integration</th>
                  </tr>
                </thead>
                <tbody>
                  {catalog?.modules.map((m: any) => (
                    <tr key={m.key}>
                      <td>
                        {m.label}
                        <small>{m.key}</small>
                      </td>
                      <td>{m.services.join(", ")}</td>
                      <td>
                        {m.recordIntegration}
                        <small>
                          {m.records.map((r: any) => r.entity).join(", ")}
                        </small>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
          <section className="cc-card">
            <h2>Channel readiness</h2>
            {data.providers.map((p: any) => (
              <p key={p.channel}>
                {p.channel}: <strong>{p.status}</strong>{" "}
                {p.deliverySemantics && `· ${p.deliverySemantics}`}
              </p>
            ))}
          </section>
        </>
      )}
      {section === "workflows" && (
        <>
          <div className="cc-actions">
            <select
              aria-label="Select workflow"
              value={definition?.id || ""}
              onChange={(e) =>
                openWorkflow(
                  data?.find((w: any) => w.id === Number(e.target.value)),
                )
              }
            >
              <option value="">New workflow</option>
              {Array.isArray(data) &&
                data.map((w: any) => (
                  <option key={w.id} value={w.id}>
                    {w.name} · draft {w.draft_version}
                    {w.published_version
                      ? ` / published ${w.published_version}`
                      : ""}
                  </option>
                ))}
            </select>
            <Button variant="outline" onClick={() => openWorkflow()}>
              New
            </Button>
            <Button
              variant="outline"
              disabled={!definition}
              onClick={() => {
                setDefinition(undefined);
                setName((n) => n + " (copy)");
                setDirty(true);
              }}
            >
              Duplicate
            </Button>
            <Button onClick={save} disabled={!name.trim() || !identity}>
              <Save size={14} />
              Save Draft
            </Button>
            <Button
              variant="outline"
              disabled={!definition || dirty}
              onClick={() =>
                stage({
                  title: "Publish immutable workflow version",
                  url: `${base}/workflows/${definition.id}/publish`,
                  body: () => ({ version: definition.draft_version }),
                })
              }
            >
              Publish
            </Button>
            <Button
              variant="outline"
              onClick={async () => {
                try {
                  const r = await api.post(`${base}/graph/validate`, graph);
                  setNotice(r.data.message);
                } catch (e) {
                  setError(message(e));
                }
              }}
            >
              Validate Preview
            </Button>
            <Button
              variant="outline"
              disabled={!definition}
              onClick={async () => {
                try {
                  setInspect(
                    (
                      await api.get(
                        `${base}/workflows/${definition.id}/versions`,
                        { params: { companyId: company } },
                      )
                    ).data,
                  );
                } catch (e) {
                  setError(message(e));
                }
              }}
            >
              Versions
            </Button>
            {dirty && <span>Unsaved changes</span>}
          </div>
          <div className="ss-workflow-meta">
            <label>
              Name
              <input
                value={name}
                onChange={(e) => {
                  setName(e.target.value);
                  setDirty(true);
                }}
              />
            </label>
            <label>
              Module
              <select
                disabled={!!definition}
                value={module}
                onChange={(e) => {
                  setModule(e.target.value);
                  setDirty(true);
                }}
              >
                {catalog?.modules
                  .filter((m: any) => m.installed)
                  .map((m: any) => (
                    <option key={m.key} value={m.key}>
                      {m.label}
                    </option>
                  ))}
              </select>
            </label>
            <label>
              Entity
              <input
                disabled={!!definition}
                value={entity}
                onChange={(e) => {
                  setEntity(e.target.value);
                  setDirty(true);
                }}
              />
            </label>
            <label>
              Event
              <select
                disabled={!!definition}
                value={event}
                onChange={(e) => {
                  setEvent(e.target.value);
                  setDirty(true);
                }}
              >
                {[
                  "record.created",
                  "record.updated",
                  "status.changed",
                  "record.assigned",
                  "task.completed",
                  "invoice.issued",
                  "payment.received",
                  "lead.converted",
                  "intern.submitted",
                  "approval.completed",
                  "form.submitted",
                  "scheduled",
                  "webhook.received",
                ].map((v) => (
                  <option key={v}>{v}</option>
                ))}
              </select>
            </label>
            <label>
              Execution identity
              <select
                aria-label="Execution identity"
                value={identity}
                onChange={(e) => {
                  setIdentity(e.target.value);
                  setDirty(true);
                }}
              >
                <option value="">Choose managed non-superuser</option>
                {users
                  .filter(
                    (u) => u.managed && !u.isSuperuser && u.status === "active",
                  )
                  .map((u) => (
                    <option value={u.id} key={u.id}>
                      {u.name} · {u.email}
                    </option>
                  ))}
              </select>
            </label>
          </div>
          <div className="ss-editor">
            <aside className="ss-palette">
              <h3>Add node</h3>
              {catalog?.nodes.map((type: string) => (
                <button key={type} onClick={() => add(type)}>
                  <Plus size={12} />
                  {type.replace(/_/g, " ")}
                </button>
              ))}
            </aside>
            <section className="ss-canvas-shell">
              <div className="ss-canvas-tools">
                <Button
                  variant="outline"
                  aria-label="Zoom in"
                  onClick={() => setZoom((v) => Math.min(2, v + 0.1))}
                >
                  <ZoomIn size={15} />
                </Button>
                <span>{Math.round(zoom * 100)}%</span>
                <Button
                  variant="outline"
                  aria-label="Zoom out"
                  onClick={() => setZoom((v) => Math.max(0.35, v - 0.1))}
                >
                  <ZoomOut size={15} />
                </Button>
                <Button
                  variant="outline"
                  aria-pressed={panning}
                  onClick={() => setPanning((v) => !v)}
                >
                  <Move size={15} />
                  Pan
                </Button>
                <span>
                  {connection
                    ? `Choose target for ${connection}`
                    : "Select a link handle to connect nodes"}
                </span>
              </div>
              <div
                className="ss-viewport"
                onPointerDown={(e) => {
                  if (panning) {
                    e.currentTarget.setPointerCapture(e.pointerId);
                    (e.currentTarget as any)._pan = {
                      x: e.clientX,
                      y: e.clientY,
                      initial: pan,
                    };
                  }
                }}
                onPointerMove={(e) => {
                  const p = (e.currentTarget as any)._pan;
                  if (p)
                    setPan({
                      x: p.initial.x + e.clientX - p.x,
                      y: p.initial.y + e.clientY - p.y,
                    });
                }}
                onPointerUp={(e) => {
                  (e.currentTarget as any)._pan = undefined;
                }}
              >
                <DndContext onDragEnd={drag}>
                  <div
                    className="ss-world"
                    style={{
                      transform: `translate(${pan.x}px,${pan.y}px) scale(${zoom})`,
                    }}
                  >
                    <svg className="ss-edges" width="2400" height="1800">
                      <defs>
                        <marker
                          id="arrow"
                          markerWidth="8"
                          markerHeight="8"
                          refX="7"
                          refY="4"
                          orient="auto"
                        >
                          <path d="M0,0 L8,4 L0,8" fill="currentColor" />
                        </marker>
                      </defs>
                      {graph.edges.map((edge, i) => {
                        const a = graph.nodes.find((n) => n.id === edge.source),
                          b = graph.nodes.find((n) => n.id === edge.target);
                        if (!a || !b) return null;
                        return (
                          <g
                            key={i}
                            onClick={() => {
                              if (window.confirm("Remove this connection?"))
                                editGraph({
                                  ...graph,
                                  edges: graph.edges.filter((_, j) => j !== i),
                                });
                            }}
                          >
                            <path
                              d={`M${a.x + 170},${a.y + 30} C${a.x + 240},${a.y + 30} ${b.x - 70},${b.y + 30} ${b.x},${b.y + 30}`}
                              fill="none"
                              stroke="currentColor"
                              strokeWidth="2"
                              markerEnd="url(#arrow)"
                            />
                            <text
                              x={(a.x + b.x + 170) / 2}
                              y={(a.y + b.y) / 2 + 18}
                            >
                              {edge.when || ""}
                            </text>
                          </g>
                        );
                      })}
                    </svg>
                    {graph.nodes.map((node) => (
                      <DraggableNode
                        key={node.id}
                        node={node}
                        selected={selected === node.id}
                        choose={() => {
                          setSelected(node.id);
                          setConfigText(JSON.stringify(node.config, null, 2));
                        }}
                        connect={() => connect(node.id)}
                      />
                    ))}
                  </div>
                </DndContext>
              </div>
            </section>
            <aside className="ss-config">
              <h3>
                {selectedNode
                  ? selectedNode.type.replace(/_/g, " ")
                  : "Node configuration"}
              </h3>
              {selectedNode ? (
                <>
                  {["notification", "escalation"].includes(
                    selectedNode.type,
                  ) && (
                    <>
                      {configField("title", "Title")}
                      {configField("message", "Message")}
                      {configField(
                        "recipientId",
                        "Authorized recipient ID",
                        "number",
                      )}
                    </>
                  )}
                  {selectedNode.type === "delay" &&
                    configField("seconds", "Delay seconds", "number")}
                  {selectedNode.type === "wait_event" &&
                    configField("event", "Event name")}
                  {["create_record", "update_record", "assignment"].includes(
                    selectedNode.type,
                  ) && (
                    <>
                      <label className="cc-field">
                        Approved action
                        <select
                          value={selectedNode.config.tool || ""}
                          onChange={(e) =>
                            editGraph({
                              ...graph,
                              nodes: graph.nodes.map((n) =>
                                n.id === selected
                                  ? {
                                      ...n,
                                      config: {
                                        ...n.config,
                                        tool: e.target.value,
                                      },
                                    }
                                  : n,
                              ),
                            })
                          }
                        >
                          <option value="">Choose action</option>
                          {catalog?.tools.map((t: any) => (
                            <option value={t.name} key={t.name}>
                              {t.name}
                            </option>
                          ))}
                        </select>
                      </label>
                      {configField(
                        "recordId",
                        "Target ID (defaults to event record)",
                        "number",
                      )}
                    </>
                  )}
                  <label className="cc-field">
                    Configuration JSON
                    <textarea
                      aria-label="Node configuration JSON"
                      rows={12}
                      value={configText}
                      onChange={(e) => setConfigText(e.target.value)}
                    />
                  </label>
                  <Button
                    variant="outline"
                    onClick={() => {
                      try {
                        const parsed = JSON.parse(configText);
                        if (
                          typeof parsed !== "object" ||
                          Array.isArray(parsed) ||
                          !parsed
                        )
                          throw new Error("Use a JSON object");
                        editGraph({
                          ...graph,
                          nodes: graph.nodes.map((n) =>
                            n.id === selected ? { ...n, config: parsed } : n,
                          ),
                        });
                        setNotice("Node configuration applied to the draft.");
                      } catch (e) {
                        setError(message(e));
                      }
                    }}
                  >
                    Apply Configuration
                  </Button>
                  {selectedNode.type === "approval" && (
                    <p>
                      Use approvers as user IDs and mode: all, any or
                      sequential. Self approval is blocked.
                    </p>
                  )}
                  {selectedNode.type === "condition" && (
                    <p>
                      Use condition with field/operator/value, or nested all/any
                      groups. Label outgoing edges true/false.
                    </p>
                  )}
                  <h4>Outgoing connections</h4>
                  {graph.edges.map(
                    (edge, i) =>
                      edge.source === selected && (
                        <label className="cc-field" key={i}>
                          {edge.target}
                          <select
                            value={edge.when || ""}
                            onChange={(e) =>
                              editGraph({
                                ...graph,
                                edges: graph.edges.map((x, j) =>
                                  j === i
                                    ? {
                                        ...x,
                                        when: e.target.value || undefined,
                                      }
                                    : x,
                                ),
                              })
                            }
                          >
                            <option value="">Always</option>
                            <option value="true">True</option>
                            <option value="false">False</option>
                          </select>
                        </label>
                      ),
                  )}
                  <Button
                    variant="outline"
                    onClick={() => {
                      editGraph({
                        nodes: graph.nodes.filter((n) => n.id !== selected),
                        edges: graph.edges.filter(
                          (e) => e.source !== selected && e.target !== selected,
                        ),
                      });
                      setSelected(undefined);
                    }}
                  >
                    Remove Node
                  </Button>
                </>
              ) : (
                <p>
                  Select a node to edit its configuration. Published versions
                  remain unchanged while you edit a draft.
                </p>
              )}
            </aside>
          </div>
        </>
      )}
      {data && section === "executions" && (
        <section className="cc-card">
          {actor?.is_superuser && (
            <Button
              variant="outline"
              onClick={() =>
                stage({
                  title: "Process a bounded worker batch",
                  url: `${base}/worker/tick`,
                })
              }
            >
              <Play size={14} />
              Process Queue
            </Button>
          )}
          <div className="cc-scroll">
            <table>
              <thead>
                <tr>
                  <th>Execution</th>
                  <th>Source</th>
                  <th>Status</th>
                  <th>Progress</th>
                  <th>Diagnostics</th>
                  <th>Controls</th>
                </tr>
              </thead>
              <tbody>
                {data.map((j: any) => (
                  <tr key={j.id}>
                    <td>#{j.id}</td>
                    <td>
                      {j.module_name} · {j.record_type} #{j.record_id}
                    </td>
                    <td>{j.status}</td>
                    <td>
                      {j.payload_json?.steps || 0} steps · {j.attempts} retries
                    </td>
                    <td>
                      {j.last_error || "No error"}
                      <Button variant="ghost" onClick={() => setInspect(j)}>
                        Inspect
                      </Button>
                    </td>
                    <td>
                      {(j.status === "scheduled"
                        ? ["pause", "cancel"]
                        : j.status === "paused"
                          ? ["resume", "cancel"]
                          : j.status === "dead_letter"
                            ? ["retry", "cancel"]
                            : []
                      ).map((op) => (
                        <Button
                          variant="outline"
                          key={op}
                          onClick={() =>
                            stage({
                              title: `${op} execution #${j.id}`,
                              url: `${base}/executions/${j.id}/${op}`,
                            })
                          }
                        >
                          {op}
                        </Button>
                      ))}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {!data.length && (
              <p className="cc-empty">
                No executions. Publish a workflow and emit an authorized
                matching event.
              </p>
            )}
          </div>
        </section>
      )}
      {data && section === "connections" && (
        <>
          <section className="cc-card">
            <h2>Company connections</h2>
            {data.map((c: any) => (
              <div className="cc-branch" key={c.id}>
                <strong>{c.name}</strong>
                <p>
                  {c.provider} · {c.status} · {c.verification} ·{" "}
                  {c.modules?.join(", ")}
                </p>
                <p>Approved operations: {c.operations.join(", ")}</p>
                <Button
                  variant="outline"
                  disabled={c.status === "Revoked"}
                  onClick={() =>
                    stage({
                      title: `Revoke ${c.name}`,
                      url: `${base}/connections/${c.id}/revoke`,
                    })
                  }
                >
                  Revoke
                </Button>
              </div>
            ))}
            {!data.length && <p>No approved connections for this company.</p>}
          </section>
          {actor?.is_superuser && (
            <section className="cc-card">
              <h2>Add signed HTTPS connection</h2>
              <div className="cc-form-grid">
                {["name", "provider", "modules"].map((key) => (
                  <label className="cc-field" key={key}>
                    {key}
                    <input
                      value={(connectionForm as any)[key]}
                      onChange={(e) =>
                        setConnectionForm((v) => ({
                          ...v,
                          [key]: e.target.value,
                        }))
                      }
                    />
                  </label>
                ))}
                <label className="cc-field">
                  Signing secret
                  <input
                    type="password"
                    autoComplete="new-password"
                    value={connectionForm.secret}
                    onChange={(e) =>
                      setConnectionForm((v) => ({
                        ...v,
                        secret: e.target.value,
                      }))
                    }
                  />
                </label>
              </div>
              <label className="cc-field">
                Approved operations (fixed URLs and field allowlists)
                <textarea
                  rows={5}
                  value={connectionForm.operations}
                  onChange={(e) =>
                    setConnectionForm((v) => ({
                      ...v,
                      operations: e.target.value,
                    }))
                  }
                />
              </label>
              <Button
                onClick={() =>
                  stage({
                    title: "Approve connection destinations",
                    url: `${base}/connections`,
                    body: () => ({
                      ...connectionForm,
                      modules: connectionForm.modules
                        .split(",")
                        .map((s) => s.trim())
                        .filter(Boolean),
                      operations: JSON.parse(connectionForm.operations),
                    }),
                  })
                }
              >
                Review & Add Connection
              </Button>
              <p>
                Credentials are encrypted. A configured connection remains
                unverified until an actual provider operation succeeds.
              </p>
            </section>
          )}
        </>
      )}
      {data && section === "webhooks" && <><section className="cc-card"><h2>Signed inbound subscriptions</h2>{data.map((w:any)=><div className="cc-branch" key={w.id}><strong>{w.name}</strong><p>{w.subscription.module} � {w.subscription.entity} � {w.active?"Active":"Disabled"}</p><code>{w.path}</code><p>Events: {w.subscription.events.join(", ")}</p></div>)}{!data.length&&<p>No inbound subscriptions.</p>}</section>{actor?.is_superuser&&<section className="cc-card"><h2>Register signed webhook</h2><div className="cc-form-grid">{["name","module","entity","events","runAsUserId","secret"].map(key=><label className="cc-field" key={key}>{key}<input type={key==="secret"?"password":key==="runAsUserId"?"number":"text"} value={(webhookForm as any)[key]} onChange={e=>setWebhookForm(v=>({...v,[key]:e.target.value}))}/></label>)}</div><Button onClick={()=>stage({title:"Approve signed webhook subscription",url:`${base}/webhooks`,body:()=>({...webhookForm,events:webhookForm.events.split(",").map(x=>x.trim()),runAsUserId:Number(webhookForm.runAsUserId)})})}>Review & Register</Button><p>Sign timestamp + a dot + the raw JSON body using HMAC-SHA256. Send X-Suite-Timestamp and X-Suite-Signature. Event IDs are replay-protected and timestamps expire after five minutes.</p></section>}</>}
      {data && section === "ai" && <><section className="cc-card"><h2>Company model registry</h2>{data.providers.map((p:any)=><p key={p.provider}>{p.provider} � {p.model} � {p.status} � Data sharing {p.dataSharingAllowed?"enabled":"disabled"}</p>)}{!data.providers.length&&<p>No company conversational providers configured.</p>}<div className="cc-actions">{[["/ai/provider-settings","Provider configuration"],["/ai-agents/config","Agent & tool configuration"],["/ai-agents/usage","Usage & budgets"]].filter(([path])=>canAccessRoute(path,actor?.role,actor?.is_superuser)).map(([path,label])=><Link key={path} to={path}>{label}</Link>)}</div><p>{data.localModels}</p></section><section className="cc-card"><h2>Approved AI tool registry</h2><div className="cc-scroll"><table><thead><tr><th>Tool</th><th>Module</th><th>Native permission</th><th>Risk</th><th>Approval</th><th>Schema</th></tr></thead><tbody>{data.tools.map((t:any)=><tr key={t.id}><td>{t.id}<small>{t.description}</small></td><td>{t.module}</td><td>{t.requiredPermission||"Existing record authorization"}</td><td>{t.risk}</td><td>{t.humanApprovalRequired?"Required":"Read / draft"}</td><td><Button variant="ghost" onClick={()=>setInspect(t)}>Inspect</Button></td></tr>)}</tbody></table></div></section><section className="cc-card"><h2>Recorded usage</h2><p>{data.costSemantics}</p><div className="cc-scroll"><table><thead><tr><th>Module</th><th>User</th><th>Event</th><th>Input / output tokens</th><th>Estimated cost</th></tr></thead><tbody>{data.usage.map((u:any)=><tr key={u.id}><td>{u.module}</td><td>#{u.userId}</td><td>{u.type}</td><td>{u.inputTokens} / {u.outputTokens}</td><td>{u.estimatedCost??"Unavailable"}</td></tr>)}</tbody></table></div></section></>}
      {data && section === "delivery" && (
        <section className="cc-card">
          <div className="cc-scroll">
            <table>
              <thead>
                <tr>
                  <th>Notification</th>
                  <th>Module</th>
                  <th>Recipient</th>
                  <th>Channel</th>
                  <th>Status</th>
                  <th>Diagnostics</th>
                </tr>
              </thead>
              <tbody>
                {data.map((d: any) => (
                  <tr key={d.id}>
                    <td>#{d.notificationId}</td>
                    <td>{d.module}</td>
                    <td>User #{d.userId}</td>
                    <td>{d.channel}</td>
                    <td>{d.status}</td>
                    <td>{d.error || "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {!data.length && <p>No delivery records for this company.</p>}
          </div>
          <p>
            External delivery is confirmed only by a verified provider callback.
            In-app delivery means the authorized inbox record exists.
          </p>
        </section>
      )}
      {data && section === "documents" && (
        <>
          <section className="cc-card">
            <h2>Upload to an authorized record</h2>
            <div className="cc-form-grid">
              <label className="cc-field">
                Module
                <select
                  value={module}
                  onChange={(e) => setModule(e.target.value)}
                >
                  {catalog?.modules
                    .filter((m: any) => m.installed)
                    .map((m: any) => (
                      <option value={m.key} key={m.key}>
                        {m.label}
                      </option>
                    ))}
                </select>
              </label>
              <label className="cc-field">
                Entity
                <input
                  value={entity}
                  onChange={(e) => setEntity(e.target.value)}
                />
              </label>
              <label className="cc-field">
                Record ID
                <input
                  type="number"
                  value={documentEntityId}
                  onChange={(e) => setDocumentEntityId(e.target.value)}
                />
              </label>
              <label className="cc-field">
                Folder
                <input
                  value={folder}
                  onChange={(e) => setFolder(e.target.value)}
                />
              </label>
              <label className="cc-field">
                File (PDF, PNG, JPEG)
                <input
                  type="file"
                  accept=".pdf,.png,.jpg,.jpeg"
                  onChange={(e) => setFile(e.target.files?.[0])}
                />
              </label>
            </div>
            <Button
              disabled={!file || !documentEntityId}
              onClick={async () => {
                try {
                  const form = new FormData();
                  form.append("companyId", String(company));
                  form.append("module", module);
                  form.append("entity", entity);
                  form.append("entityId", documentEntityId);
                  form.append("folder", folder);
                  form.append("file", file!);
                  await api.post(`${base}/documents`, form);
                  setNotice("Document stored with record authorization.");
                  load();
                } catch (e) {
                  setError(message(e));
                }
              }}
            >
              <Upload size={14} />
              Upload
            </Button>
          </section>
          <section className="cc-card">
            <div className="cc-scroll">
              <table>
                <thead>
                  <tr>
                    <th>Document</th>
                    <th>Record</th>
                    <th>Version</th>
                    <th>Folder</th>
                    <th>Size</th>
                    <th>Download</th>
                  </tr>
                </thead>
                <tbody>
                  {data.map((d: any) => (
                    <tr key={d.id}>
                      <td>{d.name}</td>
                      <td>
                        {d.module_key} {d.entity_type} #{d.entity_id}
                      </td>
                      <td>{d.version}</td>
                      <td>{d.folder}</td>
                      <td>{d.size_bytes} bytes</td>
                      <td>
                        <Button
                          variant="outline"
                          onClick={async () => {
                            try {
                              const response = await api.get(
                                `${base}/documents/${d.id}/download`,
                                { responseType: "blob" },
                              );
                              const url = URL.createObjectURL(response.data);
                              const a = document.createElement("a");
                              a.href = url;
                              a.download = d.name;
                              a.click();
                              setTimeout(() => URL.revokeObjectURL(url), 500);
                            } catch (e) {
                              setError(message(e));
                            }
                          }}
                        >
                          Download
                        </Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p>
              Only documents whose source record is currently authorized are
              listed.
            </p>
          </section>
        </>
      )}
      {data && section === "settings" && (
        <div className="cc-charts">
          <section className="cc-card">
            <h2>Shared configuration overrides</h2><label className="cc-field">Configuration level<select value={settingsScope} onChange={e=>setSettingsScope(e.target.value)}>{actor?.is_superuser&&<option value="platform">Platform policy</option>}<option value="company">Company configuration</option><option value="module">Module configuration</option></select></label>{settingsScope==="module"&&<label className="cc-field">Module<select value={settingsModule} onChange={e=>setSettingsModule(e.target.value)}>{catalog?.modules.filter((m:any)=>m.installed).map((m:any)=><option key={m.key} value={m.key}>{m.label}</option>)}</select></label>}
            <label className="cc-field">
              Validated shared settings
              <textarea
                rows={18}
                value={settingText}
                onChange={(e) => setSettingText(e.target.value)}
              />
            </label>
            <Button
              onClick={() =>
                stage({
                  title: "Save company settings",
                  url: `${base}/settings`,
                  method: "put",
                  body: () => ({
                    module: settingsScope==="module"?settingsModule:"*",
                    platform:settingsScope==="platform",
                    version: data.override?.version || 0,
                    values: JSON.parse(settingText),
                  }),
                })
              }
            >
              Review & Save
            </Button>
          </section>
          <section className="cc-card">
            <h2>Effective settings</h2>
            <pre className="ss-json">
              {JSON.stringify(data.effective, null, 2)}
            </pre>
            <p>
              Lower layers cannot weaken mandatory security settings or increase
              platform limits. Country metadata does not change tax
              calculations.
            </p>
          </section>
        </div>
      )}
      <Dialog
        open={!!command}
        onOpenChange={(v) => {
          if (!v && !busy) {
            setCommand(undefined);
            setPassword("");
          }
        }}
      >
        <DialogContent className="ua-root cc-dialog">
          <DialogTitle>{command?.title || "Review change"}</DialogTitle>
          <form onSubmit={confirm}>
            <p>
              Company:{" "}
              {organizations.find((o) => o.id === company)?.name || company}
            </p>
            <label className="cc-field">
              Reason
              <textarea
                required
                minLength={3}
                maxLength={500}
                value={reason}
                onChange={(e) => setReason(e.target.value)}
              />
            </label>
            <AdminVerification value={password} onChange={setPassword} />
            {error && <p role="alert">{error}</p>}
            <Button disabled={busy} type="submit">
              {busy ? "Saving…" : "Verify & Apply"}
            </Button>
          </form>
        </DialogContent>
      </Dialog>
      <Dialog
        open={!!inspect}
        onOpenChange={(v) => !v && setInspect(undefined)}
      >
        <DialogContent className="ua-root cc-dialog">
          <DialogTitle>Version / execution details</DialogTitle>
          <pre className="ss-json">{JSON.stringify(inspect, null, 2)}</pre>
        </DialogContent>
      </Dialog>
    </main>
  );
}
