import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowRightLeft,
  CalendarClock,
  CheckCircle2,
  ClipboardCheck,
  Download,
  FileText,
  Layers,
  PackagePlus,
  Settings2,
  Upload,
  UserRound,
  ShieldCheck,
} from "lucide-react";
import { api, assetApi } from "@/services/api";
import { useAuthStore } from "@/store/authStore";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";
import EmployeeSearchSelect from "../../components/EmployeeSearchSelect";
import { toast } from "@/hooks/use-toast";
import { formatDate } from "@/lib/utils";

export type CustodyRow = {
  id: number;
  asset_id?: number;
  asset_name?: string;
  asset_tag?: string;
  employee_id: number;
  employee_name: string;
  assigned_date: string;
  expected_return_date?: string | null;
  returned_date?: string | null;
  condition_at_assignment?: string;
  condition_at_return?: string | null;
  acknowledged: boolean;
  accessories?: string[];
  inspection_approval_id?: number;
  recovery_approval_id?: number;
  inspection_status?: string;
  recovery_status?: string;
  recovery_amount?: string;
  return_details?: Record<string, unknown>;
};
type Approval = {
  id: number;
  type: string;
  status: string;
  reason?: string;
  can_decide: boolean;
};
type Document = {
  id: number;
  name: string;
  version: number;
  mime_type: string;
};
type Detail = {
  id: number;
  name: string;
  asset_tag: string;
  status: string;
  serial_number?: string;
  brand?: string;
  model?: string;
  location?: string;
  condition?: string;
  purchase_date?: string;
  purchase_cost?: string;
  warranty_expiry?: string;
  description?: string;
  details?: Record<string, unknown>;
  assignments: CustodyRow[];
  documents: Document[];
  approvals: Approval[];
  timeline: {
    id: number;
    action: string;
    at: string;
    actor_id: number;
    changes?: Record<string, unknown>;
  }[];
};
const today = () => new Date().toLocaleDateString("en-CA");
const message = (e: unknown) => {
  const value = (e as { response?: { data?: { detail?: unknown } } }).response
    ?.data?.detail;
  return typeof value === "string"
    ? value
    : "Please check the fields and try again.";
};
export function useAssetRefresh() {
  const qc = useQueryClient();
  return () =>
    Promise.all(
      [
        "assets",
        "asset-summary",
        "asset-insights",
        "assets-available",
        "asset-assignments",
        "asset-clearance",
        "asset-detail",
        "asset-policy",
      ].map((key) => qc.invalidateQueries({ queryKey: [key] })),
    );
}
export async function downloadAssetFile(url: string, name: string) {
  const { data } = await api.get(url, { responseType: "blob" });
  const link = document.createElement("a");
  const object = URL.createObjectURL(data);
  link.href = object;
  link.download = name;
  link.click();
  setTimeout(() => URL.revokeObjectURL(object), 1000);
}
function DownloadButton({
  url,
  name,
  label = "Download PDF",
}: {
  url: string;
  name: string;
  label?: string;
}) {
  const [busy, setBusy] = useState(false);
  return (
    <Button
      type="button"
      variant="outline"
      disabled={busy}
      onClick={async () => {
        setBusy(true);
        try {
          await downloadAssetFile(url, name);
        } catch (e) {
          toast({
            title: "Download unavailable",
            description: message(e),
            variant: "destructive",
          });
        } finally {
          setBusy(false);
        }
      }}
    >
      <Download size={15} />
      {label}
    </Button>
  );
}
function Field({
  label,
  value,
  onChange,
  type = "text",
  required = false,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  type?: string;
  required?: boolean;
}) {
  return (
    <label className="asset-form-field">
      <span>{label}</span>
      <Input
        type={type}
        required={required}
        value={value}
        onChange={(e) => onChange(e.target.value)}
      />
    </label>
  );
}
function EvidenceReferences({
  ids,
  documents = [],
}: {
  ids: unknown;
  documents?: Document[];
}) {
  if (!Array.isArray(ids) || !ids.length) return null;
  return (
    <div className="flex gap-2 flex-wrap">
      {ids.map((id) => {
        const document = documents.find((d) => d.id === Number(id));
        return (
          <DownloadButton
            key={Number(id)}
            url={`/access/services/documents/${Number(id)}/download`}
            name={document?.name || `evidence-${id}`}
            label={document?.name || `Evidence ${id}`}
          />
        );
      })}
    </div>
  );
}

