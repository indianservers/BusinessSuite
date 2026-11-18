import { Children, Fragment, isValidElement, type ReactElement, type ReactNode } from "react";
type Element = ReactElement<Record<string, any>>;
export function elements(children: ReactNode): Element[] {
  return Children.toArray(children).flatMap(child => !isValidElement(child) ? [] : child.type === Fragment ? elements((child.props as {children?:ReactNode}).children) : [child as Element]);
}
/** Recognizes page-owned open/preview controls without mounting their components. */
export function hasRecordOpenControl(node:ReactNode):boolean {
  return elements(node).some(element=>typeof element.props.onOpen==="function" || typeof element.props.onSelectRecord==="function" || /^(preview|view profile|view details|open record)\b/i.test(String(element.props["aria-label"]||element.props.title||gridCellText(element.props.children)).trim()) && (element.type==="button"||typeof element.type!=="string") || hasRecordOpenControl(element.props.children));
}
export function gridCellText(node: ReactNode): string {
  if (node == null || typeof node === "boolean") return "";
  if (typeof node === "string" || typeof node === "number") return String(node);
  if (Array.isArray(node)) return node.map(gridCellText).filter(Boolean).join(" ");
  if (!isValidElement(node)) return "";
  const p = node.props as Record<string, any>;
  if (p["aria-hidden"] === true || p["aria-hidden"] === "true") return "";
  if (p["data-grid-value"] !== undefined) return p["data-grid-value"] == null ? "" : String(p["data-grid-value"]);
  // TanStack cell renderers expose a pure accessor through their render context.
  if (p.cell && p.column && p.row && typeof p.getValue === "function") {
    const value = p.getValue();
    if (value === undefined && p.column.id === "avatar") {
      const record = p.row.original || {};
      return record.full_name || record.name || [record.first_name,record.last_name].filter(Boolean).join(" ") || record.email || "";
    }
    if (value == null || ["string","number","boolean"].includes(typeof value)) return value == null ? "" : String(value);
  }
  if (p.column && typeof p.column.columnDef?.header === "string") return p.column.columnDef.header;
  if ("value" in p && !p.children) return p.value == null ? "" : String(p.value);
  if (p.value != null) {
    const selected = elements(p.children).find(option => option.type === "option" && String(option.props.value ?? gridCellText(option.props.children)) === String(p.value));
    if (selected) return gridCellText(selected.props.children);
    if (!p.children) return String(p.value);
  }
  return gridCellText(p.children) || (p.value != null ? String(p.value) : p.label != null ? String(p.label) : typeof p.status === "string" ? p.status : typeof p.stage === "string" ? p.stage : "");
}

export function hasRecordStatusIcon(node: ReactNode): boolean {
  return elements(node).some(element => /suite-record-status|srm-record-name|lm-record-identity/.test(element.props.className || "") || (element.type as {name?:string}).name === "RecordStatusIcon" || hasRecordStatusIcon(element.props.children));
}

export function gridHeaderText(node: ReactNode): string {
  return gridCellText(node).replace(/\s*[⌃⌄↑↓▲▼↕]+\s*$/u, "").trim();
}
