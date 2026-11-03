import { recordPreviewProps } from "@/components/RecordQuickPreview";
import { useEffect, useRef, useState } from "react";
import * as Dialog from "@radix-ui/react-dialog";
import {
  ArrowRight,
  Check,
  Download,
  FileSpreadsheet,
  Loader2,
  Upload,
  X,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { api } from "@/services/api";
import {
  csvText,
  downloadBlob,
  fieldLabel,
  inspectFile,
  mapRows,
  mappedFile,
  suggestMapping,
  transferError,
  type ImportResult,
  type MappedImport,
  type TransferField,
  type TransferIssue,
  type TransferTable,
} from "./transfer";
import "./transfer.css";

export type ImportWizardProps = {
  title?: string;
  label?: string;
  description?: string;
  fields: TransferField[] | (() => Promise<TransferField[]>);
  onImport: (data: MappedImport) => Promise<ImportResult | void>;
  maxRows?: number;
  maxBytes?: number;
  confirmLabel?: string;
  disabled?: boolean;
  autoOpen?: boolean;
  onClose?: () => void;
};
export default function ImportWizard({
  title = "Import data",
  label = "Import",
  description = "Match your spreadsheet columns, review the data, then confirm.",
  fields: supplied,
  onImport,
  maxRows = 5000,
  maxBytes = 3 * 1024 * 1024,
  confirmLabel = "Import rows",
  disabled,
  autoOpen,
  onClose,
}: ImportWizardProps) {
  const [open, setOpen] = useState(false),
    [step, setStep] = useState(0),
    [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  const [fields, setFields] = useState<TransferField[]>([]),
    [file, setFile] = useState<File>(),
    [table, setTable] = useState<TransferTable>(),
    [mapping, setMapping] = useState<Record<string, string>>({}),
    [result, setResult] = useState<ImportResult>(),
    [serverIssues, setServerIssues] = useState<TransferIssue[]>([]);
  const [availableSheets, setAvailableSheets] = useState<string[]>([]);
  const input = useRef<HTMLInputElement>(null),
    request = useRef(0);
  const prepared = table
    ? mapRows(table, fields, mapping)
    : { rows: [], issues: [] };
  const missing = fields.filter(
    (f) => f.required && !mapping[f.key] && f.default === undefined,
  );
  const mappedSources = Object.values(mapping).filter(Boolean),
    duplicates = mappedSources.length !== new Set(mappedSources).size;
  const issues = [...prepared.issues, ...serverIssues];
  async function begin() {
    setOpen(true);
    setStep(0);
    setTable(undefined);
    setAvailableSheets([]);
    setFile(undefined);
    setResult(undefined);
    setMapping({});
    setServerIssues([]);
    setError("");
    setBusy(true);
    try {
      setFields(typeof supplied === "function" ? await supplied() : supplied);
    } catch (e) {
      setError(transferError(e));
    } finally {
      setBusy(false);
    }
  }
  useEffect(() => {
    if (autoOpen) void begin();
  }, []);
  function close() {
    setOpen(false);
    onClose?.();
  }
  async function read(selected: File, sheet = "", headerRow = 1) {
    const token = ++request.current;
    setError("");
    setTable(undefined);
    setResult(undefined);
    setServerIssues([]);
    setStep(0);
    setFile(selected);
    if (selected.size > maxBytes) {
      setError(`Choose a file up to ${(maxBytes / 1024 / 1024).toFixed(1)} MB`);
      return;
    }
    setBusy(true);
    try {
      const data = await inspectFile(selected, sheet, headerRow);
      if (token !== request.current) return;
      if (data.total > maxRows)
        throw Error(
          `Import at most ${maxRows.toLocaleString()} rows at a time`,
        );
      setAvailableSheets(data.sheets);
      setTable(data);
      setMapping(suggestMapping(data.headers, fields));
      setStep(1);
    } catch (e) {
      if (token === request.current) {
        setError(transferError(e));
        const sheets = (
          e as { response?: { data?: { detail?: { sheets?: string[] } } } }
        )?.response?.data?.detail?.sheets;
        if (sheets) setAvailableSheets(sheets);
      }
    } finally {
      if (token === request.current) setBusy(false);
    }
  }
  async function template() {
    setBusy(true);
    setError("");
    try {
      const data = new FormData();
      data.append(
        "file",
        mappedFile(
          [
            Object.fromEntries(
              fields.map((f) => [
                f.key,
                f.default ||
                  (f.type === "date"
                    ? "2026-01-01"
                    : f.type === "number"
                      ? 0
                      : f.type === "email"
                        ? "name@example.com"
                        : f.hint || `Example ${fieldLabel(f)}`),
              ]),
            ),
          ],
          "template.csv",
        ),
      );
      data.append("format", "xlsx");
      const response = await api.post("/data-transfer/export/convert", data, {
        responseType: "blob",
      });
      downloadBlob(response.data, "import-template.xlsx");
    } catch (e) {
      setError(transferError(e));
    } finally {
      setBusy(false);
    }
  }
  async function commit() {
    if (
      !table ||
      !file ||
      busy ||
      result ||
      issues.length ||
      missing.length ||
      duplicates
    )
      return;
    setBusy(true);
    setError("");
    setServerIssues([]);
    try {
      const response = await onImport({
        rows: prepared.rows,
        file: mappedFile(prepared.rows, file.name),
        filename: file.name,
        rowNumbers: table.rowNumbers,
        mapping: Object.fromEntries(
          Object.entries(mapping)
            .filter(([, source]) => source)
            .map(([target, source]) => [source, target]),
        ),
      });
      const errors = (response?.errors || []).map((e) => ({
        row: table.rowNumbers[Math.max(0, e.row - 1)] || e.row,
        error:
          e.errors?.join("; ") ||
          (typeof e.error === "string" ? e.error : JSON.stringify(e.error)) ||
          "Invalid row",
      }));
      setServerIssues(errors);
      // Partial imports must not be submitted again: keep a completion receipt and row errors.
      if (!errors.length || (response?.created || 0) > 0) {
        setResult(response || { created: prepared.rows.length });
        setStep(3);
      }
    } catch (e) {
      setError(transferError(e));
    } finally {
      setBusy(false);
    }
  }
  const changeMapping = (target: string, source: string) => {
    setMapping((v) => ({ ...v, [target]: source }));
    setServerIssues([]);
    setError("");
  };
  return (
    <>
      {!autoOpen && (
        <Button
          variant="outline"
          disabled={disabled}
          onClick={() => void begin()}
        >
          <Upload size={16} />
          {label}
        </Button>
      )}
      <Dialog.Root
        open={open}
        onOpenChange={(value) => {
          if (!busy) {
            ++request.current;
            setOpen(value);
            if (!value) onClose?.();
          }
        }}
      >
        <Dialog.Portal>
          <Dialog.Overlay className="dt-overlay" />
          <Dialog.Content
            className="dt-dialog"
            aria-describedby="dt-import-description"
          >
            <header className="dt-heading">
              <span className="dt-icon">
                <FileSpreadsheet size={24} />
              </span>
              <div>
                <Dialog.Title>{title}</Dialog.Title>
                <Dialog.Description id="dt-import-description">
                  {description}
                </Dialog.Description>
              </div>
              <Dialog.Close disabled={busy} aria-label="Close import">
                <X size={20} />
              </Dialog.Close>
            </header>
            <div className="dt-steps">
              {["Upload", "Map columns", "Review", "Complete"].map(
                (text, i) => (
                  <span
                    key={text}
                    aria-current={step === i ? "step" : undefined}
                    className={i <= step ? "active" : ""}
                  >
                    <b>{i < step ? <Check size={13} /> : i + 1}</b>
                    {text}
                  </span>
                ),
              )}
            </div>
            <div className="dt-body">
              {error && (
                <p className="dt-error" role="alert">
                  {error}
                </p>
              )}
              {busy && (
                <p role="status" className="dt-muted">
                  <Loader2 size={16} className="animate-spin" />
                  Processing…
                </p>
              )}
              {step < 3 && (
                <>
                  <div
                    className="dt-upload"
                    onDragOver={(e) => e.preventDefault()}
                    onDrop={(e) => {
                      e.preventDefault();
                      if (!busy && fields.length && e.dataTransfer.files[0])
                        void read(e.dataTransfer.files[0]);
                    }}
                  >
                    <Upload size={24} />
                    <strong>
                      {file?.name || "Drop your spreadsheet here"}
                    </strong>
                    <span>
                      Excel .xlsx, CSV, TSV or JSON · Up to{" "}
                      {maxRows.toLocaleString()} rows
                    </span>
                    <div>
                      <Button
                        disabled={busy || !fields.length}
                        variant="outline"
                        onClick={() => input.current?.click()}
                      >
                        {file ? "Choose another file" : "Choose file"}
                      </Button>
                      <Button
                        variant="ghost"
                        disabled={busy || !fields.length}
                        onClick={() => void template()}
                      >
                        <Download size={15} />
                        Excel template
                      </Button>
                    </div>
                    <input
                      ref={input}
                      hidden
                      aria-label="Choose import file"
                      type="file"
                      accept=".xlsx,.csv,.tsv,.json"
                      disabled={busy}
                      onChange={(e) => {
                        const f = e.target.files?.[0];
                        e.target.value = "";
                        if (f) void read(f);
                      }}
                    />
                  </div>
                  {table && (
                    <div className="dt-file-settings">
                      {table.sheets.length > 1 && (
                        <label>
                          Worksheet
                          <select
                            disabled={busy}
                            value={table.sheet}
                            onChange={(e) =>
                              file &&
                              void read(file, e.target.value, table.headerRow)
                            }
                          >
                            {table.sheets.map((s) => (
                              <option key={s}>{s}</option>
                            ))}
                          </select>
                        </label>
                      )}
                      <label>
                        Header row
                        <select
                          disabled={busy}
                          value={table.headerRow}
                          onChange={(e) =>
                            file &&
                            void read(file, table.sheet, Number(e.target.value))
                          }
                        >
                          {Array.from({ length: 50 }, (_, i) => (
                            <option key={i} value={i + 1}>
                              {i + 1}
                            </option>
                          ))}
                        </select>
                      </label>
                      <span>
                        {table.total.toLocaleString()} rows ·{" "}
                        {table.headers.length} columns
                      </span>
                    </div>
                  )}
                  {step === 0 && file && !busy && !table && (
                    <>
                      {availableSheets.length > 1 && (
                        <label>
                          Worksheet
                          <select
                            aria-label="Choose worksheet"
                            defaultValue=""
                            onChange={(e) => void read(file, e.target.value)}
                          >
                            <option value="" disabled>
                              Choose worksheet
                            </option>
                            {availableSheets.map((s) => (
                              <option key={s}>{s}</option>
                            ))}
                          </select>
                        </label>
                      )}
                      <label>
                        Headers below a title? Start at row{" "}
                        <select
                          aria-label="Retry header row"
                          defaultValue="1"
                          onChange={(e) =>
                            void read(file, "", Number(e.target.value))
                          }
                        >
                          {Array.from({ length: 50 }, (_, i) => (
                            <option key={i} value={i + 1}>
                              {i + 1}
                            </option>
                          ))}
                        </select>
                      </label>
                    </>
                  )}
                  {step === 1 && table && (
                    <>
                      <div className="dt-section-title">
                        <h3>Match your columns</h3>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() =>
                            setMapping(suggestMapping(table.headers, fields))
                          }
                        >
                          Auto-match
                        </Button>
                      </div>
                      <p className="dt-muted">
                        Choose the uploaded column for each destination field.
                        Unmapped columns are ignored.
                      </p>
                      <div className="dt-mapping">
                        <div className="dt-map-head">
                          <span>Our field</span>
                          <span>Your spreadsheet column</span>
                          <span>Sample value</span>
                        </div>
                        {fields.map((field) => (
                          <div className="dt-map-row" key={field.key}>
                            <label htmlFor={`dt-map-${field.key}`}>
                              {fieldLabel(field)}
                              {field.required && (
                                <b className="dt-required"> *</b>
                              )}
                              <small>
                                {field.hint || field.type || "Text"}
                              </small>
                            </label>
                            <select
                              id={`dt-map-${field.key}`}
                              value={mapping[field.key] || ""}
                              onChange={(e) =>
                                changeMapping(field.key, e.target.value)
                              }
                            >
                              <option value="">
                                {field.default !== undefined
                                  ? `Default: ${field.default}`
                                  : "Do not import"}
                              </option>
                              {table.headers.map((h) => (
                                <option
                                  key={h}
                                  value={h}
                                  disabled={
                                    mappedSources.includes(h) &&
                                    mapping[field.key] !== h
                                  }
                                >
                                  {h}
                                </option>
                              ))}
                            </select>
                            <span className="dt-sample">
                              {mapping[field.key]
                                ? String(
                                    table.rows.find(
                                      (row) =>
                                        row[
                                          table.headers.indexOf(
                                            mapping[field.key],
                                          )
                                        ] !== "",
                                    )?.[
                                      table.headers.indexOf(mapping[field.key])
                                    ] ?? "Empty",
                                  )
                                : "—"}
                            </span>
                          </div>
                        ))}
                      </div>
                      <p className="dt-muted">
                        {Object.values(mapping).filter(Boolean).length} mapped ·{" "}
                        {
                          table.headers.filter(
                            (h) => !mappedSources.includes(h),
                          ).length
                        }{" "}
                        source columns ignored
                      </p>
                      {missing.length > 0 && (
                        <p role="status" className="dt-warning">
                          Map required fields:{" "}
                          {missing.map(fieldLabel).join(", ")}
                        </p>
                      )}
                      {duplicates && (
                        <p className="dt-error">
                          Use each uploaded column only once.
                        </p>
                      )}
                    </>
                  )}
                  {step === 2 && table && (
                    <>
                      <h3>
                        Review {prepared.rows.length.toLocaleString()} rows
                      </h3>
                      <p className="dt-muted">
                        Showing the first 10 mapped rows. The destination module
                        validates permissions, relationships and duplicates when
                        you confirm.
                      </p>
                      <div className="dt-preview">
                        <table>
                          <thead>
                            <tr>
                              <th>File row</th>
                              {fields
                                .filter(
                                  (f) =>
                                    mapping[f.key] || f.default !== undefined,
                                )
                                .map((f) => (
                                  <th key={f.key}>{fieldLabel(f)}</th>
                                ))}
                            </tr>
                          </thead>
                          <tbody>
                            {prepared.rows.slice(0, 10).map((row, i) => (
                              <tr {...recordPreviewProps(row)} key={i}>
                                <td>{table.rowNumbers[i]}</td>
                                {fields
                                  .filter(
                                    (f) =>
                                      mapping[f.key] || f.default !== undefined,
                                  )
                                  .map((f) => (
                                    <td key={f.key}>
                                      {String(row[f.key] ?? "—")}
                                    </td>
                                  ))}
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </>
                  )}
                </>
              )}
              {step === 3 && (
                <div className="dt-complete">
                  <Check size={32} />
                  <h3>
                    {result?.created ?? prepared.rows.length} rows processed
                  </h3>
                  <p>
                    {result?.message ||
                      "Your file has been processed. Review any row errors before uploading corrections."}
                  </p>
                  <Button variant="outline" onClick={() => void begin()}>
                    Import another file
                  </Button>
                </div>
              )}
              {issues.length > 0 && step >= 2 && (
                <section className="dt-error-list">
                  <div className="dt-section-title">
                    <h3>{issues.length} row issues</h3>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() =>
                        downloadBlob(
                          new Blob(
                            [
                              "\ufeff" +
                                csvText(issues, ["row", "error"], true),
                            ],
                            { type: "text/csv" },
                          ),
                          "import-row-errors.csv",
                        )
                      }
                    >
                      <Download size={14} />
                      Download errors
                    </Button>
                  </div>
                  {issues.slice(0, 30).map((issue, i) => (
                    <p key={i}>
                      Row {issue.row}: {issue.error}
                    </p>
                  ))}
                  {issues.length > 30 && (
                    <p>Download the full error list to see all issues.</p>
                  )}
                </section>
              )}
            </div>
            <footer className="dt-footer">
              <Button
                variant="ghost"
                disabled={busy}
                onClick={() =>
                  step === 2 ? (setServerIssues([]), setStep(1)) : close()
                }
              >
                {step === 2
                  ? "Back to mapping"
                  : step === 3
                    ? "Close"
                    : "Cancel"}
              </Button>
              <span />
              {step === 1 && (
                <Button
                  disabled={
                    busy || !fields.length || missing.length > 0 || duplicates
                  }
                  onClick={() => setStep(2)}
                >
                  Review data
                  <ArrowRight size={15} />
                </Button>
              )}
              {step === 2 && (
                <Button
                  disabled={busy || !prepared.rows.length || issues.length > 0}
                  onClick={() => void commit()}
                >
                  {busy
                    ? "Importing…"
                    : `${confirmLabel} (${prepared.rows.length})`}
                  <ArrowRight size={15} />
                </Button>
              )}
            </footer>
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>
    </>
  );
}
