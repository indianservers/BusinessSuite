import { useState } from "react";
import * as Dialog from "@radix-ui/react-dialog";
import { Check, Download, FileSpreadsheet, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { api } from "@/services/api";
import {
  downloadBlob,
  inspectFile,
  transferError,
  type TransferTable,
} from "./transfer";
import "./transfer.css";

export default function DataExportButton({
  load,
  filename = "export",
  label = "Export",
  description = "Exports data available to you under the current permissions.",
  disabled,
}: {
  load: () => Promise<Blob | Record<string, unknown>[]>;
  filename?: string;
  label?: string;
  description?: string;
  disabled?: boolean;
}) {
  const [open, setOpen] = useState(false),
    [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [message, setMessage] = useState(""),
    [file, setFile] = useState<File>(),
    [table, setTable] = useState<TransferTable>(),
    [columns, setColumns] = useState<string[]>([]),
    [format, setFormat] = useState("xlsx");
  async function begin() {
    setOpen(true);
    setBusy(true);
    setError("");
    setMessage("");
    setFile(undefined);
    setTable(undefined);
    try {
      const source = await load();
      if (Array.isArray(source) && !source.length)
        throw Error("No rows are available to export.");
      const blob =
        source instanceof Blob
          ? source
          : new Blob([JSON.stringify(source)], { type: "application/json" });
      const extension = blob.type.includes("json")
        ? "json"
        : blob.type.includes("sheet") || /\.xlsx$/i.test(filename)
          ? "xlsx"
          : "csv";
      const selected = new File([blob], `export.${extension}`, {
        type: blob.type,
      });
      const parsed = await inspectFile(selected, "", 1, true);
      setFile(selected);
      setTable(parsed);
      setColumns(parsed.headers);
    } catch (e) {
      setError(transferError(e));
    } finally {
      setBusy(false);
    }
  }
  async function save() {
    if (!file || !columns.length) return;
    setBusy(true);
    setError("");
    setMessage("");
    try {
      const body = new FormData();
      body.append("file", file);
      body.append("format", format);
      body.append("columns", JSON.stringify(columns));
      const response = await api.post("/data-transfer/export/convert", body, {
        responseType: "blob",
      });
      if (format === "clipboard") {
        await navigator.clipboard.writeText(
          (await response.data.text()).replace(/^\uFEFF/, ""),
        );
        setMessage("Copied to clipboard");
      } else {
        downloadBlob(
          response.data,
          `${filename.replace(/\.(csv|xlsx|xls|json)$/i, "")}.${format}`,
        );
        setMessage("Export downloaded");
      }
    } catch (e) {
      const blob = (e as { response?: { data?: Blob } })?.response?.data;
      if (blob instanceof Blob) {
        try {
          const detail = JSON.parse(await blob.text()).detail;
          setError(
            typeof detail === "string"
              ? detail
              : detail?.message || "Export failed",
          );
        } catch {
          setError("Export failed");
        }
      } else setError(transferError(e));
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <Button
        variant="outline"
        disabled={disabled}
        onClick={() => void begin()}
      >
        <Download size={16} />
        {label}
      </Button>
      <Dialog.Root
        open={open}
        onOpenChange={(value) => {
          if (!busy) setOpen(value);
        }}
      >
        <Dialog.Portal>
          <Dialog.Overlay className="dt-overlay" />
          <Dialog.Content className="dt-dialog dt-export">
            <header className="dt-heading">
              <span className="dt-icon">
                <FileSpreadsheet size={24} />
              </span>
              <div>
                <Dialog.Title>Export data</Dialog.Title>
                <Dialog.Description>{description}</Dialog.Description>
              </div>
              <Dialog.Close disabled={busy} aria-label="Close export">
                <X size={20} />
              </Dialog.Close>
            </header>
            <div className="dt-body">
              {busy && <p role="status">Preparing your export…</p>}
              {error && (
                <p role="alert" className="dt-error">
                  {error}
                </p>
              )}
              {message && (
                <p role="status" className="dt-success">
                  <Check size={16} />
                  {message}
                </p>
              )}
              {table && (
                <>
                  <p>
                    <strong>{table.total.toLocaleString()}</strong>{" "}
                    {table.total === 1 ? "row" : "rows"} available · Choose your
                    format and columns
                  </p>
                  <div className="dt-formats">
                    {[
                      ["xlsx", "Excel", ".xlsx workbook"],
                      ["csv", "CSV", "Universal spreadsheet"],
                      ["json", "JSON", "Structured data"],
                      ["clipboard", "Copy", "Paste into a spreadsheet"],
                    ].map(([value, name, hint]) => (
                      <button
                        key={value}
                        aria-pressed={format === value}
                        onClick={() => setFormat(value)}
                      >
                        <FileSpreadsheet size={20} />
                        <strong>{name}</strong>
                        <small>{hint}</small>
                      </button>
                    ))}
                  </div>
                  <div className="dt-section-title">
                    <h3>
                      Columns ({columns.length}/{table.headers.length})
                    </h3>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() =>
                        setColumns(
                          columns.length === table.headers.length
                            ? []
                            : table.headers,
                        )
                      }
                    >
                      {columns.length === table.headers.length
                        ? "Clear"
                        : "Select all"}
                    </Button>
                  </div>
                  <div className="dt-export-columns">
                    {table.headers.map((h) => (
                      <label key={h}>
                        <input
                          type="checkbox"
                          checked={columns.includes(h)}
                          onChange={(e) =>
                            setColumns((current) =>
                              e.target.checked
                                ? table.headers.filter(
                                    (key) => current.includes(key) || key === h,
                                  )
                                : current.filter((key) => key !== h),
                            )
                          }
                        />
                        {h.replace(/_/g, " ")}
                      </label>
                    ))}
                  </div>
                </>
              )}
            </div>
            <footer className="dt-footer">
              <Button
                variant="ghost"
                disabled={busy}
                onClick={() => setOpen(false)}
              >
                Close
              </Button>
              <span />
              <Button
                disabled={busy || !file || !columns.length}
                onClick={() => void save()}
              >
                <Download size={15} />
                {format === "clipboard"
                  ? "Copy data"
                  : `Download ${format.toUpperCase()}`}
              </Button>
            </footer>
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>
    </>
  );
}