function EvidenceUpload({
  assetId,
  documents = [],
  onUploaded,
}: {
  assetId: number;
  documents?: Document[];
  onUploaded?: (id: number) => void;
}) {
  const user = useAuthStore((s) => s.user),
    refresh = useAssetRefresh();
  const upload = useMutation({
    mutationFn: async (file: File) => {
      const form = new FormData();
      form.append("companyId", String(user?.access?.companyId || 1));
      form.append("module", "hrms");
      form.append("entity", "asset");
      form.append("entityId", String(assetId));
      form.append("file", file);
      return (await api.post("/access/services/documents", form))
        .data as Document;
    },
    onSuccess: async (doc) => {
      onUploaded?.(doc.id);
      await refresh();
      toast({ title: "Evidence attached" });
    },
    onError: (e) =>
      toast({
        title: "Upload failed",
        description: message(e),
        variant: "destructive",
      }),
  });
  return (
    <section className="asset-evidence">
      <h3>
        <FileText size={16} /> Documents & evidence
      </h3>
      <p className="text-xs text-muted-foreground">
        PDF, PNG or JPEG. Files use your company’s private document storage.
      </p>
      <label className="asset-upload-label">
        <Upload size={16} />
        {upload.isPending ? "Uploading…" : "Attach invoice, photo or document"}
        <input
          aria-label="Upload asset evidence"
          type="file"
          accept="application/pdf,image/png,image/jpeg"
          disabled={upload.isPending}
          onChange={(e) => {
            const file = e.target.files?.[0];
            if (file) upload.mutate(file);
            e.target.value = "";
          }}
        />
      </label>
      {documents.map((d) => (
        <div className="asset-document-row" key={d.id}>
          <span>
            {d.name}
            <small>Version {d.version}</small>
          </span>
          <DownloadButton
            url={`/access/services/documents/${d.id}/download`}
            name={d.name}
            label="Download"
          />
        </div>
      ))}
    </section>
  );
}
export function Asset360Panel({
  assetId,
  canManage = false,
}: {
  assetId: number;
  canManage?: boolean;
}) {
  const uid = useAuthStore((s) => s.user?.id);
  const query = useQuery({
    queryKey: ["asset-detail", uid, assetId],
    queryFn: () => api.get<Detail>(`/assets/${assetId}`).then((r) => r.data),
  });
  const refresh = useAssetRefresh();
  const repair = useMutation({
    mutationFn: () =>
      assetApi.update(assetId, { status: "Available", condition: "Good" }),
    onSuccess: refresh,
    onError: (e) =>
      toast({
        title: "Update failed",
        description: message(e),
        variant: "destructive",
      }),
  });
  if (query.isPending)
    return (
      <div className="asset-loading" role="status">
        Loading asset lifecycle…
      </div>
    );
  if (query.isError)
    return (
      <div role="alert">
        Asset details could not load.{" "}
        <Button onClick={() => query.refetch()}>Retry</Button>
      </div>
    );
  const d = query.data;
  return (
    <div className="asset-360-content">
      <div className="asset-detail-hero">
        <PackagePlus className="text-violet-600" />
        <h2>{d.name}</h2>
        <p>
          {d.asset_tag} · <span className="asset-status">{d.status}</span>
        </p>
      </div>
      <dl className="asset-detail-fields">
        {Object.entries({
          "Serial / registration": d.serial_number,
          Brand: d.brand,
          Model: d.model,
          Location: d.location,
          Condition: d.condition,
          "Purchase date": formatDate(d.purchase_date ?? null),
          "Purchase cost": d.purchase_cost,
          Warranty: formatDate(d.warranty_expiry ?? null),
          "Notes / accessories": d.description,
          ...(d.details || {}),
        }).map(([k, v]) => (
          <div key={k}>
            <dt>{k.replace(/_/g, " ")}</dt>
            <dd>
              {typeof v === "object"
                ? JSON.stringify(v)
                : String(v ?? "Not recorded")}
            </dd>
          </div>
        ))}
      </dl>
      {canManage && d.status === "Under Repair" && (
        <Button disabled={repair.isPending} onClick={() => repair.mutate()}>
          Repair complete: make available
        </Button>
      )}
      {canManage && <AssetEditDetails asset={d} />}
      {canManage ? (
        <EvidenceUpload assetId={assetId} documents={d.documents} />
      ) : (
        <section>
          <h3>Documents</h3>
          {d.documents.map((doc) => (
            <DownloadButton
              key={doc.id}
              url={`/access/services/documents/${doc.id}/download`}
              name={doc.name}
              label={doc.name}
            />
          ))}
        </section>
      )}
      <h3>Custody, return & inspection history</h3>
      {d.assignments.length ? (
        d.assignments.map((r) => (
          <div className="asset-timeline" key={r.id}>
            <b>{r.employee_name}</b>
            <p>
              Assigned {formatDate(r.assigned_date)} · Expected return{" "}
              {formatDate(r.expected_return_date ?? null)}
            </p>
            <p>
              {r.acknowledged ? "Acknowledged" : "Awaiting acknowledgment"}{" "}
              {r.returned_date && ` · Returned ${formatDate(r.returned_date)}`}
            </p>
            {r.returned_date && (
              <div className="asset-condition-comparison">
                <div>
                  <small>At handover</small>
                  <b>{r.condition_at_assignment || "Not recorded"}</b>
                  <span>
                    {(r.accessories || []).join(", ") ||
                      "No accessories recorded"}
                  </span>
                </div>
                <div>
                  <small>At return</small>
                  <b>{r.condition_at_return}</b>
                  <span>Inspection: {r.inspection_status}</span>
                </div>
              </div>
            )}
            <AssetRecordWorkflow
              row={{ ...r, asset_id: assetId }}
              canManage={canManage}
            />
          </div>
        ))
      ) : (
        <p>No custody history recorded.</p>
      )}
      <h3>Activity timeline</h3>
      {d.timeline.map((t) => (
        <div className="asset-timeline" key={t.id}>
          <b>{t.action.replace(/_/g, " ")}</b>
          <p>
            {formatDate(t.at)} · User {t.actor_id}
          </p>
          {t.changes && (
            <details>
              <summary>View recorded changes</summary>
              <pre className="asset-audit-json">
                {JSON.stringify(t.changes, null, 2)}
              </pre>
            </details>
          )}
        </div>
      ))}
    </div>
  );
}
export function Asset360Button({
  assetId,
  label,
  canManage = false,
}: {
  assetId: number;
  label: string;
  canManage?: boolean;
}) {
  const [open, setOpen] = useState(false);
  return (
    <>
      <button
        className="text-violet-700 underline underline-offset-4"
        onClick={() => setOpen(true)}
      >
        {label}
      </button>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="asset-360">
          <DialogTitle>Asset 360°</DialogTitle>
          <Asset360Panel assetId={assetId} canManage={canManage} />
        </DialogContent>
      </Dialog>
    </>
  );
}

export function AssetHandoverButton({ onSaved }: { onSaved?: () => void }) {
  const [open, setOpen] = useState(false),
    [employee, setEmployee] = useState(""),
    [search, setSearch] = useState(""),
    [ids, setIds] = useState<number[]>([]),
    [assigned, setAssigned] = useState(today()),
    [due, setDue] = useState(""),
    [condition, setCondition] = useState("Good"),
    [accessories, setAccessories] = useState(""),
    [remarks, setRemarks] = useState(""),
    [key, setKey] = useState(() => crypto.randomUUID()),
    [result, setResult] = useState<{ assignment_ids: number[] } | null>(null);
  const [handoverPhotos, setHandoverPhotos] = useState<
    Record<number, number[]>
  >({});
  const refresh = useAssetRefresh(),
    uid = useAuthStore((s) => s.user?.id);
  const available = useQuery({
    queryKey: ["assets-available", "batch", uid, search],
    enabled: open,
    queryFn: () =>
      assetApi
        .list({ status: "Available", search: search || undefined, limit: 200 })
        .then(
          (r) =>
            r.data as {
              id: number;
              name: string;
              asset_tag: string;
              condition?: string;
            }[],
        ),
  });
  const save = useMutation({
    mutationFn: () =>
      api
        .post("/assets/assignments/batch", {
          employee_id: Number(employee),
          asset_ids: ids,
          assigned_date: assigned,
          expected_return_date: due || null,
          condition_at_assignment: condition,
          accessories: accessories
            .split(",")
            .map((s) => s.trim())
            .filter(Boolean),
          remarks,
          request_key: key,
          handover_document_ids: handoverPhotos,
        })
        .then((r) => r.data),
    onSuccess: async (r) => {
      setResult(r);
      await refresh();
      onSaved?.();
      toast({
        title: "Handover registered",
        description: "The employee can acknowledge each asset in My Assets.",
      });
    },
    onError: (e) =>
      toast({
        title: "Handover failed",
        description: message(e),
        variant: "destructive",
      }),
  });
  return (
    <>
      <Button
        onClick={() => {
          setResult(null);
          setIds([]);
          setHandoverPhotos({});
          setKey(crypto.randomUUID());
          setOpen(true);
        }}
      >
        <Layers size={16} /> Assign multiple assets
      </Button>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="asset-360">
          <DialogTitle>Assign company assets</DialogTitle>
          {result ? (
            <div className="asset-form-grid">
              <CheckCircle2 className="text-green-600" />
              <h3>Handover saved</h3>
              <p>
                {result.assignment_ids.length} assets assigned. Employee
                acknowledgment is pending.
              </p>
              <DownloadButton
                url={`/assets/assignments/${result.assignment_ids[0]}/receipt`}
                name="asset-handover.pdf"
                label="Download handover receipt"
              />
              <Button onClick={() => setOpen(false)}>Done</Button>
            </div>
          ) : (
            <form
              className="asset-form-grid"
              onSubmit={(e) => {
                e.preventDefault();
                save.mutate();
              }}
            >
              <EmployeeSearchSelect
                endpoint="/assets/employees"
                value={employee}
                onChange={setEmployee}
              />
              <Field
                label="Find available assets"
                value={search}
                onChange={setSearch}
              />
              <div className="asset-available-list">
                {available.isPending ? (
                  <p role="status">Checking availability…</p>
                ) : available.isError ? (
                  <p role="alert">Available assets could not load.</p>
                ) : available.data?.length ? (
                  available.data.map((a) => (
                    <label key={a.id}>
                      <input
                        type="checkbox"
                        checked={ids.includes(a.id)}
                        disabled={["Poor", "Damaged", "Lost"].includes(
                          a.condition || "",
                        )}
                        onChange={(e) =>
                          setIds(
                            e.target.checked
                              ? [...ids, a.id]
                              : ids.filter((id) => id !== a.id),
                          )
                        }
                      />
                      <span>
                        <b>{a.name}</b>
                        <small>
                          {a.asset_tag} ·{" "}
                          {a.condition || "Condition not recorded"}
                        </small>
                      </span>
                    </label>
                  ))
                ) : (
                  <p>No available assets match this search.</p>
                )}
              </div>
              <p className="text-xs text-muted-foreground">
                {ids.length} selected · Availability is rechecked atomically
                when saving. Search to find assets beyond the first 200 matches.
              </p>
              <div className="asset-form-columns">
                <Field
                  label="Assignment date"
                  value={assigned}
                  onChange={setAssigned}
                  type="date"
                  required
                />
                <Field
                  label="Expected return date"
                  value={due}
                  onChange={setDue}
                  type="date"
                />
              </div>
              <label className="asset-form-field">
                Handover condition
                <select
                  aria-label="Physical condition"
                  value={condition}
                  onChange={(e) => setCondition(e.target.value)}
                >
                  {["New", "Good", "Fair"].map((s) => (
                    <option key={s}>{s}</option>
                  ))}
                </select>
              </label>
              <Field
                label="Accessories provided (comma separated)"
                value={accessories}
                onChange={setAccessories}
              />
              <Field
                label="Existing damage / handover remarks"
                value={remarks}
                onChange={setRemarks}
              />
              {!!ids.length && (
                <details>
                  <summary>
                    Handover photos / existing damage evidence (optional)
                  </summary>
                  <div className="asset-form-grid mt-3">
                    {ids.map((id) => (
                      <div key={id}>
                        <b>
                          {available.data?.find((a) => a.id === id)?.name ||
                            `Asset ${id}`}
                        </b>
                        <EvidenceUpload
                          assetId={id}
                          onUploaded={(doc) =>
                            setHandoverPhotos((previous) => ({
                              ...previous,
                              [id]: [...(previous[id] || []), doc],
                            }))
                          }
                        />
                      </div>
                    ))}
                  </div>
                </details>
              )}
              <p className="asset-policy-note">
                Employee acknowledgment is captured by the employee after
                handover. It cannot be signed on their behalf here.
              </p>
              <Button disabled={!employee || !ids.length || save.isPending}>
                {save.isPending
                  ? "Saving handover…"
                  : `Assign ${ids.length} assets`}
              </Button>
            </form>
          )}
        </DialogContent>
      </Dialog>
    </>
  );
}

