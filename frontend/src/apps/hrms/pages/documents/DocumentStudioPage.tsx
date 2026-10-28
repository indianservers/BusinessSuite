import { useSearchParams } from "react-router-dom";
import {
  Suspense,
  lazy,
  cloneElement,
  forwardRef,
  useEffect,
  useId,
  useRef,
  useState,
  type ReactElement,
  type TextareaHTMLAttributes,
} from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Award,
  Download,
  Eye,
  FileText,
  Plus,
  RefreshCw,
  Save,
  Copy,
  Upload,
} from "lucide-react";
import { api } from "@/services/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { toast } from "@/hooks/use-toast";

type CustomField = {
  key: string;
  label: string;
  type: "text" | "multiline" | "date" | "number";
  required: boolean;
  default: string;
};
type Template = {
  id?: number;
  name: string;
  document_type: string;
  kind: string;
  orientation: string;
  recipient_scope: string;
  title: string;
  body: string;
  custom_fields: CustomField[];
  letterhead_id: number | null;
  is_active: boolean;
  version?: number;
};
type Head = {
  id?: number;
  name: string;
  header_text: string;
  footer_text: string;
  accent_color: string;
  show_company_header: boolean;
  logo_asset_id: number | null;
  background_asset_id: number | null;
  signature_asset_id: number | null;
  signatory_name: string;
  signatory_title: string;
  top_margin_mm: number;
  bottom_margin_mm: number;
  is_active: boolean;
  version?: number;
};
type Issued = {
  id: number;
  reference: string;
  recipient_name: string;
  title: string;
  status: string;
  issue_date: string;
  template_version: number;
  revoke_reason?: string;
};
const PdfPreview = lazy(() => import("@/components/PdfPreview"));
const base = "/documents/studio";
const blankTemplate: Template = {
  name: "",
  document_type: "Letter",
  kind: "letter",
  orientation: "portrait",
  recipient_scope: "both",
  title: "",
  body: "Dear {{recipient.name}},\n\n",
  custom_fields: [],
  letterhead_id: null,
  is_active: true,
};
const blankHead: Head = {
  name: "",
  header_text: "",
  footer_text: "",
  accent_color: "#173b56",
  show_company_header: true,
  logo_asset_id: null,
  background_asset_id: null,
  signature_asset_id: null,
  signatory_name: "",
  signatory_title: "Authorized Signatory",
  top_margin_mm: 44,
  bottom_margin_mm: 25,
  is_active: true,
};
const selectClass =
  "h-10 w-full rounded-md border border-input bg-background px-3 text-sm";
const panelClass = "rounded-xl border bg-card p-5 shadow-sm";
const Textarea = forwardRef<
  HTMLTextAreaElement,
  TextareaHTMLAttributes<HTMLTextAreaElement>
>((props, ref) => (
  <textarea
    ref={ref}
    {...props}
    className="min-h-24 w-full rounded-md border border-input bg-background px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
  />
));
Textarea.displayName = "StudioTextarea";
const today = () => new Date().toLocaleDateString("en-CA");
async function errorText(error: unknown) {
  let detail = (error as { response?: { data?: { detail?: unknown } | Blob } })
    ?.response?.data;
  if (detail instanceof Blob) {
    try {
      detail = JSON.parse(await detail.text());
    } catch {
      return "Unable to generate PDF";
    }
  }
  const value = (detail as { detail?: unknown })?.detail;
  return typeof value === "string"
    ? value
    : Array.isArray(value)
      ? value
          .map((v) => `${v.loc?.slice(-1)?.[0] || "Field"}: ${v.msg}`)
          .join("; ")
      : "Request failed. Please try again.";
}
function Field({
  label,
  children,
}: {
  label: string;
  children: ReactElement<{ id?: string }>;
}) {
  const id = useId();
  return (
    <div className="grid gap-2 text-sm">
      <label htmlFor={id} className="font-medium">
        {label}
      </label>
      {cloneElement(children, { id })}
    </div>
  );
}

