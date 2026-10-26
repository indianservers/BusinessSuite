import React, { useEffect, useState, useRef } from "react";
import { Link } from "react-router-dom";
import { ShieldCheck, RefreshCw, LockKeyhole } from "lucide-react";
import { api } from "@/services/api";
import { useAuthStore } from "@/store/authStore";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";
import { ControlNav } from "./ControlCenter";
import "./control.css";
const root = "/access/ai-security";
const error = (e: any) =>
  typeof e?.response?.data?.detail === "string"
    ? e.response.data.detail
    : JSON.stringify(e?.response?.data?.detail || e.message);
export default function AiSecurityPage() {
  const actor = useAuthStore((s) => s.user);
  const [company, setCompany] = useState(
    Number(
      sessionStorage.getItem("suite-organization") ||
        actor?.access?.companyId ||
        1,
    ),
  );
  const [companies, setCompanies] = useState<any[]>([]),
    [result, setResult] = useState<{
      company: number;
      policy: any;
      logs: any;
    } | null>(null);
  const [page, setPage] = useState(1),
    [blocked, setBlocked] = useState(false),
    [busy, setBusy] = useState(false),
    [notice, setNotice] = useState(""),
    [failure, setFailure] = useState("");
  const [draft, setDraft] = useState<any>({
    max_calls: 8,
    max_seconds: 60,
    max_result_bytes: 16000,
    disabled_tools: [],
  });
  const [review, setReview] = useState(false),
    [password, setPassword] = useState(""),
    [reason, setReason] = useState("");
  const loadSequence = useRef(0);
  const draftIdentity = useRef("");
  const data = result?.company === company ? result : null;
  useEffect(() => {
    api
      .get("/access/control/organizations")
      .then((r) => setCompanies(r.data))
      .catch((e) => setFailure(error(e)));
  }, []);
  useEffect(() => {
    load();
  }, [company, page, blocked]);
  async function load() {
    const sequence = ++loadSequence.current;
    setBusy(true);
    setFailure("");
    try {
      const response = await Promise.all([
        api.get(root, { params: { companyId: company } }),
        api.get(root + "/logs", {
          params: { companyId: company, page, blocked },
        }),
      ]);
      if (sequence !== loadSequence.current) return;
      setResult({ company, policy: response[0].data, logs: response[1].data });
      const identity = `${company}:${response[0].data.version}`;
      if (draftIdentity.current !== identity) {
        draftIdentity.current = identity;
        setDraft({
          max_calls: response[0].data.limits.max_calls,
          max_seconds: response[0].data.limits.max_seconds,
          max_result_bytes: response[0].data.limits.max_result_bytes,
          disabled_tools: response[0].data.limits.disabled_tools,
        });
      }
    } catch (e) {
      if (sequence === loadSequence.current) setFailure(error(e));
    } finally {
      if (sequence === loadSequence.current) setBusy(false);
    }
  }
  async function save() {
    try {
      const token = (await api.post("/access/step-up", { password })).data
        .token;
      setPassword("");
      await api.put(
        root,
        { ...draft, companyId: company, version: data!.policy.version, reason },
        { headers: { "X-Access-Step-Up": token } },
      );
      setReview(false);
      setNotice(
        "AI limits saved and audited. Existing previews must be reviewed again.",
      );
      await load();
    } catch (e) {
      setFailure(error(e));
    }
  }
  return (
    <main className="cc-root" aria-busy={busy || !data}>
      <header className="cc-heading">
        <div>
          <span className="cc-eyebrow">MASTER SUITE / AI MANAGEMENT</span>
          <h1 className="text-2xl font-semibold">AI Security</h1>
          <p>
            AI proposes. Server authorization and exact human confirmation
            control execution.
          </p>
        </div>
        <div className="flex gap-2">
          <select
            aria-label="Security company"
            value={company}
            onChange={(e) => {
              setCompany(Number(e.target.value));
              setPage(1);
            }}
          >
            {companies.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </select>
          <Button variant="outline" onClick={load}>
            <RefreshCw size={14} />
            Refresh
          </Button>
        </div>
      </header>
      <ControlNav />
      {failure && (
        <p className="cc-error" role="alert">
          {failure}
        </p>
      )}
      {notice && <p role="status">{notice}</p>}
      {data && (
        <>
          <section className="cc-card">
            <div className="flex items-center gap-2">
              <ShieldCheck size={20} />
              <h2>Mandatory baseline · {data.policy.policyVersion}</h2>
            </div>
            <p className="my-3 text-sm">
              These protections cannot be disabled by prompts, models, tool
              arguments or administration settings.
            </p>
            <ul className="grid gap-2 md:grid-cols-2 text-sm">
              {data.policy.permanentlyProhibited.map((p: string) => (
                <li key={p} className="flex gap-2">
                  <LockKeyhole size={14} />
                  {p}
                </li>
              ))}
            </ul>
            <p className="mt-4 text-xs text-muted-foreground">
              Last configuration review:{" "}
              {data.policy.lastConfigurationReview
                ? new Date(data.policy.lastConfigurationReview).toLocaleString()
                : "Not recorded"}
              . Historical records without a verified context remain stored and
              are not replayed.
            </p>
          </section>
          <section className="cc-card">
            <h2>Execution limits</h2>
            <div className="flex flex-wrap gap-4 my-4">
              {["max_calls", "max_seconds", "max_result_bytes"].map((name) => (
                <label className="text-sm" key={name}>
                  {name.replace(/_/g, " ")}
                  <input
                    className="block border rounded p-2 mt-1"
                    aria-label={name}
                    type="number"
                    value={draft[name]}
                    onChange={(e) =>
                      setDraft({ ...draft, [name]: Number(e.target.value) })
                    }
                  />
                </label>
              ))}
            </div>
            <Button
              onClick={() => {
                setPassword("");
                setReason("");
                setReview(true);
              }}
            >
              Review and save limits
            </Button>
            <p className="mt-3 text-xs text-muted-foreground">
              You may tighten limits or disable reviewed tools. Registering a
              new tool does not approve it for AI.
            </p>
          </section>
          <section className="cc-card">
            <h2>Tool and permission registry</h2>
            <div className="cc-scroll">
              <table>
                <thead>
                  <tr>
                    <th>Tool</th>
                    <th>Module / permissions</th>
                    <th>Risk</th>
                    <th>Confirmation</th>
                    <th>AI execution</th>
                    <th>Handler</th>
                  </tr>
                </thead>
                <tbody>
                  {data.policy.tools.map((t: any) => (
                    <tr key={t.id}>
                      <td>
                        {t.id}
                        <small className="block">v{t.version}</small>
                      </td>
                      <td>
                        {t.module}
                        <small className="block max-w-xs break-words">
                          {typeof t.permission === "string"
                            ? t.permission
                            : JSON.stringify(t.permission)}
                        </small>
                      </td>
                      <td>{t.risk}</td>
                      <td>
                        {t.confirmation
                          ? "Exact reviewed operation"
                          : "Read authorization"}
                      </td>
                      <td>
                        {t.approved ? (
                          <label>
                            <input
                              type="checkbox"
                              checked={!draft.disabled_tools.includes(t.id)}
                              aria-label={`Enable ${t.id}`}
                              onChange={(e) =>
                                setDraft({
                                  ...draft,
                                  disabled_tools: e.target.checked
                                    ? draft.disabled_tools.filter(
                                        (id: string) => id !== t.id,
                                      )
                                    : [...draft.disabled_tools, t.id],
                                })
                              }
                            />{" "}
                            Enabled
                          </label>
                        ) : (
                          <strong>Permanently unavailable</strong>
                        )}
                      </td>
                      <td>
                        <code className="text-xs">{t.handler}</code>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
          <section className="cc-card">
            <div className="cc-heading">
              <h2>Execution and security events</h2>
              <label className="text-sm">
                <input
                  type="checkbox"
                  checked={blocked}
                  onChange={(e) => {
                    setBlocked(e.target.checked);
                    setPage(1);
                  }}
                />{" "}
                Denials and injection alerts
              </label>
            </div>
            <p className="text-xs text-muted-foreground mb-3">
              Append-only metadata. Prompts, document contents, credentials and
              full arguments are excluded.
            </p>
            <div className="cc-scroll">
              <table>
                <thead>
                  <tr>
                    <th>Time</th>
                    <th>User / session</th>
                    <th>Action / tool</th>
                    <th>Decision</th>
                    <th>Correlation</th>
                  </tr>
                </thead>
                <tbody>
                  {data.logs.items.map((row: any) => (
                    <tr key={row.id}>
                      <td>{new Date(row.created_at).toLocaleString()}</td>
                      <td>
                        #{row.user_id}
                        <small className="block">
                          Session{" "}
                          {row.session_id || "trusted internal delegation"}
                        </small>
                      </td>
                      <td>
                        {row.action}
                        <small className="block">
                          {row.input_json?.tool_name || row.module}
                        </small>
                      </td>
                      <td>
                        {row.status}
                        <small className="block">
                          {row.output_json?.authorization ||
                            row.output_json?.error_code ||
                            ""}
                        </small>
                      </td>
                      <td className="text-xs">{row.correlation_id}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {!data.logs.items.length && (
                <p className="cc-empty">
                  No matching events recorded for this company.
                </p>
              )}
            </div>
            <div className="flex gap-3 mt-3 items-center">
              <Button
                variant="outline"
                disabled={page === 1}
                onClick={() => setPage(page - 1)}
              >
                Previous
              </Button>
              <span>
                Page {page} · {data.logs.total} events
              </span>
              <Button
                variant="outline"
                disabled={page * 50 >= data.logs.total}
                onClick={() => setPage(page + 1)}
              >
                Next
              </Button>
            </div>
          </section>
          <Link to="/admin/control/services/ai">AI providers and usage</Link>
        </>
      )}
      <Dialog open={review} onOpenChange={setReview}>
        <DialogContent>
          <DialogTitle>Confirm AI security limits</DialogTitle>
          <p className="text-sm">
            Company #{company}. Policy {data?.policy.policyVersion}. The
            mandatory baseline remains enabled.
          </p>
          <pre className="text-xs overflow-auto max-h-52 bg-muted p-3">
            {JSON.stringify(draft, null, 2)}
          </pre>
          <label>
            Reason
            <input
              aria-label="AI policy reason"
              className="block border rounded p-2 w-full"
              value={reason}
              onChange={(e) => setReason(e.target.value)}
            />
          </label>
          <label>
            Administrator password
            <input
              aria-label="AI policy password"
              type="password"
              className="block border rounded p-2 w-full"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </label>
          {failure && <p role="alert">{failure}</p>}
          <Button disabled={reason.length < 3 || !password} onClick={save}>
            Verify and save AI policy
          </Button>
        </DialogContent>
      </Dialog>
    </main>
  );
}