export function AssetRecordWorkflow({
  row,
  canManage,
}: {
  row: CustodyRow;
  canManage: boolean;
}) {
  const [mode, setMode] = useState(""),
    [condition, setCondition] = useState("Good"),
    [date, setDate] = useState(today()),
    [remarks, setRemarks] = useState(""),
    [damage, setDamage] = useState(""),
    [accessories, setAccessories] = useState<string[]>([]),
    [photos, setPhotos] = useState<number[]>([]),
    [ack, setAck] = useState(false),
    [resolved, setResolved] = useState(false),
    [disposition, setDisposition] = useState("Available"),
    [amount, setAmount] = useState(""),
    [reference, setReference] = useState(""),
    [employee, setEmployee] = useState("");
  const refresh = useAssetRefresh(),
    uid = useAuthStore((s) => s.user?.id);
  const detail = useQuery({
    queryKey: ["asset-detail", uid, row.asset_id],
    enabled: !!row.asset_id && !!mode,
    queryFn: () =>
      api.get<Detail>(`/assets/${row.asset_id}`).then((r) => r.data),
  });
  const current = detail.data?.assignments.find((r) => r.id === row.id) || row;
  const perform = useMutation({
    mutationFn: async () => {
      const url = `/assets/assignments/${row.id}`;
      if (mode === "return")
        return api.post(url + "/receive", {
          return_date: date,
          condition,
          remarks,
          damage_description: damage,
          accessories_returned: accessories,
          employee_acknowledged: ack,
          photo_document_ids: photos,
        });
      if (mode === "inspection")
        return api.post(url + "/inspection", {
          comments: remarks,
          condition,
          disposition,
          missing_resolved: resolved,
          photo_document_ids: photos,
        });
      if (mode === "recovery")
        return api.post(url + "/recovery", {
          amount,
          reason: remarks,
          policy_reference: reference,
        });
      if (mode === "settle")
        return api.post(url + "/settle-recovery", { reference });
      if (mode === "exception")
        return api.post(url + "/exception", {
          reason: remarks,
          policy_reference: reference,
        });
      if (mode === "extend")
        return api.post(url + "/extend", {
          expected_return_date: date,
          reason: remarks,
        });
      if (mode === "transfer")
        return api.post(url + "/transfer", {
          employee_id: Number(employee),
          reason: remarks,
          assigned_date: date,
          condition,
        });
      return api.post(url + "/request-return");
    },
    onSuccess: async () => {
      await refresh();
      setMode("");
      toast({ title: "Asset lifecycle updated" });
    },
    onError: (e) =>
      toast({
        title: "Action could not complete",
        description: message(e),
        variant: "destructive",
      }),
  });
  const decision = useMutation({
    mutationFn: ({ id, decision }: { id: number; decision: string }) =>
      api.post(`/assets/approvals/${id}/decision`, {
        decision,
        reason: remarks,
      }),
    onSuccess: async () => {
      await refresh();
      toast({ title: "Approval decision recorded" });
    },
    onError: (e) =>
      toast({
        title: "Approval failed",
        description: message(e),
        variant: "destructive",
      }),
  });
  const active = !current.returned_date;
  const open = (value: string) => {
    setCondition("Good");
    setDate(today());
    setRemarks("");
    setReference("");
    setDamage("");
    setAccessories([]);
    setPhotos([]);
    setAck(false);
    setResolved(false);
    setMode(value);
  };
  const approvals =
    detail.data?.approvals.filter((a) =>
      [
        current.inspection_approval_id,
        (current as CustodyRow & { recovery_approval_id?: number })
          .recovery_approval_id,
        Number(current.return_details?.exception_approval_id),
      ].includes(a.id),
    ) || [];
  return (
    <div className="asset-workflow-actions">
      <DownloadButton
        url={`/assets/assignments/${row.id}/receipt`}
        name={`handover-${row.id}.pdf`}
        label="Handover PDF"
      />
      {canManage && (
        <>
          {active ? (
            <>
              <Button variant="outline" onClick={() => open("return")}>
                Record return
              </Button>
              <Button variant="outline" onClick={() => open("transfer")}>
                <ArrowRightLeft size={14} /> Transfer
              </Button>
              <Button variant="outline" onClick={() => open("extend")}>
                <CalendarClock size={14} /> Extend custody
              </Button>
              <Button variant="outline" onClick={() => open("request")}>
                Request return
              </Button>
            </>
          ) : (
            <>
              <Button variant="outline" onClick={() => open("inspection")}>
                <ClipboardCheck size={14} /> Inspect / approve
              </Button>
              <Button variant="outline" onClick={() => open("recovery")}>
                Propose recovery
              </Button>
              {current.recovery_status === "Approved" && (
                <Button variant="outline" onClick={() => open("settle")}>
                  Record settlement
                </Button>
              )}
              {(current.condition_at_return === "Lost" ||
                current.condition_at_return === "Damaged" ||
                current.condition_at_return === "Poor" ||
                !!current.return_details?.missing_accessories) && (
                <Button variant="outline" onClick={() => open("exception")}>
                  Request exception
                </Button>
              )}
            </>
          )}
        </>
      )}
      <Dialog
        open={!!mode}
        onOpenChange={(v) => {
          if (!v) setMode("");
        }}
      >
        <DialogContent className="asset-360">
          <DialogTitle>
            {
              (
                {
                  return: "Record asset return",
                  inspection: "Inspect return & approve",
                  recovery: "Recovery proposal",
                  settle: "Record approved settlement",
                  exception: "Document an asset exception",
                  extend: "Extend custody",
                  transfer: "Transfer asset",
                  request: "Request asset return",
                } as Record<string, string>
              )[mode]
            }
          </DialogTitle>
          <p className="text-sm text-muted-foreground">
            {row.asset_name} · {row.asset_tag} · {row.employee_name}
          </p>
          <form
            className="asset-form-grid"
            onSubmit={(e) => {
              e.preventDefault();
              perform.mutate();
            }}
          >
            {mode === "transfer" && (
              <EmployeeSearchSelect
                endpoint="/assets/employees"
                value={employee}
                onChange={setEmployee}
              />
            )}
            {["return", "extend", "transfer"].includes(mode) && (
              <Field
                label={
                  mode === "extend"
                    ? "New expected return date"
                    : mode === "transfer"
                      ? "Transfer date"
                      : "Return date"
                }
                type="date"
                value={date}
                onChange={setDate}
                required
              />
            )}
            {["return", "inspection", "transfer"].includes(mode) && (
              <label className="asset-form-field">
                Physical condition
                <select
                  aria-label="Physical condition"
                  value={condition}
                  onChange={(e) => setCondition(e.target.value)}
                >
                  {(mode === "return"
                    ? [
                        "New",
                        "Good",
                        "Fair",
                        "Poor",
                        "Damaged",
                        "Missing Accessories",
                        "Lost",
                        "Under Inspection",
                        "Under Repair",
                      ]
                    : mode === "transfer"
                      ? ["New", "Good", "Fair"]
                      : ["New", "Good", "Fair", "Poor", "Damaged", "Lost"]
                  ).map((c) => (
                    <option key={c}>{c}</option>
                  ))}
                </select>
              </label>
            )}
            {mode === "return" && (
              <>
                <fieldset className="asset-accessories">
                  <legend>Accessories received</legend>
                  {(row.accessories || []).length ? (
                    (row.accessories || []).map((a) => (
                      <label key={a}>
                        <input
                          type="checkbox"
                          checked={accessories.includes(a)}
                          onChange={(e) =>
                            setAccessories(
                              e.target.checked
                                ? [...accessories, a]
                                : accessories.filter((v) => v !== a),
                            )
                          }
                        />
                        {a}
                      </label>
                    ))
                  ) : (
                    <p>No accessories recorded at handover.</p>
                  )}
                </fieldset>
                <Field
                  label="Damage / loss description"
                  value={damage}
                  onChange={setDamage}
                  required={condition === "Lost"}
                />
                <label className="asset-checkbox">
                  <input
                    type="checkbox"
                    checked={ack}
                    onChange={(e) => setAck(e.target.checked)}
                  />
                  Employee acknowledged this return
                </label>
                <p className="asset-policy-note">
                  The asset remains unavailable until inspection and approval
                  are complete. Missing accessories are reconciled
                  automatically.
                </p>
              </>
            )}
            {mode === "inspection" && (
              <>
                <div className="asset-condition-comparison">
                  <div>
                    <small>At handover</small>
                    <b>{current.condition_at_assignment || "Not recorded"}</b>
                    <span>{(current.accessories || []).join(", ")}</span>
                    <EvidenceReferences
                      ids={
                        (
                          current.return_details?.at_handover as
                            | { photo_document_ids?: number[] }
                            | undefined
                        )?.photo_document_ids ||
                        current.return_details?.handover_photo_document_ids
                      }
                      documents={detail.data?.documents}
                    />
                  </div>
                  <div>
                    <small>At return</small>
                    <b>{current.condition_at_return}</b>
                    <EvidenceReferences
                      ids={current.return_details?.photo_document_ids}
                      documents={detail.data?.documents}
                    />
                    <span>
                      {String(
                        current.return_details?.remarks || "No return remarks",
                      )}
                    </span>
                  </div>
                </div>
                {!!current.return_details?.missing_accessories && (
                  <p className="asset-policy-note">
                    Missing:{" "}
                    {String(current.return_details.missing_accessories)}
                  </p>
                )}
                <label className="asset-form-field">
                  Recommended lifecycle status
                  <select
                    aria-label="Recommended lifecycle status"
                    value={disposition}
                    onChange={(e) => setDisposition(e.target.value)}
                  >
                    {[
                      "Available",
                      "Under Repair",
                      "Lost",
                      "Damaged",
                      "Retired",
                    ].map((s) => (
                      <option key={s}>{s}</option>
                    ))}
                  </select>
                </label>
                <label className="asset-checkbox">
                  <input
                    type="checkbox"
                    checked={resolved}
                    onChange={(e) => setResolved(e.target.checked)}
                  />
                  Missing accessories resolved and verified
                </label>
                <p className="text-sm">
                  Inspection status: <b>{current.inspection_status}</b>
                </p>
              </>
            )}
            {["recovery", "settle", "exception"].includes(mode) && (
              <>
                <p className="asset-policy-note">
                  Recovery proposals require company policy and an authorized
                  decision. This module never automatically charges an employee
                  or creates a payroll deduction.
                </p>
                {mode === "recovery" && (
                  <Field
                    label="Proposed recovery amount"
                    type="number"
                    value={amount}
                    onChange={setAmount}
                    required
                  />
                )}
                <Field
                  label={
                    mode === "settle"
                      ? "Payment / settlement reference"
                      : "Company policy reference"
                  }
                  value={reference}
                  onChange={setReference}
                  required
                />
              </>
            )}
            {mode !== "settle" && (
              <label className="asset-form-field">
                {mode === "inspection"
                  ? "Inspector comments / approval decision reason"
                  : "Reason / physical inspection remarks"}
                <textarea
                  required={mode !== "return" && mode !== "request"}
                  minLength={
                    mode === "exception" ? 10 : mode === "recovery" ? 5 : 3
                  }
                  rows={3}
                  value={remarks}
                  onChange={(e) => setRemarks(e.target.value)}
                />
              </label>
            )}
            {["return", "inspection"].includes(mode) && row.asset_id && (
              <EvidenceUpload
                assetId={row.asset_id}
                documents={detail.data?.documents}
                onUploaded={(id) => setPhotos([...photos, id])}
              />
            )}
            {mode === "inspection" &&
              approvals.map((a) => (
                <div className="asset-approval-card" key={a.id}>
                  <strong>
                    {a.type.replace(/_/g, " ")} · {a.status}
                  </strong>
                  <p>{a.reason}</p>
                  {a.status === "Pending" && a.can_decide && (
                    <div className="flex gap-2">
                      <Button
                        type="button"
                        disabled={
                          remarks.trim().length < 3 || decision.isPending
                        }
                        onClick={() =>
                          decision.mutate({ id: a.id, decision: "approve" })
                        }
                      >
                        Approve
                      </Button>
                      <Button
                        type="button"
                        variant="outline"
                        disabled={
                          remarks.trim().length < 3 || decision.isPending
                        }
                        onClick={() =>
                          decision.mutate({ id: a.id, decision: "reject" })
                        }
                      >
                        Reject
                      </Button>
                    </div>
                  )}
                </div>
              ))}
            <Button
              disabled={
                perform.isPending ||
                (mode === "inspection" &&
                  !["Pending", "Rejected"].includes(
                    current.inspection_status || "",
                  )) ||
                (mode === "transfer" && !employee)
              }
            >
              {perform.isPending
                ? "Saving…"
                : mode === "inspection"
                  ? "Submit inspection for approval"
                  : mode === "recovery"
                    ? "Submit recovery proposal"
                    : "Confirm " + mode}
            </Button>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}

type AssetPolicyValues = {
  inspection_approver_id: number | null;
  recovery_approver_id: number | null;
  exception_approver_id: number | null;
  block_damaged_clearance?: boolean;
  block_missing_clearance?: boolean;
  recovery_enabled: boolean;
  recovery_limit: string | number;
  reminders_enabled: boolean;
  reminder_days: number;
  repeat_days: number;
  channels: string[];
  manager_user_ids: number[];
  whatsapp_template?: Record<string, unknown> | null;
};
export function AssetPolicyButton() {
  const [open, setOpen] = useState(false),
    [form, setForm] = useState<AssetPolicyValues | null>(null),
    [template, setTemplate] = useState("");
  const refresh = useAssetRefresh();
  const query = useQuery({
    queryKey: ["asset-policy"],
    queryFn: () =>
      api
        .get<{
          values: AssetPolicyValues;
          can_configure: boolean;
        }>("/assets/policy")
        .then((r) => r.data),
  });
  const approvers = useQuery({
    queryKey: ["asset-policy", "approvers"],
    enabled: open,
    queryFn: () =>
      api
        .get<{ id: number; name: string }[]>("/assets/approvers")
        .then((r) => r.data),
  });
  const save = useMutation({
    mutationFn: () =>
      api.post("/assets/policy", {
        ...form,
        whatsapp_template: template.trim() ? JSON.parse(template) : null,
      }),
    onSuccess: async () => {
      await refresh();
      setOpen(false);
      toast({ title: "Asset policy saved" });
    },
    onError: (e) =>
      toast({
        title: "Policy could not save",
        description: message(e),
        variant: "destructive",
      }),
  });
  const run = useMutation({
    mutationFn: () => api.post<{ queued: number }>("/assets/reminders/run"),
    onSuccess: (r) =>
      toast({
        title: `${r.data.queued} reminders queued`,
        description: "Previously queued alerts are skipped.",
      }),
    onError: (e) =>
      toast({
        title: "Reminders unavailable",
        description: message(e),
        variant: "destructive",
      }),
  });
  return (
    <>
      <Button
        variant="outline"
        disabled={!query.data}
        onClick={() => {
          setForm(query.data!.values);
          setTemplate(
            query.data!.values.whatsapp_template
              ? JSON.stringify(query.data!.values.whatsapp_template, null, 2)
              : "",
          );
          setOpen(true);
        }}
      >
        <Settings2 size={15} /> Asset policy
      </Button>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="asset-360">
          <DialogTitle>Approvals & reminders</DialogTitle>
          {form && (
            <form
              className="asset-form-grid"
              onSubmit={(e) => {
                e.preventDefault();
                save.mutate();
              }}
            >
              <p className="asset-policy-note">
                Approvals use Approval OS. Without a named approver, only a
                super administrator can decide. Ordinary requesters cannot
                approve their own proposals.
              </p>
              {(
                [
                  "inspection_approver_id",
                  "recovery_approver_id",
                  "exception_approver_id",
                ] as const
              ).map((key) => (
                <label className="asset-form-field" key={key}>
                  {(
                    {
                      inspection_approver_id: "Inspection approver",
                      recovery_approver_id: "Recovery / Finance approver",
                      exception_approver_id: "Exception approver",
                    } as Record<string, string>
                  )[key] || key.replace(/_/g, " ")}
                  <select
                    disabled={!query.data?.can_configure}
                    value={form[key] || ""}
                    onChange={(e) =>
                      setForm({
                        ...form,
                        [key]: e.target.value ? Number(e.target.value) : null,
                      })
                    }
                  >
                    <option value="">Super administrator</option>
                    {approvers.data?.map((a) => (
                      <option key={a.id} value={a.id}>
                        {a.name}
                      </option>
                    ))}
                  </select>
                </label>
              ))}
              <label className="asset-checkbox">
                <input
                  disabled={!query.data?.can_configure}
                  type="checkbox"
                  checked={form.recovery_enabled}
                  onChange={(e) =>
                    setForm({ ...form, recovery_enabled: e.target.checked })
                  }
                />
                Enable policy-based recovery proposals
              </label>
              <label className="asset-checkbox">
                <input
                  type="checkbox"
                  checked={form.block_damaged_clearance ?? false}
                  disabled={!query.data?.can_configure}
                  onChange={(e) =>
                    setForm({
                      ...form,
                      block_damaged_clearance: e.target.checked,
                    })
                  }
                />
                Block asset clearance until damage is resolved or excepted
              </label>
              <label className="asset-checkbox">
                <input
                  type="checkbox"
                  checked={form.block_missing_clearance ?? true}
                  disabled={!query.data?.can_configure}
                  onChange={(e) =>
                    setForm({
                      ...form,
                      block_missing_clearance: e.target.checked,
                    })
                  }
                />
                Block asset clearance for missing accessories
              </label>
              <Field
                label="Maximum recovery proposal (0 = no configured cap)"
                type="number"
                value={String(form.recovery_limit)}
                onChange={(v) => setForm({ ...form, recovery_limit: v })}
              />
              <label className="asset-checkbox">
                <input
                  disabled={!query.data?.can_configure}
                  type="checkbox"
                  checked={form.reminders_enabled}
                  onChange={(e) =>
                    setForm({ ...form, reminders_enabled: e.target.checked })
                  }
                />
                Enable asset reminders
              </label>
              <div className="asset-form-columns">
                <Field
                  label="Days before deadline"
                  type="number"
                  value={String(form.reminder_days)}
                  onChange={(v) =>
                    setForm({ ...form, reminder_days: Number(v) })
                  }
                />
                <Field
                  label="Repeat interval (days)"
                  type="number"
                  value={String(form.repeat_days)}
                  onChange={(v) => setForm({ ...form, repeat_days: Number(v) })}
                />
              </div>
              <fieldset className="asset-accessories">
                <legend>Delivery channels</legend>
                {["in_app", "email", "whatsapp"].map((channel) => (
                  <label key={channel}>
                    <input
                      type="checkbox"
                      disabled={!query.data?.can_configure}
                      checked={form.channels.includes(channel)}
                      onChange={(e) =>
                        setForm({
                          ...form,
                          channels: e.target.checked
                            ? [...form.channels, channel]
                            : form.channels.filter((c) => c !== channel),
                        })
                      }
                    />
                    {channel.replace("_", " ")}
                  </label>
                ))}
              </fieldset>
              <label className="asset-form-field">
                Reminder recipients (managers)
                <select
                  multiple
                  value={form.manager_user_ids.map(String)}
                  onChange={(e) =>
                    setForm({
                      ...form,
                      manager_user_ids: Array.from(
                        e.target.selectedOptions,
                        (o) => Number(o.value),
                      ),
                    })
                  }
                >
                  {approvers.data?.map((a) => (
                    <option key={a.id} value={a.id}>
                      {a.name}
                    </option>
                  ))}
                </select>
              </label>
              {form.channels.includes("whatsapp") && (
                <label className="asset-form-field">
                  Approved WhatsApp template JSON
                  <textarea
                    rows={5}
                    value={template}
                    onChange={(e) => setTemplate(e.target.value)}
                    placeholder={
                      '{"name":"asset_reminder","language":{"code":"en"}}'
                    }
                  />
                  <small>
                    Your existing connected WhatsApp account, sender
                    authorization and recipient consent rules apply.
                  </small>
                </label>
              )}
              <p className="text-xs text-muted-foreground">
                Reminders cover upcoming and overdue returns, pending
                acknowledgments, inspections, warranty, insurance, maintenance
                and exit asset actions. The existing background worker processes
                enabled policies.
              </p>
              {query.data?.can_configure && (
                <Button disabled={save.isPending}>Save policy</Button>
              )}
              <Button
                type="button"
                variant="outline"
                disabled={run.isPending}
                onClick={() => run.mutate()}
              >
                Queue due reminders now
              </Button>
            </form>
          )}
        </DialogContent>
      </Dialog>
    </>
  );
}
export function AssetExitActions({
  exitId,
  canManage,
  issues = [],
}: {
  exitId: number;
  canManage: boolean;
  issues?: { kind: string; asset_tag: string }[];
}) {
  const refresh = useAssetRefresh();
  const complete = useMutation({
    mutationFn: () =>
      api.post(`/assets/exit-clearance/${exitId}/complete-assets`),
    onSuccess: async () => {
      await refresh();
      toast({
        title: "Asset clearance signed off",
        description:
          "Other department approvals remain in the existing exit workflow.",
      });
    },
    onError: (e) =>
      toast({
        title: "Clearance blocked",
        description: message(e),
        variant: "destructive",
      }),
  });
  return (
    <section className="asset-form-grid">
      <h3>
        <ShieldCheck size={16} /> Asset clearance checks
      </h3>
      {issues.map((i, index) => (
        <p className="asset-policy-note" key={index}>
          {i.asset_tag} · {i.kind}
        </p>
      ))}
      {canManage && (
        <Button
          disabled={!!issues.length || complete.isPending}
          onClick={() => complete.mutate()}
        >
          Complete asset clearance only
        </Button>
      )}
      <DownloadButton
        url={`/assets/exit-clearance/${exitId}/certificate`}
        name={`asset-clearance-${exitId}.pdf`}
        label="Download asset clearance certificate"
      />
      <a className="text-sm text-violet-700 underline" href="/hrms/exit">
        Open existing offboarding process
      </a>
    </section>
  );
}

export function AssetRegistrationButton({
  categories,
  onSaved,
  openRequest,
}: {
  categories: { id: number; name: string }[];
  onSaved: () => void;
  openRequest?: string;
}) {
  const [open, setOpen] = useState(false),
    [tab, setTab] = useState("Basic details"),
    [review, setReview] = useState(false),
    [form, setForm] = useState<Record<string, string>>({}),
    [custom, setCustom] = useState(""),
    [invoice, setInvoice] = useState<File | null>(null),
    [created, setCreated] = useState<number | null>(null),
    [pending, setPending] = useState(false);
  const refresh = useAssetRefresh(),
    user = useAuthStore((s) => s.user);
  useEffect(() => {
    if (openRequest) {
      setForm({});
      setReview(false);
      setCreated(null);
      setInvoice(null);
      setCustom("");
      setTab("Basic details");
      setOpen(true);
    }
  }, [openRequest]);
  const update = (key: string, value: string) =>
    setForm({ ...form, [key]: value });
  const field = (
    key: string,
    label: string,
    type = "text",
    required = false,
  ) => (
    <Field
      key={key}
      label={label}
      value={form[key] || ""}
      type={type}
      onChange={(v) => update(key, v)}
      required={required}
    />
  );
  const vehicle = /bike|scooter|car|vehicle|two.?wheeler/i.test(
    categories.find((c) => String(c.id) === form.category_id)?.name || "",
  );
  const save = async () => {
    setPending(true);
    try {
      let identity = created;
      if (!identity) {
        const details: Record<string, unknown> = {};
        for (const key of [
          "supplier",
          "invoice_number",
          "asset_value",
          "department",
          "responsible_person",
          "insurance_number",
          "insurance_expiry",
          "chassis_number",
          "engine_number",
          "roadworthiness_expiry",
          "maintenance_due",
          "replacement_due",
          "specifications",
          "notes",
        ])
          if (form[key]) details[key] = form[key];
        if (custom.trim()) details.custom_fields = JSON.parse(custom);
        const response = await assetApi.create({
          name: form.name,
          asset_tag: form.asset_tag,
          category_id: form.category_id ? Number(form.category_id) : null,
          brand: form.brand || null,
          model: form.model || null,
          serial_number: form.serial_number || null,
          purchase_cost: form.purchase_cost || null,
          purchase_date: form.purchase_date || null,
          warranty_expiry: form.warranty_expiry || null,
          description: form.description || null,
          condition: form.condition || "Good",
          location: form.location || null,
          details,
        });
        identity = response.data.id;
        setCreated(identity);
      }
      if (invoice) {
        const payload = new FormData();
        payload.append("companyId", String(user?.access?.companyId || 1));
        payload.append("module", "hrms");
        payload.append("entity", "asset");
        payload.append("entityId", String(identity));
        payload.append("file", invoice);
        await api.post("/access/services/documents", payload);
        setInvoice(null);
      }
      await refresh();
      onSaved();
      setOpen(false);
      toast({ title: "Asset registered" });
    } catch (e) {
      toast({
        title: created
          ? "Asset saved; attachment needs retry"
          : "Registration failed",
        description: message(e),
        variant: "destructive",
      });
    } finally {
      setPending(false);
    }
  };
  const tabs = [
    "Basic details",
    "Purchase & finance",
    "Location & custody",
    "Additional details",
  ];
  return (
    <>
      <Button
        onClick={() => {
          setForm({});
          setCustom("");
          setInvoice(null);
          setCreated(null);
          setReview(false);
          setTab(tabs[0]);
          setOpen(true);
        }}
      >
        <PackagePlus size={16} /> Register asset
      </Button>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="asset-360">
          <DialogTitle>Register company asset</DialogTitle>
          <nav className="asset-form-tabs">
            {tabs.map((t) => (
              <button
                key={t}
                aria-pressed={tab === t && !review}
                onClick={() => {
                  setTab(t);
                  setReview(false);
                }}
              >
                {t}
              </button>
            ))}
          </nav>
          <form
            className="asset-form-grid"
            onSubmit={(e) => {
              e.preventDefault();
              if (review) void save();
              else if (form.name?.trim() && form.asset_tag?.trim())
                setReview(true);
              else {
                setTab(tabs[0]);
                toast({
                  title: "Enter an asset name and unique tag",
                  variant: "destructive",
                });
              }
            }}
          >
            {review ? (
              <>
                <h3>Review before saving</h3>
                <dl className="asset-detail-fields">
                  {Object.entries(form)
                    .filter(([, v]) => v)
                    .map(([k, v]) => (
                      <div key={k}>
                        <dt>{k.replace(/_/g, " ")}</dt>
                        <dd>{v}</dd>
                      </div>
                    ))}
                </dl>
                {invoice && <p>Invoice attachment: {invoice.name}</p>}
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => setReview(false)}
                >
                  Back to details
                </Button>
              </>
            ) : (
              <>
                {tab === tabs[0] && (
                  <>
                    {field("name", "Asset name", "text", true)}
                    {field(
                      "asset_tag",
                      "Unique company asset tag",
                      "text",
                      true,
                    )}
                    <label className="asset-form-field">
                      Category
                      <select
                        aria-label="Category"
                        value={form.category_id || ""}
                        onChange={(e) => update("category_id", e.target.value)}
                      >
                        <option value="">Uncategorized</option>
                        {categories.map((c) => (
                          <option key={c.id} value={c.id}>
                            {c.name}
                          </option>
                        ))}
                      </select>
                    </label>
                    <div className="asset-form-columns">
                      {field("brand", "Brand")}
                      {field("model", "Model")}
                    </div>
                    {field(
                      "serial_number",
                      vehicle ? "Vehicle registration number" : "Serial number",
                    )}
                    {field("description", "Description / handover notes")}
                  </>
                )}
                {tab === tabs[1] && (
                  <>
                    {field("supplier", "Supplier")}
                    {field("invoice_number", "Invoice number")}
                    <div className="asset-form-columns">
                      {field("purchase_date", "Purchase date", "date")}
                      {field("purchase_cost", "Purchase cost", "number")}
                      {field("warranty_expiry", "Warranty expiry", "date")}
                      {field("asset_value", "Asset value", "number")}
                    </div>
                    <label className="asset-form-field">
                      Invoice attachment
                      <input
                        type="file"
                        accept="application/pdf,image/png,image/jpeg"
                        onChange={(e) =>
                          setInvoice(e.target.files?.[0] || null)
                        }
                      />
                    </label>
                  </>
                )}
                {tab === tabs[2] && (
                  <>
                    {field("location", "Branch / physical location")}
                    {field("department", "Responsible department")}
                    {field("responsible_person", "Responsible person")}
                    <p className="asset-policy-note">
                      Assets are registered in the selected workspace branch as
                      Available. Use Assign multiple assets to establish
                      employee custody and capture acknowledgment.
                    </p>
                  </>
                )}
                {tab === tabs[3] && (
                  <>
                    <label className="asset-form-field">
                      Physical condition
                      <select
                        value={form.condition || "Good"}
                        onChange={(e) => update("condition", e.target.value)}
                      >
                        {["New", "Good", "Fair", "Poor", "Damaged"].map((c) => (
                          <option key={c}>{c}</option>
                        ))}
                      </select>
                    </label>
                    {vehicle ? (
                      <>
                        {field("chassis_number", "Chassis number")}
                        {field("engine_number", "Engine number")}
                        {field("insurance_number", "Insurance policy number")}
                        {field("insurance_expiry", "Insurance expiry", "date")}
                        {field(
                          "roadworthiness_expiry",
                          "Roadworthiness expiry",
                          "date",
                        )}
                      </>
                    ) : (
                      field("specifications", "Specifications")
                    )}
                    {field("maintenance_due", "Next maintenance", "date")}
                    {field("replacement_due", "Due for replacement", "date")}
                    {field("notes", "Additional notes")}
                    <CustomFieldsEditor value={custom} onChange={setCustom} />
                  </>
                )}
              </>
            )}
            <Button disabled={pending}>
              {pending
                ? "Saving…"
                : review
                  ? created
                    ? "Retry invoice attachment"
                    : "Save asset"
                  : "Review asset"}
            </Button>
          </form>
        </DialogContent>
      </Dialog>
    </>
  );
}