export default function DocumentStudioPage() {
  const qc = useQueryClient();
  const [params] = useSearchParams();
  const [tab, setTab] = useState(() => params.get("tab") === "templates" ? "Templates" : params.get("tab") === "letterheads" ? "Letterheads" : "Generate");
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");
  const [templateId, setTemplateId] = useState("");
  const [headId, setHeadId] = useState("");
  const [kind, setKind] = useState("employee");
  const [search, setSearch] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [recipientId, setRecipientId] = useState("");
  const [issueDate, setIssueDate] = useState(today);
  const [variables, setVariables] = useState<Record<string, string>>({});
  const [preview, setPreview] = useState("");
  const [previewFile, setPreviewFile] = useState<Blob | null>(null);
  const [previewKey, setPreviewKey] = useState("");
  const [requestKey, setRequestKey] = useState(() => crypto.randomUUID());
  const [editTemplate, setEditTemplate] = useState<Template | null>(null);
  const [editHead, setEditHead] = useState<Head | null>(null);
  const [historySearch, setHistorySearch] = useState("");
  const [historyPage, setHistoryPage] = useState(0);
  const [revoke, setRevoke] = useState<Issued | null>(null);
  const [reason, setReason] = useState("");
  const bodyRef = useRef<HTMLTextAreaElement>(null);
  const meta = useQuery({
    queryKey: ["studio", "metadata"],
    queryFn: async () => (await api.get(`${base}/metadata`)).data,
  });
  const templates = useQuery<Template[]>({
    queryKey: ["studio", "templates"],
    queryFn: async () => (await api.get(`${base}/templates`)).data,
  });
  const heads = useQuery<Head[]>({
    queryKey: ["studio", "letterheads"],
    queryFn: async () => (await api.get(`${base}/letterheads`)).data,
  });
  const recipients = useQuery<{ id: number; name: string; detail: string }[]>({
    queryKey: ["studio", "recipients", kind, debouncedSearch],
    queryFn: async () =>
      (
        await api.get(`${base}/recipients`, {
          params: { kind, q: debouncedSearch },
        })
      ).data,
    enabled: tab === "Generate" && !!meta.data,
  });
  const history = useQuery<{ total: number; items: Issued[] }>({
    queryKey: ["studio", "issued", historySearch, historyPage],
    queryFn: async () =>
      (
        await api.get(`${base}/issued`, {
          params: { q: historySearch, skip: historyPage * 30 },
        })
      ).data,
    enabled: tab === "Issued",
  });
  const template = templates.data?.find((t) => String(t.id) === templateId);
  const head = heads.data?.find((h) => String(h.id) === headId);
  const payload = {
    template_id: template?.id,
    template_version: template?.version,
    letterhead_id: head?.id,
    letterhead_version: head?.version,
    recipient_type: kind,
    recipient_id: Number(recipientId),
    issue_date: issueDate,
    variables,
    request_key: requestKey,
  };
  const payloadKey = JSON.stringify(payload);
  useEffect(() => {
    const timer = setTimeout(() => setDebouncedSearch(search), 300);
    return () => clearTimeout(timer);
  }, [search]);
  useEffect(() => {
    if (preview) return () => URL.revokeObjectURL(preview);
  }, [preview]);
  useEffect(() => {
    setPreview("");
    setPreviewFile(null);
    setPreviewKey("");
    setRequestKey(crypto.randomUUID());
  }, [templateId, headId, kind, recipientId, issueDate, variables]);
  async function run(action: () => Promise<void>) {
    if (busy) return;
    setBusy(true);
    setNotice("");
    try {
      await action();
    } catch (error) {
      const message = await errorText(error);
      setNotice(message);
      toast({
        title: "Action could not be completed",
        description: message,
        variant: "destructive",
      });
    } finally {
      setBusy(false);
    }
  }
  async function refresh() {
    await qc.invalidateQueries({ queryKey: ["studio"] });
  }
  async function download(document: Issued) {
    const response = await api.get(`${base}/issued/${document.id}/pdf`, {
      responseType: "blob",
    });
    const url = URL.createObjectURL(response.data);
    const anchor = window.document.createElement("a");
    anchor.href = url;
    anchor.download = `${document.reference}.pdf`;
    anchor.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  function selectTemplate(value: string) {
    setTemplateId(value);
    const item = templates.data?.find((t) => String(t.id) === value);
    setVariables(
      Object.fromEntries(
        (item?.custom_fields || []).map((f) => [f.key, f.default]),
      ),
    );
    if (item?.letterhead_id) setHeadId(String(item.letterhead_id));
    if (item?.recipient_scope !== "both" && item?.recipient_scope !== kind) {
      setKind(item?.recipient_scope || "employee");
      setRecipientId("");
    }
  }
  async function saveTemplate() {
    if (!editTemplate) return;
    const { id, ...data } = editTemplate;
    await api.request({
      method: id ? "put" : "post",
      url: `${base}/templates${id ? `/${id}` : ""}`,
      data,
    });
    setEditTemplate(null);
    await refresh();
    toast({ title: "Template saved" });
  }
  async function saveHead() {
    if (!editHead) return;
    const { id, ...data } = editHead;
    await api.request({
      method: id ? "put" : "post",
      url: `${base}/letterheads${id ? `/${id}` : ""}`,
      data,
    });
    setEditHead(null);
    await refresh();
    toast({ title: "Letterhead saved" });
  }
  function insertPlaceholder(key: string) {
    if (!editTemplate) return;
    const field = bodyRef.current;
    const token = `{{${key}}}`;
    const start = field?.selectionStart ?? editTemplate.body.length;
    const end = field?.selectionEnd ?? start;
    setEditTemplate({
      ...editTemplate,
      body:
        editTemplate.body.slice(0, start) +
        token +
        editTemplate.body.slice(end),
    });
    requestAnimationFrame(() => {
      field?.focus();
      field?.setSelectionRange(start + token.length, start + token.length);
    });
  }
  const failed = meta.isError || templates.isError || heads.isError;
  return (
    <div className="mx-auto max-w-7xl space-y-6 p-4 md:p-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="flex items-center gap-2 text-2xl font-semibold">
            <FileText className="h-6 w-6" />
            Letters & Certificates
          </h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Create documents from live records, reusable templates and your
            company letterheads.
          </p>
        </div>
        <Button
          variant="outline"
          disabled={busy}
          onClick={() => void run(refresh)}
        >
          <RefreshCw className="mr-2 h-4 w-4" />
          Refresh
        </Button>
      </div>
      {notice && (
        <div
          role="alert"
          className="rounded-lg border border-destructive p-3 text-sm text-destructive"
        >
          {notice}
        </div>
      )}
      {failed ? (
        <div role="alert" className={panelClass}>
          Unable to load Document Studio. Check your access and retry using
          Refresh.
        </div>
      ) : meta.isPending ? (
        <p role="status">Loading Document Studio…</p>
      ) : (
        <>
          <div
            className="flex flex-wrap gap-2"
            role="tablist"
            aria-label="Document studio sections"
          >
            {[
              "Generate",
              ...(meta.data?.can_edit_templates
                ? ["Templates", "Letterheads"]
                : []),
              "Issued",
            ].map((name) => (
              <Button
                key={name}
                role="tab"
                aria-selected={tab === name}
                variant={tab === name ? "default" : "outline"}
                onClick={() => setTab(name)}
              >
                {name}
              </Button>
            ))}
          </div>
          {!templates.isPending && !templates.data?.length && (
            <div className={panelClass}>
              <h2 className="font-semibold">Set up your document studio</h2>
              <p className="my-2 text-sm text-muted-foreground">
                Add 12 editable letter and certificate templates and a
                letterhead using your company profile. Review the wording and
                upload your official artwork before issuing documents.
              </p>
              {meta.data?.can_edit_templates && (
                <Button
                  disabled={busy}
                  onClick={() =>
                    void run(async () => {
                      await api.post(`${base}/initialize`);
                      await refresh();
                    })
                  }
                >
                  <Plus className="mr-2 h-4 w-4" />
                  Add starter templates
                </Button>
              )}
            </div>
          )}
          {tab === "Generate" && (
            <div className="grid gap-5 lg:grid-cols-2">
              <section className={panelClass}>
                <h2 className="mb-4 font-semibold">Prepare a document</h2>
                <form
                  className="space-y-4"
                  onSubmit={(event) => {
                    event.preventDefault();
                    void run(async () => {
                      const response = await api.post(
                        `${base}/preview`,
                        payload,
                        { responseType: "blob" },
                      );
                      setPreview(URL.createObjectURL(response.data));
                      setPreviewFile(response.data);
                      setPreviewKey(payloadKey);
                    });
                  }}
                >
                  <Field label="Template">
                    <select
                      aria-label="Template"
                      className={selectClass}
                      required
                      value={templateId}
                      onChange={(e) => selectTemplate(e.target.value)}
                    >
                      <option value="">Choose a template</option>
                      {templates.data
                        ?.filter((t) => t.is_active)
                        .map((t) => (
                          <option key={t.id} value={t.id}>
                            {t.name} · v{t.version}
                          </option>
                        ))}
                    </select>
                  </Field>
                  <Field label="Letterhead">
                    <select
                      aria-label="Letterhead"
                      className={selectClass}
                      required
                      value={headId}
                      onChange={(e) => setHeadId(e.target.value)}
                    >
                      <option value="">Choose a letterhead</option>
                      {heads.data
                        ?.filter((h) => h.is_active)
                        .map((h) => (
                          <option key={h.id} value={h.id}>
                            {h.name} · v{h.version}
                          </option>
                        ))}
                    </select>
                  </Field>
                  <div className="grid gap-4 sm:grid-cols-2">
                    <Field label="Recipient source">
                      <select
                        aria-label="Recipient source"
                        className={selectClass}
                        value={kind}
                        onChange={(e) => {
                          setKind(e.target.value);
                          setRecipientId("");
                        }}
                      >
                        <option
                          value="employee"
                          disabled={template?.recipient_scope === "application"}
                        >
                          Employee / onboarded intern
                        </option>
                        {meta.data?.can_use_applications && (
                          <option
                            value="application"
                            disabled={template?.recipient_scope === "employee"}
                          >
                            Internship applicant
                          </option>
                        )}
                      </select>
                    </Field>
                    <Field label="Issue date">
                      <Input
                        aria-label="Issue date"
                        type="date"
                        required
                        value={issueDate}
                        onChange={(e) => setIssueDate(e.target.value)}
                      />
                    </Field>
                  </div>
                  <Field label="Find recipient">
                    <Input
                      placeholder="Search name or reference…"
                      value={search}
                      onChange={(e) => {
                        setSearch(e.target.value);
                        setRecipientId("");
                      }}
                    />
                  </Field>
                  <Field label="Recipient">
                    <select
                      aria-label="Recipient"
                      required
                      className={selectClass}
                      value={recipientId}
                      onChange={(e) => setRecipientId(e.target.value)}
                    >
                      <option value="">
                        {recipients.isFetching
                          ? "Loading…"
                          : "Choose a recipient"}
                      </option>
                      {recipients.data?.map((r) => (
                        <option key={r.id} value={r.id}>
                          {r.name} · {r.detail}
                        </option>
                      ))}
                    </select>
                  </Field>
                  {recipients.isError && (
                    <p role="alert" className="text-sm text-destructive">
                      Unable to load recipients. Refresh and try again.
                    </p>
                  )}
                  {template?.custom_fields.map((field) => (
                    <Field
                      key={field.key}
                      label={`${field.label}${field.required ? " *" : ""}`}
                    >
                      {field.type === "multiline" ? (
                        <Textarea
                          required={field.required}
                          maxLength={2000}
                          value={variables[field.key] || ""}
                          onChange={(e) =>
                            setVariables({
                              ...variables,
                              [field.key]: e.target.value,
                            })
                          }
                        />
                      ) : (
                        <Input
                          type={field.type === "text" ? "text" : field.type}
                          step={field.type === "number" ? "any" : undefined}
                          required={field.required}
                          maxLength={2000}
                          value={variables[field.key] || ""}
                          onChange={(e) =>
                            setVariables({
                              ...variables,
                              [field.key]: e.target.value,
                            })
                          }
                        />
                      )}
                    </Field>
                  ))}
                  <p className="text-xs text-muted-foreground">
                    Names, employment details and company details come from the
                    database. Custom fields supply approved terms and program
                    details.
                  </p>
                  <div className="flex flex-wrap gap-2">
                    <Button
                      type="submit"
                      disabled={busy || !template || !head || !recipientId}
                    >
                      <Eye className="mr-2 h-4 w-4" />
                      Preview PDF
                    </Button>
                    <Button
                      type="button"
                      variant="outline"
                      disabled={busy || !preview || previewKey !== payloadKey}
                      onClick={() =>
                        void run(async () => {
                          const result = (
                            await api.post(`${base}/issue`, payload)
                          ).data as Issued;
                          setRequestKey(crypto.randomUUID());
                          setPreview("");
                          setPreviewFile(null);
                          setPreviewKey("");
                          await qc.invalidateQueries({
                            queryKey: ["studio", "issued"],
                          });
                          toast({
                            title: `Issued ${result.reference}`,
                            description:
                              "The original data and template version have been saved.",
                          });
                          await download(result);
                        })
                      }
                    >
                      <Award className="mr-2 h-4 w-4" />
                      Issue & download
                    </Button>
                  </div>
                </form>
              </section>
              <section className={`${panelClass} min-h-[550px]`}>
                <h2 className="mb-3 font-semibold">PDF preview</h2>
                {preview && previewKey === payloadKey ? (
                  <>
                    {previewFile && (
                      <Suspense
                        fallback={<p role="status">Loading PDF viewer…</p>}
                      >
                        <PdfPreview file={previewFile} />
                      </Suspense>
                    )}
                    <a
                      className="mt-3 inline-block text-sm underline"
                      href={preview}
                      target="_blank"
                      rel="noreferrer"
                    >
                      Open preview in a new tab
                    </a>
                  </>
                ) : (
                  <div className="flex h-96 flex-col items-center justify-center gap-3 text-center text-muted-foreground">
                    <FileText className="h-14 w-14" />
                    <p>
                      Choose a template and recipient, then preview.
                      <br />
                      Previewing does not issue a document.
                    </p>
                  </div>
                )}
              </section>
            </div>
          )}
          {tab === "Templates" && (
            <div className="grid gap-5 lg:grid-cols-[280px_1fr]">
              <aside className={`${panelClass} space-y-2`}>
                <Button
                  className="w-full"
                  onClick={() =>
                    setEditTemplate(structuredClone(blankTemplate))
                  }
                >
                  <Plus className="mr-2 h-4 w-4" />
                  New template
                </Button>
                {templates.data?.map((t) => (
                  <button
                    key={t.id}
                    className="w-full rounded border p-3 text-left text-sm hover:bg-muted"
                    onClick={() => setEditTemplate(structuredClone(t))}
                  >
                    <strong className="block">{t.name}</strong>
                    <span className="text-xs text-muted-foreground">
                      {t.kind} · v{t.version} ·{" "}
                      {t.is_active ? "Active" : "Archived"}
                    </span>
                  </button>
                ))}
              </aside>
              <section className={panelClass}>
                {!editTemplate ? (
                  <p>Select a template to edit, or create one.</p>
                ) : (
                  <form
                    className="space-y-4"
                    onSubmit={(e) => {
                      e.preventDefault();
                      void run(saveTemplate);
                    }}
                  >
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <h2 className="font-semibold">
                        {editTemplate.id ? "Edit template" : "New template"}
                      </h2>
                      <Button
                        type="button"
                        variant="outline"
                        onClick={() =>
                          setEditTemplate({
                            ...editTemplate,
                            id: undefined,
                            version: undefined,
                            name: `${editTemplate.name} copy`.slice(0, 150),
                          })
                        }
                      >
                        <Copy className="mr-2 h-4 w-4" />
                        Duplicate
                      </Button>
                    </div>
                    <Field label="Template name">
                      <Input
                        required
                        maxLength={150}
                        value={editTemplate.name}
                        onChange={(e) =>
                          setEditTemplate({
                            ...editTemplate,
                            name: e.target.value,
                          })
                        }
                      />
                    </Field>
                    <div className="grid gap-4 sm:grid-cols-3">
                      <Field label="Kind">
                        <select
                          className={selectClass}
                          value={editTemplate.kind}
                          onChange={(e) =>
                            setEditTemplate({
                              ...editTemplate,
                              kind: e.target.value,
                            })
                          }
                        >
                          <option value="letter">Letter</option>
                          <option value="certificate">Certificate</option>
                        </select>
                      </Field>
                      <Field label="Orientation">
                        <select
                          className={selectClass}
                          value={editTemplate.orientation}
                          onChange={(e) =>
                            setEditTemplate({
                              ...editTemplate,
                              orientation: e.target.value,
                            })
                          }
                        >
                          <option value="portrait">Portrait</option>
                          <option value="landscape">Landscape</option>
                        </select>
                      </Field>
                      <Field label="Recipients">
                        <select
                          className={selectClass}
                          value={editTemplate.recipient_scope}
                          onChange={(e) =>
                            setEditTemplate({
                              ...editTemplate,
                              recipient_scope: e.target.value,
                            })
                          }
                        >
                          <option value="both">Employees & applicants</option>
                          <option value="employee">Employees only</option>
                          <option value="application">Applicants only</option>
                        </select>
                      </Field>
                    </div>
                    <Field label="Document category">
                      <Input
                        required
                        maxLength={80}
                        value={editTemplate.document_type}
                        onChange={(e) =>
                          setEditTemplate({
                            ...editTemplate,
                            document_type: e.target.value,
                          })
                        }
                      />
                    </Field>
                    <Field label="Default letterhead">
                      <select
                        className={selectClass}
                        value={editTemplate.letterhead_id || ""}
                        onChange={(e) =>
                          setEditTemplate({
                            ...editTemplate,
                            letterhead_id: Number(e.target.value) || null,
                          })
                        }
                      >
                        <option value="">Choose at generation</option>
                        {heads.data?.map((h) => (
                          <option key={h.id} value={h.id}>
                            {h.name}
                          </option>
                        ))}
                      </select>
                    </Field>
                    <Field label="Document title (placeholders supported)">
                      <Input
                        required
                        maxLength={250}
                        value={editTemplate.title}
                        onChange={(e) =>
                          setEditTemplate({
                            ...editTemplate,
                            title: e.target.value,
                          })
                        }
                      />
                    </Field>
                    <Field label="Body · plain text and {{group.field}} placeholders">
                      <Textarea
                        ref={bodyRef}
                        required
                        rows={12}
                        maxLength={20000}
                        value={editTemplate.body}
                        onChange={(e) =>
                          setEditTemplate({
                            ...editTemplate,
                            body: e.target.value,
                          })
                        }
                      />
                    </Field>
                    <details className="rounded border p-3">
                      <summary className="cursor-pointer text-sm font-medium">
                        Insert database placeholder
                      </summary>
                      <div className="mt-3 flex flex-wrap gap-2">
                        {[
                          ...(meta.data?.placeholders || []),
                          ...editTemplate.custom_fields.map(
                            (f) => `custom.${f.key}`,
                          ),
                        ].map((key: string) => (
                          <button
                            type="button"
                            className="rounded border px-2 py-1 font-mono text-xs hover:bg-muted"
                            key={key}
                            onClick={() => insertPlaceholder(key)}
                          >{`{{${key}}}`}</button>
                        ))}
                      </div>
                    </details>
                    <div className="space-y-3">
                      <div className="flex items-center justify-between">
                        <Label>Custom placeholders</Label>
                        <Button
                          type="button"
                          size="sm"
                          variant="outline"
                          disabled={editTemplate.custom_fields.length >= 20}
                          onClick={() =>
                            setEditTemplate({
                              ...editTemplate,
                              custom_fields: [
                                ...editTemplate.custom_fields,
                                {
                                  key: `field_${editTemplate.custom_fields.length + 1}`,
                                  label: "New field",
                                  type: "text",
                                  required: true,
                                  default: "",
                                },
                              ],
                            })
                          }
                        >
                          <Plus className="mr-1 h-4 w-4" />
                          Add field
                        </Button>
                      </div>
                      {editTemplate.custom_fields.map((field, index) => {
                        const change = (patch: Partial<CustomField>) =>
                          setEditTemplate({
                            ...editTemplate,
                            custom_fields: editTemplate.custom_fields.map(
                              (f, i) => (i === index ? { ...f, ...patch } : f),
                            ),
                          });
                        return (
                          <div
                            className="grid gap-3 rounded border p-3 sm:grid-cols-2"
                            key={index}
                          >
                            <Field label="Key · custom.key">
                              <Input
                                required
                                pattern="[a-z][a-z0-9_]{0,49}"
                                value={field.key}
                                onChange={(e) =>
                                  change({ key: e.target.value })
                                }
                              />
                            </Field>
                            <Field label="Label">
                              <Input
                                required
                                value={field.label}
                                onChange={(e) =>
                                  change({ label: e.target.value })
                                }
                              />
                            </Field>
                            <Field label="Input type">
                              <select
                                className={selectClass}
                                value={field.type}
                                onChange={(e) =>
                                  change({
                                    type: e.target.value as CustomField["type"],
                                  })
                                }
                              >
                                {["text", "multiline", "date", "number"].map(
                                  (type) => (
                                    <option key={type}>{type}</option>
                                  ),
                                )}
                              </select>
                            </Field>
                            <Field label="Default value">
                              <Input
                                value={field.default}
                                onChange={(e) =>
                                  change({ default: e.target.value })
                                }
                              />
                            </Field>
                            <label className="flex items-center gap-2 text-sm">
                              <input
                                type="checkbox"
                                checked={field.required}
                                onChange={(e) =>
                                  change({ required: e.target.checked })
                                }
                              />
                              Required
                            </label>
                            <Button
                              type="button"
                              variant="ghost"
                              onClick={() =>
                                setEditTemplate({
                                  ...editTemplate,
                                  custom_fields:
                                    editTemplate.custom_fields.filter(
                                      (_, i) => i !== index,
                                    ),
                                })
                              }
                            >
                              Remove field
                            </Button>
                          </div>
                        );
                      })}
                    </div>
                    <label className="flex items-center gap-2 text-sm">
                      <input
                        type="checkbox"
                        checked={editTemplate.is_active}
                        onChange={(e) =>
                          setEditTemplate({
                            ...editTemplate,
                            is_active: e.target.checked,
                          })
                        }
                      />
                      Active template
                    </label>
                    <p className="text-xs text-muted-foreground">
                      Saving creates a new version. Previously issued documents
                      keep their original wording.
                    </p>
                    <Button disabled={busy}>
                      <Save className="mr-2 h-4 w-4" />
                      Save template
                    </Button>
                  </form>
                )}
              </section>
            </div>
          )}
          {tab === "Letterheads" && (
            <div className="grid gap-5 lg:grid-cols-[280px_1fr]">
              <aside className={`${panelClass} space-y-2`}>
                <Button
                  className="w-full"
                  onClick={() => setEditHead(structuredClone(blankHead))}
                >
                  <Plus className="mr-2 h-4 w-4" />
                  New letterhead
                </Button>
                {heads.data?.map((h) => (
                  <button
                    key={h.id}
                    className="w-full rounded border p-3 text-left text-sm hover:bg-muted"
                    onClick={() => setEditHead(structuredClone(h))}
                  >
                    <strong className="block">{h.name}</strong>
                    <span className="text-xs text-muted-foreground">
                      v{h.version} · {h.is_active ? "Active" : "Archived"}
                    </span>
                  </button>
                ))}
              </aside>
              <section className={panelClass}>
                {!editHead ? (
                  <p>
                    Select a letterhead to configure your official branding.
                  </p>
                ) : (
                  <form
                    className="space-y-4"
                    onSubmit={(e) => {
                      e.preventDefault();
                      void run(saveHead);
                    }}
                  >
                    <h2 className="font-semibold">Letterhead settings</h2>
                    <p className="text-sm text-muted-foreground">
                      Company name, address and contact information come from
                      your company profile. Upload your official letterhead as a
                      PDF, PNG or JPEG, or use a logo with the company header.
                    </p>
                    {meta.data?.has_company_logo && (
                      <Button
                        type="button"
                        variant="outline"
                        disabled={busy}
                        onClick={() =>
                          void run(async () => {
                            const result = await api.post(
                              `${base}/company-logo`,
                            );
                            setEditHead((current) =>
                              current
                                ? { ...current, logo_asset_id: result.data.id }
                                : current,
                            );
                          })
                        }
                      >
                        Use logo from company profile
                      </Button>
                    )}
                    <Field label="Letterhead name">
                      <Input
                        required
                        maxLength={150}
                        value={editHead.name}
                        onChange={(e) =>
                          setEditHead({ ...editHead, name: e.target.value })
                        }
                      />
                    </Field>
                    <div className="grid gap-4 sm:grid-cols-3">
                      {(
                        [
                          ["logo_asset_id", "Logo", "logo"],
                          [
                            "background_asset_id",
                            "Full-page artwork",
                            "background",
                          ],
                          ["signature_asset_id", "Signature", "signature"],
                        ] as const
                      ).map(([key, label, assetKind]) => (
                        <div className="space-y-2 rounded border p-3" key={key}>
                          <Label>{label}</Label>
                          <p className="text-xs text-muted-foreground">
                            {editHead[key]
                              ? `Saved artwork #${editHead[key]}`
                              : "No artwork"}
                          </p>
                          <label className="flex cursor-pointer items-center gap-2 text-sm text-primary">
                            <Upload className="h-4 w-4" />
                            Upload
                            <input
                              aria-label={`Upload ${label}`}
                              className="sr-only"
                              type="file"
                              accept={
                                assetKind === "background"
                                  ? "application/pdf,image/png,image/jpeg"
                                  : "image/png,image/jpeg"
                              }
                              disabled={busy}
                              onChange={(event) => {
                                const file = event.target.files?.[0];
                                event.target.value = "";
                                if (file)
                                  void run(async () => {
                                    const form = new FormData();
                                    form.append("file", file);
                                    const result = await api.post(
                                      `${base}/assets?kind=${assetKind}`,
                                      form,
                                    );
                                    setEditHead((current) =>
                                      current
                                        ? { ...current, [key]: result.data.id }
                                        : current,
                                    );
                                  });
                              }}
                            />
                          </label>
                          {editHead[key] && (
                            <Button
                              type="button"
                              size="sm"
                              variant="ghost"
                              onClick={() =>
                                setEditHead({ ...editHead, [key]: null })
                              }
                            >
                              Remove
                            </Button>
                          )}
                        </div>
                      ))}
                    </div>
                    <p className="text-xs text-muted-foreground">
                      PNG or JPEG, up to 2 MB; full-page artwork also accepts a
                      single-page PDF. Use artwork matching the document
                      orientation. Artwork and signatures are stored securely in
                      the database.
                    </p>
                    <label className="flex items-center gap-2 text-sm">
                      <input
                        type="checkbox"
                        checked={editHead.show_company_header}
                        onChange={(e) =>
                          setEditHead({
                            ...editHead,
                            show_company_header: e.target.checked,
                          })
                        }
                      />
                      Show company header (turn off if included in full-page
                      artwork)
                    </label>
                    <Field label="Header text (blank uses company address)">
                      <Textarea
                        maxLength={1000}
                        value={editHead.header_text}
                        onChange={(e) =>
                          setEditHead({
                            ...editHead,
                            header_text: e.target.value,
                          })
                        }
                      />
                    </Field>
                    <Field label="Footer text">
                      <Textarea
                        maxLength={1000}
                        value={editHead.footer_text}
                        onChange={(e) =>
                          setEditHead({
                            ...editHead,
                            footer_text: e.target.value,
                          })
                        }
                      />
                    </Field>
                    <div className="grid gap-4 sm:grid-cols-2">
                      <Field label="Signatory name">
                        <Input
                          maxLength={150}
                          value={editHead.signatory_name}
                          onChange={(e) =>
                            setEditHead({
                              ...editHead,
                              signatory_name: e.target.value,
                            })
                          }
                        />
                      </Field>
                      <Field label="Signatory title">
                        <Input
                          required
                          maxLength={150}
                          value={editHead.signatory_title}
                          onChange={(e) =>
                            setEditHead({
                              ...editHead,
                              signatory_title: e.target.value,
                            })
                          }
                        />
                      </Field>
                    </div>
                    <div className="grid gap-4 sm:grid-cols-3">
                      <Field label="Accent colour">
                        <Input
                          type="color"
                          value={editHead.accent_color}
                          onChange={(e) =>
                            setEditHead({
                              ...editHead,
                              accent_color: e.target.value,
                            })
                          }
                        />
                      </Field>
                      <Field label="Top margin (mm)">
                        <Input
                          type="number"
                          min={30}
                          max={90}
                          required
                          value={editHead.top_margin_mm}
                          onChange={(e) =>
                            setEditHead({
                              ...editHead,
                              top_margin_mm: Number(e.target.value),
                            })
                          }
                        />
                      </Field>
                      <Field label="Bottom margin (mm)">
                        <Input
                          type="number"
                          min={20}
                          max={60}
                          required
                          value={editHead.bottom_margin_mm}
                          onChange={(e) =>
                            setEditHead({
                              ...editHead,
                              bottom_margin_mm: Number(e.target.value),
                            })
                          }
                        />
                      </Field>
                    </div>
                    <label className="flex items-center gap-2 text-sm">
                      <input
                        type="checkbox"
                        checked={editHead.is_active}
                        onChange={(e) =>
                          setEditHead({
                            ...editHead,
                            is_active: e.target.checked,
                          })
                        }
                      />
                      Active letterhead
                    </label>
                    <Button disabled={busy}>
                      <Save className="mr-2 h-4 w-4" />
                      Save letterhead
                    </Button>
                  </form>
                )}
              </section>
            </div>
          )}
          {tab === "Issued" && (
            <section className={`${panelClass} space-y-4`}>
              <div className="flex flex-wrap items-center justify-between gap-3">
                <h2 className="font-semibold">
                  Issued documents ({history.data?.total || 0})
                </h2>
                <Input
                  className="max-w-sm"
                  placeholder="Find recipient or reference…"
                  value={historySearch}
                  onChange={(e) => {
                    setHistorySearch(e.target.value);
                    setHistoryPage(0);
                  }}
                />
              </div>
              <p className="text-sm text-muted-foreground">
                Reprints use the data and letterhead version saved at issuance.
                Revoked copies carry a watermark.
              </p>
              {history.isError && (
                <p role="alert">
                  Unable to load issued documents. Please refresh.
                </p>
              )}
              <div className="space-y-3">
                {history.data?.items.map((item) => (
                  <article
                    key={item.id}
                    className="flex flex-wrap items-center justify-between gap-3 rounded-lg border p-4"
                  >
                    <div>
                      <h3 className="font-medium">{item.title}</h3>
                      <p className="text-sm">{item.recipient_name}</p>
                      <p className="mt-1 text-xs text-muted-foreground">
                        {item.reference} · {item.issue_date} · Template v
                        {item.template_version} · {item.status}
                      </p>
                      {item.revoke_reason && (
                        <p className="mt-1 text-sm text-destructive">
                          Revocation: {item.revoke_reason}
                        </p>
                      )}
                    </div>
                    <div className="flex gap-2">
                      <Button
                        variant="outline"
                        size="sm"
                        disabled={busy}
                        onClick={() => void run(() => download(item))}
                      >
                        <Download className="mr-2 h-4 w-4" />
                        Download
                      </Button>
                      {item.status !== "Revoked" && (
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => {
                            setRevoke(item);
                            setReason("");
                          }}
                        >
                          Revoke
                        </Button>
                      )}
                    </div>
                  </article>
                ))}
                {history.data?.total === 0 && (
                  <p className="py-10 text-center text-muted-foreground">
                    No documents issued yet.
                  </p>
                )}
              </div>
              <div className="flex justify-end gap-2">
                <Button
                  variant="outline"
                  disabled={!historyPage || history.isFetching}
                  onClick={() => setHistoryPage((p) => p - 1)}
                >
                  Previous
                </Button>
                <Button
                  variant="outline"
                  disabled={
                    history.isFetching ||
                    (historyPage + 1) * 30 >= (history.data?.total || 0)
                  }
                  onClick={() => setHistoryPage((p) => p + 1)}
                >
                  Next
                </Button>
              </div>
            </section>
          )}
        </>
      )}
      {revoke && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
          role="dialog"
          aria-modal="true"
          aria-labelledby="revoke-title"
        >
          <form
            className="w-full max-w-md space-y-4 rounded-xl bg-background p-6"
            onSubmit={(e) => {
              e.preventDefault();
              void run(async () => {
                await api.post(`${base}/issued/${revoke.id}/revoke`, {
                  reason,
                });
                setRevoke(null);
                await refresh();
              });
            }}
          >
            <h2 id="revoke-title" className="font-semibold">
              Revoke {revoke.reference}
            </h2>
            <p className="text-sm">
              The original remains in the register with its reason and a revoked
              watermark.
            </p>
            <Field label="Reason">
              <Textarea
                autoFocus
                required
                minLength={5}
                maxLength={1000}
                value={reason}
                onChange={(e) => setReason(e.target.value)}
              />
            </Field>
            <div className="flex justify-end gap-2">
              <Button
                type="button"
                variant="outline"
                disabled={busy}
                onClick={() => setRevoke(null)}
              >
                Cancel
              </Button>
              <Button
                variant="destructive"
                disabled={busy || reason.trim().length < 5}
              >
                Revoke document
              </Button>
            </div>
          </form>
        </div>
      )}
    </div>
  );
}
