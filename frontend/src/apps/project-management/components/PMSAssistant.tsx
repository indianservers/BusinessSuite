import { useEffect, useRef, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import {
  ArrowUp,
  Check,
  ChevronDown,
  Expand,
  History,
  Loader2,
  Mic,
  Plus,
  Settings,
  Sparkles,
  X,
} from "lucide-react";
import { assistantStream } from "@/services/pmsAssistantStream";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/services/api";
import { useAuthStore } from "@/store/authStore";
import "./PMSAssistant.css";

type Row = Record<string, any>;
const root = "/ai-operator/assistant";
const suggestions = [
  "Create an Invoice",
  "Create a Project",
  "Assign Tasks",
  "Generate Reports",
  "Check Overdue Work",
  "Summarize My Projects",
  "Find Customer",
  "Plan My Day",
];
const textError = (e: any) =>
  typeof e?.response?.data?.detail === "string"
    ? e.response.data.detail
    : "The request could not finish. Your draft is preserved; please retry.";

export default function PMSAssistant() {
  const uid = useAuthStore((s) => s.user?.id);
  const location = useLocation();
  const standardModule = ["/pms", "/crm", "/srm"].some(prefix=>location.pathname.startsWith(prefix));
  const access = useQuery({queryKey:["suite-assistant-access",uid],queryFn:()=>api.get(`${root}/tools`),enabled:!!uid&&!standardModule,retry:false,staleTime:300000});
  return uid && (standardModule || access.isSuccess) ? <Assistant key={uid} /> : null;
}

function Assistant() {
  const queryClient = useQueryClient();
  const location = useLocation();
  const projectId =
    Number(location.pathname.match(/\/projects\/(\d+)/)?.[1]) || undefined;
  const customerId =
    Number(
      location.pathname.match(/\/crm\/(?:accounts|companies)\/(\d+)/)?.[1],
    ) || undefined;
  const workspaceId =
    Number((new URLSearchParams(location.search).get("workspace_id") || new URLSearchParams(location.search).get("workspace"))) ||
    undefined;
  const [open, setOpen] = useState(false);
  const [expanded, setExpanded] = useState(false);
  const [history, setHistory] = useState(false);
  const [search, setSearch] = useState("");
  const [chats, setChats] = useState<Row[]>([]);
  const [chat, setChat] = useState<number>();
  const [messages, setMessages] = useState<Row[]>([]);
  const [text, setText] = useState("");
  const [provider, setProvider] = useState("");
  const [stage, setStage] = useState(
    "Checking permissions and authoritative records…",
  );
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [details, setDetails] = useState(false);
  const [listening,setListening]=useState(false);
  const voice=useRef<any>();
  useEffect(()=>()=>voice.current?.abort(),[]);
  function dictate(){
    const Recognition=(window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    if(!Recognition){setError('Voice capture is unavailable in this browser. Type your request instead.');return;}
    if(listening){voice.current?.stop();return;}
    const rec=new Recognition();voice.current=rec;rec.lang=navigator.language;rec.interimResults=false;
    rec.onresult=(event:any)=>setText(old=>`${old} ${event.results[0][0].transcript}`.trim());
    rec.onend=()=>setListening(false);rec.onerror=()=>{setListening(false);setError('Voice capture stopped. Review the transcript before sending.');};
    rec.start();setListening(true);
  }
  const [intent, setIntent] = useState<Row>({
    tool: "invoices.prepare",
    tax_amount: "",
    amount: "",
    title: "",
    percentage: "",
  });
  const input = useRef<HTMLTextAreaElement>(null);
  const launcher = useRef<HTMLButtonElement>(null);
  const panel = useRef<HTMLElement>(null);
  const end = useRef<HTMLDivElement>(null);
  const sequence = useRef(0);
  const requestKey = useRef<string>();
  const controller = useRef<AbortController>();
  useEffect(
    () => () => {
      sequence.current++;
      controller.current?.abort();
    },
    [],
  );
  useEffect(() => {
    if (open) input.current?.focus();
  }, [open]);
  useEffect(() => {
    end.current?.scrollIntoView({ behavior: "instant" });
  }, [messages, busy]);
  useEffect(() => {
    if (!open || !history) return;
    const abort = new AbortController();
    api
      .get(`${root}/conversations`, {
        params: { q: search },
        signal: abort.signal,
      })
      .then((r) => setChats(r.data))
      .catch((e) => {
        if (!abort.signal.aborted) setError(textError(e));
      });
    return () => abort.abort();
  }, [open, history, search]);
  function close() {
    setOpen(false);
    launcher.current?.focus();
  }
  function reset() {
    sequence.current++;
    controller.current?.abort();
    setChat(undefined);
    setMessages([]);
    setText("");
    setError("");
    setBusy(false);
    requestKey.current = undefined;
    setHistory(false);
  }
  async function load(id: number) {
    const seq = ++sequence.current;
    setBusy(true);
    setError("");
    try {
      const r = await api.get(`${root}/conversations/${id}`);
      if (seq === sequence.current) {
        setChat(id);
        setMessages(r.data.messages);
        setHistory(false);
      }
    } catch (e) {
      if (seq === sequence.current) setError(textError(e));
    } finally {
      if (seq === sequence.current) setBusy(false);
    }
  }
  async function send(value = text, action?: Row) {
    if (busy || (!value.trim() && !action)) return;
    const seq = ++sequence.current;
    setBusy(true);
    setError("");
    controller.current = new AbortController();
    try {
      let id = chat;
      if (!id) {
        const r = await api.post(`${root}/conversations`, {
          title: "New conversation",
          workspace_id: workspaceId,
        });
        id = r.data.id;
        setChat(id);
      }
      requestKey.current ||= crypto.randomUUID();
      const payload: Row = {
        text: value,
        project_id: projectId,
        customer_id: customerId,
        request_key: requestKey.current,
        provider: provider || null,
      };
      if (action)
        payload.intent = Object.fromEntries(
          Object.entries(action).filter(([, v]) => v !== "" && v !== undefined),
        );
      const r = await assistantStream(
        `${root}/conversations/${id}/messages/stream`,
        payload,
        controller.current.signal,
        setStage,
      );
      if (seq === sequence.current) {
        setMessages((old) => [
          ...old.filter((m) => m.id !== r.data.id),
          r.data,
        ]);
        setText("");
        requestKey.current = undefined;
        setDetails(false);
      }
    } catch (e) {
      if (seq === sequence.current && !controller.current?.signal.aborted)
        setError(textError(e));
    } finally {
      if (seq === sequence.current) setBusy(false);
    }
  }
  async function approve(message: Row) {
    if (!chat || busy) return;
    setBusy(true);
    setError("");
    try {
      const r = await api.post(
        `${root}/conversations/${chat}/messages/${message.id}/confirm`,
        { approval_hash: message.approval_hash },
      );
      setMessages((old) =>
        old.map((m) =>
          m.id === message.id
            ? r.data
            : m.card?.kind === "saved_invoice" && m.card.id === r.data.card?.id
              ? { ...m, card: r.data.card }
              : m,
        ),
      );
      for (const key of [
        "project-billing",
        "shared-invoice",
        "customer-commercial-history",
        "srm",
        "projects",
        "tasks",
      ])
        queryClient.invalidateQueries({ queryKey: [key] });
    } catch (e) {
      setError(textError(e));
    } finally {
      setBusy(false);
    }
  }
  async function cancel(message: Row) {
    if (!chat || busy) return;
    setBusy(true);
    try {
      await api.post(
        `${root}/conversations/${chat}/messages/${message.id}/cancel`,
      );
      setMessages((old) =>
        old.map((m) =>
          m.id === message.id
            ? { ...m, status: "cancelled", card: undefined }
            : m,
        ),
      );
    } catch (e) {
      setError(textError(e));
    } finally {
      setBusy(false);
    }
  }
  function exportReport(card: Row) {
    const keys = Array.from(
      new Set<string>((card.items || []).flatMap((r: Row) => Object.keys(r))),
    );
    const cell = (value: unknown) => {
      let s = String(value ?? "");
      if (/^[=+@-]/.test(s)) s = "'" + s;
      return '"' + s.replace(/"/g, '""') + '"';
    };
    const csv = [
      keys.map(cell).join(","),
      ...(card.items || []).map((r: Row) =>
        keys.map((k) => cell(r[k])).join(","),
      ),
    ].join("\r\n");
    const url = URL.createObjectURL(
      new Blob([csv], { type: "text/csv;charset=utf-8" }),
    );
    const a = document.createElement("a");
    a.href = url;
    a.download = "authorized-assistant-report.csv";
    a.click();
    setTimeout(() => URL.revokeObjectURL(url), 10000);
  }
  async function download(id: number, number: string) {
    try {
      const response = await api.get(`/srm/invoices/${id}/pdf`, {
        responseType: "blob",
      });
      const url = URL.createObjectURL(response.data);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${number}.pdf`;
      a.click();
      setTimeout(() => URL.revokeObjectURL(url), 10000);
    } catch (e) {
      setError(textError(e));
    }
  }
  function choose(chip: string) {
    setText(chip);
    requestKey.current = undefined;
    if (
      ["Create an Invoice", "Create a Project", "Assign Tasks"].includes(chip)
    ) {
      setIntent({
        tool:
          chip === "Create an Invoice"
            ? "invoices.prepare"
            : chip === "Create a Project"
              ? "projects.create"
              : "tasks.assign",
        project_id: projectId,
      });
      setDetails(true);
    } else input.current?.focus();
  }
  return (
    <>
      <button
        ref={launcher}
        className="pms-ai-launcher"
        title="Ask AI Assistant"
        aria-label="Ask AI Assistant"
        aria-expanded={open}
        aria-controls="pms-ai-panel"
        onClick={() => setOpen((v) => !v)}
      >
        <Sparkles size={25} strokeWidth={1.6} />
        <span className="pms-ai-tooltip">Ask AI Assistant</span>
      </button>
      {open && (
        <section
          ref={panel}
          id="pms-ai-panel"
          role="dialog"
          aria-label="PMS AI Assistant"
          className={`pms-ai-panel ${expanded ? "pms-ai-expanded" : ""}`}
          onKeyDown={(e) => {
            if (e.key === "Escape") {
              e.stopPropagation();
              close();
            }
            if (e.key === "Tab") {
              const nodes = panel.current?.querySelectorAll<HTMLElement>(
                "button:not(:disabled),a,input,select,textarea",
              );
              if (!nodes?.length) return;
              const first = nodes[0],
                last = nodes[nodes.length - 1];
              if (e.shiftKey && document.activeElement === first) {
                e.preventDefault();
                last.focus();
              } else if (!e.shiftKey && document.activeElement === last) {
                e.preventDefault();
                first.focus();
              }
            }
          }}
        >
          <header className="pms-ai-header">
            <div className="pms-ai-avatar">
              <Sparkles size={21} />
            </div>
            <div>
              <strong>PMS AI Assistant</strong>
              <small>Your intelligent workspace assistant</small>
            </div>
            <button
              title="New conversation"
              aria-label="New conversation"
              onClick={reset}
            >
              <Plus size={17} />
            </button>
            <button
              title="Conversation history"
              aria-label="Conversation history"
              onClick={() => setHistory((v) => !v)}
            >
              <History size={17} />
            </button>
            <button
              title="Expand assistant"
              aria-label="Expand assistant"
              onClick={() => setExpanded((v) => !v)}
            >
              <Expand size={16} />
            </button>
            <button
              title="Close assistant"
              aria-label="Close assistant"
              onClick={close}
            >
              <X size={18} />
            </button>
          </header>
          <div className="pms-ai-context">
            <span className="pms-ai-dot" />
            {provider
              ? "Configured model · actions require approval"
              : "Guided mode · verified application tools"}
            <Link
              aria-label="Assistant provider settings"
              to="/pms/settings/ai/gemini"
            >
              <Settings size={14} />
            </Link>
          </div>
          <Link className="pms-ai-studio-link" to={`/pms/assistant${projectId?`?project=${projectId}`:''}`} onClick={close}>
            <Sparkles size={15}/><span>Open your assistant workspace<small>Plans, memory, playbooks & delivery insights</small></span><ArrowUp size={15}/>
          </Link>
          <Link className="pms-ai-studio-link" to={`/ai-agents/operator${workspaceId?`?workspace=${workspaceId}`:''}`} onClick={close}>
            <Sparkles size={15}/><span>Open suite AI operator<small>HR, CRM, sales, finance & projects · Gemini</small></span><ArrowUp size={15}/>
          </Link>
          <div className="pms-ai-body" aria-live="polite" aria-busy={busy}>
            {history ? (
              <div className="pms-ai-history">
                <label>
                  Search conversations
                  <input
                    value={search}
                    onChange={(e) => setSearch(e.target.value)}
                  />
                </label>
                {chats.map((c) => (
                  <div key={c.id}>
                    <button onClick={() => load(c.id)}>{c.title}</button>
                    <button
                      aria-label={`Rename ${c.title}`}
                      onClick={async () => {
                        const title = window.prompt(
                          "Conversation title",
                          c.title,
                        );
                        if (title) {
                          try {
                            await api.patch(`${root}/conversations/${c.id}`, {
                              title,
                            });
                            setSearch("");
                            setChats((old) =>
                              old.map((r) =>
                                r.id === c.id ? { ...r, title } : r,
                              ),
                            );
                          } catch (e) {
                            setError(textError(e));
                          }
                        }
                      }}
                    >
                      Rename
                    </button>
                    <button
                      aria-label={`Delete ${c.title}`}
                      onClick={async () => {
                        if (
                          !window.confirm(
                            "Remove this conversation from history? Business records remain intact.",
                          )
                        )
                          return;
                        try {
                          await api.delete(`${root}/conversations/${c.id}`);
                          setChats((old) => old.filter((r) => r.id !== c.id));
                          if (chat === c.id) reset();
                        } catch (e) {
                          setError(textError(e));
                        }
                      }}
                    >
                      Delete
                    </button>
                  </div>
                ))}
              </div>
            ) : (
              <>
                {!messages.length && (
                  <div className="pms-ai-welcome">
                    <span className="pms-ai-welcome-mark">
                      <Sparkles size={30} />
                    </span>
                    <h2>Hello! What would you like to accomplish today?</h2>
                    <p>
                      Find your work. Prepare a clear plan.
                      <br />
                      Review every change before it happens.
                    </p>
                    <div className="pms-ai-chips">
                      {suggestions.map((s) => (
                        <button key={s} onClick={() => choose(s)}>
                          {s}
                        </button>
                      ))}
                    </div>
                  </div>
                )}
                {messages.map((m) => (
                  <article key={m.id} className="pms-ai-turn">
                    <div className="pms-ai-user">{m.prompt || m.tool}</div>
                    <div className="pms-ai-answer">
                      <span className="pms-ai-label">
                        <Sparkles size={13} /> Assistant ·{" "}
                        {m.status.replace(/_/g, " ")}
                      </span>
                      <p>{m.card?.text || "Action cancelled."}</p>
                      {m.card?.kind === "approval" && m.card.details && (
                        <dl className="pms-ai-action-details">
                          {Object.entries(m.card.details)
                            .filter(
                              ([key, value]) =>
                                key !== "tool" &&
                                key !== "lines" &&
                                value !== null &&
                                value !== "" &&
                                !Array.isArray(value),
                            )
                            .map(([key, value]) => (
                              <div key={key}>
                                <dt>{key.replace(/_/g, " ")}</dt>
                                <dd>{String(value)}</dd>
                              </div>
                            ))}
                        </dl>
                      )}
                      {m.card?.kind === "invoice_preview" && (
                        <div className="pms-ai-invoice">
                          <div className="pms-ai-invoice-heading">
                            Invoice proposal <span>Not saved</span>
                          </div>
                          <strong>{m.card.customer}</strong>
                          <p>{m.card.project}</p>
                          <p>
                            Seller #{m.card.seller_id} · Due {m.card.due_date}
                          </p>
                          {m.card.lines.map((l: Row, i: number) => (
                            <div className="pms-ai-line" key={i}>
                              <span>
                                {l.description}
                                <small>
                                  {l.quantity} × {l.unit_price} · Discount{" "}
                                  {l.discount_amount} · Tax {l.tax_amount}
                                </small>
                              </span>
                            </div>
                          ))}
                          <div className="pms-ai-total">
                            Total{" "}
                            <strong>
                              {m.card.currency} {m.card.total} · Balance{" "}
                              {m.card.balance}
                            </strong>
                          </div>
                          <small>
                            Previously invoiced: {m.card.previously_invoiced}.
                            Remaining: {m.card.remaining ?? "No linked order"}.
                          </small>
                          <button
                            disabled={busy}
                            onClick={() => {
                              setIntent({
                                ...m.card,
                                tool: "invoices.prepare",
                                query: "",
                                customer_id: m.card.customer_id,
                                project_id: m.card.project_id,
                                lines: m.card.lines,
                                due_days: 15,
                              });
                              setDetails(true);
                              setText("Revise invoice proposal");
                            }}
                          >
                            Edit proposal
                          </button>
                        </div>
                      )}
                      {m.card?.items?.map((item: Row) => (
                        <div
                          className="pms-ai-record"
                          key={item.id || item.name}
                        >
                          <strong>{item.name}</strong>
                          <small>
                            {[
                              item.status,
                              item.due_date && `Due ${item.due_date}`,
                              item.outstanding &&
                                `${item.currency} ${item.outstanding} outstanding`,
                              item.assigned_tasks &&
                                `${item.assigned_tasks} assignments`,
                              item.invoiced && `Invoiced ${item.invoiced}`,
                              item.cash_applied && `Cash ${item.cash_applied}`,
                              item.value,
                            ]
                              .filter(Boolean)
                              .join(" · ")}
                          </small>
                          {m.card.kind === "selection" ||
                          m.card.kind === "customers" ? (
                            <button
                              disabled={busy}
                              onClick={() =>
                                send(`Selected ${item.name}`, {
                                  ...(m.card.next || {
                                    tool: "projects.search",
                                  }),
                                  query: "",
                                  [m.card.entity === "customer" ||
                                  m.card.kind === "customers"
                                    ? "customer_id"
                                    : "project_id"]: item.id,
                                })
                              }
                            >
                              Select
                            </button>
                          ) : (
                            ["projects", "tasks", "invoices"].includes(
                              m.card.kind,
                            ) && (
                              <Link
                                to={
                                  m.card.kind === "invoices"
                                    ? `/srm/invoices/${item.id}`
                                    : `/pms/${m.card.kind}/${item.id}`
                                }
                              >
                                Open ↗
                              </Link>
                            )
                          )}
                        </div>
                      ))}
                      {m.card?.kind === "report" && (
                        <button onClick={() => exportReport(m.card)}>
                          Export authorized rows (CSV)
                        </button>
                      )}
                      {m.card?.kind === "saved_invoice" && (
                        <div className="pms-ai-saved">
                          <Check size={18} />
                          <strong>
                            {m.card.number} · {m.card.currency} {m.card.total} ·
                            Balance {m.card.balance}
                          </strong>
                          <Link to={`/srm/invoices/${m.card.id}`}>
                            View invoice ↗
                          </Link>
                          <button
                            onClick={() => download(m.card.id, m.card.number)}
                          >
                            Download PDF
                          </button>
                          <button
                            disabled={
                              busy || m.card.document_status !== "draft"
                            }
                            onClick={() =>
                              send(`Review issuing ${m.card.number}`, {
                                tool: "invoices.issue",
                                invoice_id: m.card.id,
                              })
                            }
                          >
                            Review issue
                          </button>
                          <button
                            disabled={
                              busy ||
                              m.card.document_status !== "issued" ||
                              m.card.delivery_status === "sent"
                            }
                            onClick={() =>
                              send(`Review sending ${m.card.number}`, {
                                tool: "invoices.send",
                                invoice_id: m.card.id,
                              })
                            }
                          >
                            Review send
                          </button>
                          <button
                            disabled={
                              busy ||
                              m.card.document_status !== "issued" ||
                              Number(m.card.balance) <= 0
                            }
                            onClick={() => {
                              setIntent({
                                tool: "payments.record",
                                invoice_id: m.card.id,
                              });
                              setText("Review received payment");
                              setDetails(true);
                            }}
                          >
                            Record payment
                          </button>
                        </div>
                      )}
                      {m.card?.kind === "saved_project" && (
                        <Link to={`/pms/projects/${m.card.project_id}`}>
                          Open project ↗
                        </Link>
                      )}
                      {m.status === "awaiting_approval" && (
                        <div className="pms-ai-approval">
                          <small>
                            Approval expires in 15 minutes. Current permissions
                            and billing values are checked again.
                          </small>
                          <button
                            className="pms-ai-primary"
                            disabled={busy}
                            onClick={() => approve(m)}
                          >
                            Confirm{" "}
                            {m.tool === "invoices.prepare"
                              ? "& create invoice"
                              : "action"}
                          </button>
                          <button disabled={busy} onClick={() => cancel(m)}>
                            Cancel
                          </button>
                        </div>
                      )}
                    </div>
                  </article>
                ))}
              </>
            )}
            {busy && (
              <div role="status" className="pms-ai-working">
                <Loader2 size={15} className="animate-spin" /> {stage}
              </div>
            )}
            {error && (
              <p role="alert" className="pms-ai-error">
                {error}
              </p>
            )}
            <div ref={end} />
          </div>
          <footer className="pms-ai-composer">
            {details && (
              <div className="pms-ai-details">
                <label>
                  Action
                  <select
                    value={intent.tool}
                    onChange={(e) =>
                      setIntent({ ...intent, tool: e.target.value })
                    }
                  >
                    {[
                      "invoices.prepare",
                      "projects.create",
                      "tasks.create",
                      "tasks.assign",
                      "payments.record",
                    ].map((t) => (
                      <option key={t}>{t}</option>
                    ))}
                  </select>
                </label>
                {[
                  "project_id",
                  "customer_id",
                  "title",
                  ...(intent.tool === "invoices.prepare"
                    ? [
                        "amount",
                        "percentage",
                        "tax_amount",
                        "due_days",
                        "issue_date",
                        "due_date",
                      ]
                    : intent.tool === "projects.create"
                      ? [
                          "amount",
                          "seller_id",
                          "currency",
                          "start_date",
                          "due_date",
                        ]
                      : intent.tool === "tasks.assign"
                        ? ["task_id", "assignee_id"]
                        : intent.tool === "payments.record"
                          ? ["invoice_id", "amount"]
                          : []),
                ].map((k) => (
                  <label key={k}>
                    {k.replace(/_/g, " ")}
                    <input
                      value={intent[k] ?? ""}
                      type={
                        ["title", "currency"].includes(k)
                          ? "text"
                          : ["issue_date", "due_date", "start_date"].includes(k)
                            ? "date"
                            : "number"
                      }
                      min="0"
                      step="any"
                      onChange={(e) =>
                        setIntent({ ...intent, [k]: e.target.value })
                      }
                    />
                  </label>
                ))}
                {intent.lines && (
                  <div className="pms-ai-line-editor">
                    {intent.lines.map((line: Row, index: number) => (
                      <fieldset key={index}>
                        <legend>Line {index + 1}</legend>
                        {[
                          "description",
                          "quantity",
                          "unit_price",
                          "discount_amount",
                          "tax_amount",
                        ].map((key) => (
                          <label key={key}>
                            {key.replace(/_/g, " ")}
                            <input
                              aria-label={`Line ${index + 1} ${key.replace(/_/g, " ")}`}
                              type={key === "description" ? "text" : "number"}
                              min="0"
                              step="any"
                              value={line[key] ?? ""}
                              onChange={(e) =>
                                setIntent({
                                  ...intent,
                                  lines: intent.lines.map(
                                    (r: Row, i: number) =>
                                      i === index
                                        ? { ...r, [key]: e.target.value }
                                        : r,
                                  ),
                                })
                              }
                            />
                          </label>
                        ))}
                        <button
                          onClick={() =>
                            setIntent({
                              ...intent,
                              lines: intent.lines.filter(
                                (_: Row, i: number) => i !== index,
                              ),
                            })
                          }
                        >
                          Remove line
                        </button>
                      </fieldset>
                    ))}
                    <button
                      onClick={() =>
                        setIntent({
                          ...intent,
                          lines: [
                            ...intent.lines,
                            {
                              description: "",
                              quantity: 1,
                              unit_price: 0,
                              discount_amount: 0,
                              tax_amount: 0,
                            },
                          ],
                        })
                      }
                    >
                      Add invoice line
                    </button>
                  </div>
                )}
                <button
                  disabled={busy}
                  onClick={() => {
                    const allowed = [
                      "tool",
                      "query",
                      "project_id",
                      "customer_id",
                      "title",
                      "amount",
                      "percentage",
                      "tax_amount",
                      "due_days",
                      "task_id",
                      "assignee_id",
                      "lines",
                      "issue_date",
                      "due_date",
                      "invoice_id",
                      "seller_id",
                      "currency",
                      "start_date",
                    ];
                    send(
                      text || "Review action details",
                      Object.fromEntries(
                        Object.entries(intent).filter(([k]) =>
                          allowed.includes(k),
                        ),
                      ),
                    );
                  }}
                >
                  Prepare for review
                </button>
              </div>
            )}
            <div className="pms-ai-input-row">
              <button className={listening?'pms-ai-mic active':'pms-ai-mic'} disabled={busy} aria-label={listening?'Stop assistant voice capture':'Dictate assistant message'} onClick={dictate}><Mic size={17}/></button>
              <textarea
                ref={input}
                aria-label="Message AI Assistant"
                placeholder={
                  projectId
                    ? "Ask about this project…"
                    : "What would you like to do?"
                }
                rows={2}
                value={text}
                disabled={busy}
                onChange={(e) => {
                  setText(e.target.value);
                  requestKey.current = undefined;
                }}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    send();
                  }
                }}
              />
              <button
                className="pms-ai-send"
                aria-label={busy ? "Stop waiting" : "Send message"}
                disabled={!busy && !text.trim()}
                onClick={() => {
                  if (busy) {
                    controller.current?.abort();
                    sequence.current++;
                    setBusy(false);
                    setError(
                      "Stopped waiting. A read/proposal may still finish; no business action runs without confirmation. Resume history before retrying.",
                    );
                  } else send();
                }}
              >
                {busy ? <X size={18} /> : <ArrowUp size={18} />}
              </button>
            </div>
            <div className="pms-ai-bottom">
              <Link
                title="Browse authorized project documents"
                aria-label="Browse authorized project documents"
                to={
                  projectId ? `/pms/files?projectId=${projectId}` : "/pms/files"
                }
              >
                Files ↗
              </Link>
              <button
                aria-expanded={details}
                onClick={() => setDetails((v) => !v)}
              >
                <Plus size={13} /> Action details <ChevronDown size={12} />
              </button>
              <select
                aria-label="Assistant model provider"
                value={provider}
                onChange={(e) => setProvider(e.target.value)}
              >
                <option value="">Guided mode</option>
                <option value="openai">Configured OpenAI</option>
                <option value="gemini">Configured Gemini</option>
                <option value="claude">Configured Claude</option>
              </select>
            </div>
          </footer>
        </section>
      )}
    </>
  );
}