export function EmployeeAssetProfileButton({
  employeeId,
  label,
  canManage,
}: {
  employeeId: number;
  label: string;
  canManage: boolean;
}) {
  const [open, setOpen] = useState(false),
    uid = useAuthStore((s) => s.user?.id);
  const query = useQuery({
    queryKey: ["asset-assignments", "employee-profile", uid, employeeId],
    enabled: open,
    queryFn: () =>
      api
        .get<{
          name: string;
          employee_code: string;
          department: string;
          designation: string;
          status: string;
          assignments: CustodyRow[];
        }>(`/assets/employees/${employeeId}/profile`)
        .then((r) => r.data),
  });
  return (
    <>
      <Button size="sm" variant="outline" onClick={() => setOpen(true)}>
        <UserRound size={14} />
        {label}
      </Button>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="asset-360">
          <DialogTitle>Employee asset profile</DialogTitle>
          {query.isPending ? (
            <p role="status">Loading employee custody…</p>
          ) : query.isError ? (
            <p role="alert">Employee profile could not load.</p>
          ) : (
            <div className="asset-form-grid">
              <div className="asset-detail-hero">
                <h2>{query.data.name}</h2>
                <p>
                  {query.data.employee_code} · {query.data.department} ·{" "}
                  {query.data.designation}
                </p>
                <span className="asset-status">{query.data.status}</span>
              </div>
              {canManage && <AssetHandoverButton />}
              {["Current custody", "Previous assignments"].map((title) => (
                <section key={title}>
                  <h3>{title}</h3>
                  {query.data.assignments
                    .filter((r) =>
                      title === "Current custody"
                        ? !r.returned_date
                        : !!r.returned_date,
                    )
                    .map((r) => (
                      <div className="asset-timeline" key={r.id}>
                        <Asset360Button
                          assetId={r.asset_id!}
                          label={`${r.asset_name} · ${r.asset_tag}`}
                          canManage={canManage}
                        />
                        <p>
                          Assigned {formatDate(r.assigned_date)} · Expected{" "}
                          {formatDate(r.expected_return_date ?? null)}
                        </p>
                        <p>
                          {r.acknowledged
                            ? "Acknowledged"
                            : "Acknowledgment pending"}
                          {r.condition_at_return &&
                            ` · Return condition: ${r.condition_at_return}`}
                        </p>
                        <AssetRecordWorkflow row={r} canManage={canManage} />
                      </div>
                    ))}
                </section>
              ))}
            </div>
          )}
        </DialogContent>
      </Dialog>
    </>
  );
}

