import { api } from "@/services/api";

export type TransferField = {
  key: string;
  label?: string;
  required?: boolean;
  type?: "text" | "number" | "date" | "email" | "boolean";
  aliases?: string[];
  hint?: string;
  default?: string;
};
export type TransferTable = {
  headers: string[];
  rows: unknown[][];
  rowNumbers: number[];
  sheets: string[];
  sheet: string;
  total: number;
  headerRow: number;
};
export type TransferIssue = { row: number; error: string };
export type ImportResult = {
  created?: number;
  failed?: number;
  errors?: { row: number; error?: unknown; errors?: string[] }[];
  message?: string;
};
export type MappedImport = {
  rows: Record<string, unknown>[];
  file: File;
  filename: string;
  mapping: Record<string, string>;
  rowNumbers: number[];
};

export const fieldLabel = (field: TransferField) =>
  field.label ||
  field.key
    .replace(/([a-z])([A-Z])/g, "$1 $2")
    .replace(/_/g, " ")
    .replace(/^./, (c) => c.toUpperCase());
const normalized = (value: string) =>
  value.toLowerCase().replace(/[^a-z0-9]/g, "");
const aliases: Record<string, string[]> = {
  email: ["email address", "e mail", "mail"],
  personal_email: ["email", "email address"],
  full_name: ["name", "contact name", "customer name"],
  first_name: ["given name", "firstname"],
  last_name: ["surname", "family name"],
  phone: ["mobile", "phone number", "contact number"],
  phone_number: ["phone", "mobile", "contact number"],
  code: ["sku", "product code", "service code"],
  date_of_joining: ["joining date", "join date", "start date"],
  name: ["product name", "service name", "company name", "deal name"],
  transaction_date: ["date", "value date", "txn date"],
  description: ["narration", "particulars", "details"],
  reference_number: ["reference", "ref no", "transaction reference"],
  debit_amount: ["debit", "withdrawal", "withdrawals"],
  credit_amount: ["credit", "deposit", "deposits"],
};
export function suggestMapping(headers: string[], fields: TransferField[]) {
  const mapping: Record<string, string> = {},
    used = new Set<string>();
  for (const field of [...fields].sort(
    (a, b) => Number(!!b.required) - Number(!!a.required),
  )) {
    const names = [
      field.key,
      fieldLabel(field),
      ...(field.aliases || []),
      ...(aliases[field.key] || []),
    ].map(normalized);
    const source =
      headers.find(
        (header) =>
          !used.has(header) && normalized(header) === normalized(field.key),
      ) ||
      headers.find(
        (header) => !used.has(header) && names.includes(normalized(header)),
      );
    if (source) {
      mapping[field.key] = source;
      used.add(source);
    }
  }
  return mapping;
}
export function mapRows(
  table: TransferTable,
  fields: TransferField[],
  mapping: Record<string, string>,
) {
  const issues: TransferIssue[] = [];
  const rows = table.rows.map((values, index) => {
    const row: Record<string, unknown> = {};
    for (const field of fields) {
      const source = mapping[field.key];
      let value = source
        ? values[table.headers.indexOf(source)]
        : field.default;
      if (typeof value === "string") value = value.trim();
      const empty = value === undefined || value === null || value === "";
      const fail = (error: string) =>
        issues.push({
          row: table.rowNumbers[index],
          error: `${fieldLabel(field)}: ${error}`,
        });
      if (empty) {
        if (field.required) fail("Required value is missing");
        continue;
      }
      if (field.type === "number") {
        const number = Number(String(value).replace(/,/g, ""));
        if (!Number.isFinite(number)) fail("Enter a valid number");
        else value = number;
      }
      if (
        field.type === "email" &&
        !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(String(value))
      )
        fail("Enter a valid email address");
      if (field.type === "date") {
        const text = String(value);
        if (
          !/^\d{4}-\d{2}-\d{2}$/.test(text) ||
          Number.isNaN(Date.parse(text)) ||
          new Date(text).toISOString().slice(0, 10) !== text
        )
          fail("Use YYYY-MM-DD or an Excel date cell");
      }
      if (field.type === "boolean") {
        const text = String(value).toLowerCase();
        if (!["true", "false", "yes", "no", "1", "0"].includes(text))
          fail("Use Yes/No or True/False");
        else value = ["true", "yes", "1"].includes(text);
      }
      row[field.key] = value;
    }
    return row;
  });
  return { rows, issues };
}
export function csvText(
  rows: Record<string, unknown>[],
  fields?: string[],
  protect = false,
) {
  const headers =
    fields || Array.from(new Set(rows.flatMap((row) => Object.keys(row))));
  const escape = (value: unknown) => {
    let text =
      value == null
        ? ""
        : typeof value === "object"
          ? JSON.stringify(value)
          : String(value);
    if (protect && typeof value === "string" && /^[\s]*[=+@-]/.test(text))
      text = "'" + text;
    return `"${text.replace(/"/g, '""')}"`;
  };
  return [
    headers.map(escape).join(","),
    ...rows.map((row) => headers.map((key) => escape(row[key])).join(",")),
  ].join("\r\n");
}
export function mappedFile(
  rows: Record<string, unknown>[],
  name: string,
  fields?: string[],
) {
  return new File(
    [csvText(rows, fields)],
    name.replace(/\.[^.]+$/, "") + ".csv",
    { type: "text/csv" },
  );
}
export function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob),
    anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
export function transferError(error: unknown): string {
  const detail = (error as { response?: { data?: { detail?: unknown } } })
    ?.response?.data?.detail;
  return typeof detail === "string"
    ? detail
    : detail
      ? typeof detail === "object" && "message" in detail
        ? String(detail.message)
        : JSON.stringify(detail)
      : error instanceof Error
        ? error.message
        : "Unable to complete this action";
}
export async function inspectFile(
  file: File,
  sheet = "",
  headerRow = 1,
  exporting = false,
) {
  const data = new FormData();
  data.append("file", file);
  data.append("sheet", sheet);
  data.append("header_row", String(headerRow));
  return (
    await api.post<TransferTable>(
      `/data-transfer/${exporting ? "export/inspect" : "inspect"}`,
      data,
    )
  ).data;
}