export function AssetIntelligence() {
  const uid = useAuthStore((s) => s.user?.id);
  const q = useQuery({
    queryKey: ["asset-insights", uid],
    queryFn: () =>
      api
        .get<{
          repair_backlog: number;
          without_custodian: number;
          overdue: number;
          due_soon: number;
          pending_inspections: number;
          outstanding_recoveries: string;
          warranty_expiring: { id: number; name: string; date: string }[];
          high_value: { id: number; name: string; value: string }[];
          replacement_due: { id: number; name: string }[];
        }>("/assets/insights")
        .then((r) => r.data),
  });
  if (q.isPending) return <p role="status">Loading asset intelligence…</p>;
  if (q.isError) return <p role="alert">Asset intelligence could not load.</p>;
  return (
    <>
      <h2>Lifecycle intelligence</h2>
      <div className="asset-intelligence-counts">
        {[
          ["Repair backlog", q.data.repair_backlog],
          ["Overdue returns", q.data.overdue],
          ["Due within 30 days", q.data.due_soon],
          ["Pending inspections", q.data.pending_inspections],
          ["Outstanding recoveries", q.data.outstanding_recoveries],
          ["Without a custodian", q.data.without_custodian],
        ].map(([label, value]) => (
          <div key={label}>
            <span>{label}</span>
            <b>{value ?? 0}</b>
          </div>
        ))}
      </div>
      <h3>Warranty expiring</h3>
      {q.data.warranty_expiring?.length ? (
        q.data.warranty_expiring.map((a) => (
          <p key={a.id}>
            <Asset360Button assetId={a.id} label={a.name} /> ·{" "}
            {formatDate(a.date)}
          </p>
        ))
      ) : (
        <p>No warranties expire within 30 days.</p>
      )}
      <h3>High-value assets</h3>
      {q.data.high_value?.map((a) => (
        <p key={a.id}>
          <Asset360Button assetId={a.id} label={a.name} /> ·{" "}
          {Number(a.value).toLocaleString()}
        </p>
      ))}
      <h3>Due for replacement</h3>
      {q.data.replacement_due?.length ? (
        q.data.replacement_due.map((a) => (
          <p key={a.id}>
            <Asset360Button assetId={a.id} label={a.name} />
          </p>
        ))
      ) : (
        <p>No replacements currently due.</p>
      )}
    </>
  );
}

function AssetEditDetails({ asset }: { asset: Detail }) {
  const [form, setForm] = useState<Record<string, string>>(() =>
      Object.fromEntries(
        [
          "name",
          "serial_number",
          "brand",
          "model",
          "location",
          "condition",
          "status",
          "purchase_date",
          "purchase_cost",
          "warranty_expiry",
          "description",
        ].map((k) => [
          k,
          String((asset as unknown as Record<string, unknown>)[k] ?? ""),
        ]),
      ),
    ),
    [extra, setExtra] = useState(JSON.stringify(asset.details || {}, null, 2));
  const refresh = useAssetRefresh();
  const mutation = useMutation({
    mutationFn: () => {
      const details = JSON.parse(extra);
      if (!details || Array.isArray(details) || typeof details !== "object")
        throw new Error("Details must be a JSON object");
      return assetApi.update(asset.id, {
        ...form,
        purchase_date: form.purchase_date || null,
        warranty_expiry: form.warranty_expiry || null,
        purchase_cost: form.purchase_cost || null,
        details,
        ...(["Assigned", "Pending Inspection"].includes(asset.status)
          ? { status: undefined }
          : {}),
      });
    },
    onSuccess: async () => {
      await refresh();
      toast({ title: "Asset details updated" });
    },
    onError: (e) =>
      toast({
        title: "Could not update asset",
        description: message(e),
        variant: "destructive",
      }),
  });
  return (
    <details>
      <summary className="cursor-pointer text-sm font-semibold text-violet-700">
        Edit details, maintenance or lifecycle status
      </summary>
      <form
        className="asset-form-grid mt-4"
        onSubmit={(e) => {
          e.preventDefault();
          mutation.mutate();
        }}
      >
        {[
          "name",
          "serial_number",
          "brand",
          "model",
          "location",
          "purchase_date",
          "purchase_cost",
          "warranty_expiry",
          "description",
        ].map((k) => (
          <Field
            key={k}
            label={k.replace(/_/g, " ")}
            value={form[k]}
            onChange={(v) => setForm({ ...form, [k]: v })}
            required={k === "name"}
            type={
              k === "purchase_cost"
                ? "number"
                : k.includes("date") || k === "warranty_expiry"
                  ? "date"
                  : "text"
            }
          />
        ))}
        <label className="asset-form-field">
          Physical condition
          <select
            value={form.condition}
            onChange={(e) => setForm({ ...form, condition: e.target.value })}
          >
            {["New", "Good", "Fair", "Poor", "Damaged", "Lost"].map((s) => (
              <option key={s}>{s}</option>
            ))}
          </select>
        </label>
        {!["Assigned", "Pending Inspection"].includes(asset.status) && (
          <label className="asset-form-field">
            Lifecycle status
            <select
              value={form.status}
              onChange={(e) => setForm({ ...form, status: e.target.value })}
            >
              {[
                "Available",
                "Under Repair",
                "Lost",
                "Damaged",
                "Retired",
                "Disposed",
              ].map((s) => (
                <option key={s}>{s}</option>
              ))}
            </select>
          </label>
        )}
        <div className="asset-form-grid">
          {[
            "supplier",
            "invoice_number",
            "asset_value",
            "department",
            "responsible_person",
            "insurance_number",
            "insurance_expiry",
            "chassis_number",
            "engine_number",
            "roadworthiness_expiry",
            "maintenance_due",
            "replacement_due",
            "specifications",
            "notes",
          ].map((key) => {
            let values: Record<string, unknown> = {};
            try {
              values = JSON.parse(extra);
            } catch {}
            return (
              <Field
                key={key}
                label={
                  (
                    {
                      inspection_approver_id: "Inspection approver",
                      recovery_approver_id: "Recovery / Finance approver",
                      exception_approver_id: "Exception approver",
                    } as Record<string, string>
                  )[key] || key.replace(/_/g, " ")
                }
                type={
                  key.endsWith("expiry") || key.endsWith("_due")
                    ? "date"
                    : "text"
                }
                value={String(values[key] ?? "")}
                onChange={(v) =>
                  setExtra(JSON.stringify({ ...values, [key]: v }))
                }
              />
            );
          })}
          <CustomFieldsEditor
            value={JSON.stringify(
              (
                JSON.parse(extra || "{}") as {
                  custom_fields?: Record<string, string>;
                }
              ).custom_fields || {},
            )}
            onChange={(value) =>
              setExtra(
                JSON.stringify({
                  ...JSON.parse(extra || "{}"),
                  custom_fields: JSON.parse(value),
                }),
              )
            }
          />
        </div>
        <Button disabled={mutation.isPending}>Save asset details</Button>
      </form>
    </details>
  );
}
function CustomFieldsEditor({
  value,
  onChange,
  label = "Custom fields",
}: {
  value: string;
  onChange: (value: string) => void;
  label?: string;
}) {
  let entries: [string, string][] = [];
  try {
    entries = Object.entries(JSON.parse(value || "{}")).map(([k, v]) => [
      k,
      String(v ?? ""),
    ]);
  } catch {
    /* Keep the last valid fields visible. */
  }
  const save = (next: [string, string][]) =>
    onChange(JSON.stringify(Object.fromEntries(next)));
  return (
    <fieldset className="asset-accessories">
      <legend>{label}</legend>
      {entries.map(([key, val], index) => (
        <div className="asset-form-columns" key={index}>
          <Input
            aria-label={`${label} name ${index + 1}`}
            value={key}
            onChange={(e) =>
              save(
                entries.map((pair, i) =>
                  i === index ? [e.target.value, pair[1]] : pair,
                ),
              )
            }
          />
          <div className="flex gap-2">
            <Input
              aria-label={`${label} value ${index + 1}`}
              value={val}
              onChange={(e) =>
                save(
                  entries.map((pair, i) =>
                    i === index ? [pair[0], e.target.value] : pair,
                  ),
                )
              }
            />
            <Button
              type="button"
              variant="outline"
              aria-label={`Remove ${key || "field"}`}
              onClick={() => save(entries.filter((_, i) => i !== index))}
            >
              ×
            </Button>
          </div>
        </div>
      ))}
      <Button
        type="button"
        variant="outline"
        onClick={() => save([...entries, [`Field ${entries.length + 1}`, ""]])}
      >
        Add field
      </Button>
    </fieldset>
  );
}
