import { Children, Fragment, isValidElement, useId, useMemo, type HTMLAttributes, type ReactElement, type ReactNode, type TableHTMLAttributes } from "react";
import { useLocation } from "react-router-dom";
import SharedDataGrid from "./SharedDataGrid";
import { localGridSource } from "./local-source";
import type { GridColumn, GridQuery } from "./types";

type Element = ReactElement<Record<string, any>>;
type RecordRow = { id: string; values: string[] };
function elements(children: ReactNode): Element[] {
  return Children.toArray(children).flatMap(child => !isValidElement(child) ? [] : child.type === Fragment ? elements((child.props as { children?: ReactNode }).children) : [child as Element]);
}
export function gridCellText(node: ReactNode): string {
  if (node == null || typeof node === "boolean") return "";
  if (typeof node === "string" || typeof node === "number") return String(node);
  if (Array.isArray(node)) return node.map(gridCellText).filter(Boolean).join(" ");
  if (!isValidElement(node)) return "";
  const p = node.props as Record<string, any>;
  if (p["aria-hidden"] === true || p["aria-hidden"] === "true") return "";
  if (p.value != null) {
    const selected = elements(p.children).find(option => option.type === "option" && String(option.props.value ?? gridCellText(option.props.children)) === String(p.value));
    if (selected) return gridCellText(selected.props.children);
    if (!p.children) return String(p.value);
  }
  return gridCellText(p.children) || (p.value != null ? String(p.value) : p.label != null ? String(p.label) : "");
}
function contains(node: ReactNode, predicate: (element: Element) => boolean): boolean {
  return elements(node).some(element => predicate(element) || contains(element.props.children, predicate));
}
const checkbox = (element: Element) => element.type === "input" && element.props.type === "checkbox";
const editor = (element: Element) => element.type === "input" && element.props.type !== "checkbox" || element.type === "textarea" || typeof element.type !== "string" && /Input|Editor|Composer/.test((element.type as { displayName?: string; name?: string }).displayName || (element.type as { name?: string }).name || "");

/** Retains page-owned React cells and handlers; only the surrounding record grid changes. */
export default function GridTable({ children, gridId, allowExport = false, variant = "records", ...attributes }: TableHTMLAttributes<HTMLTableElement> & { gridId: string; allowExport?: boolean; variant?: "records" | "matrix" }) {
  const location = useLocation(), instance = useId();
  const sections = elements(children);
  const heads = elements(sections.find(e => e.type === "thead")?.props.children);
  const bodies = sections.filter(e => e.type === "tbody");
  const headers = elements(heads[0]?.props.children);
  const rows = bodies.flatMap(body => elements(body.props.children));
  const foot = sections.some(e => e.type === "tfoot");
  const rectangular = rows.every(row => row.type === "tr" && elements(row.props.children).length === headers.length && elements(row.props.children).every(cell => ["td", "th"].includes(String(cell.type)) && !(cell.props.colSpan > 1) && !(cell.props.rowSpan > 1)));
  // Matrices, entry forms, totals, loading/error rows, and render-prop wrappers retain native semantics.
  const compatible = variant === "records" && heads.length === 1 && headers.length > 1 && bodies.length === 1 && !foot && rectangular && !contains(children, editor)
    && sections.every(e => ["thead", "tbody", "caption"].includes(String(e.type)))
    && !headers.some(h => h.props.colSpan > 1 || h.props.rowSpan > 1);
  const scope = `suite-table:${location.pathname}:${gridId}`;
  const rowMap = new Map(rows.map((row, i) => [String(row.key ?? i), row]));
  const records: RecordRow[] = rows.map((row, i) => ({ id: String(row.key ?? i), values: elements(row.props.children).map(cell => gridCellText(cell.props.children).trim()) }));
  const hasSelection = headers.some(h => contains(h.props.children, checkbox)) || rows.some(row => contains(row.props.children, checkbox));
  const columns: GridColumn<RecordRow>[] = headers.map((header, index) => {
    const title = gridCellText(header.props.children).trim() || (index === 0 && hasSelection ? "Select" : `Column ${index + 1}`);
    const isAction = /^(actions?|quick actions|select)$/i.test(title);
    const hasControl = contains(header.props.children, e => e.type === "button" || checkbox(e) || typeof e.type !== "string");
    return {
      id: `column-${index}`, title, width: isAction ? 100 : index === (hasSelection ? 1 : 0) ? 260 : 180,
      header: hasControl ? header.props.children : undefined,
      sortable: !isAction && !hasControl, filterable: !isAction, groupable: !isAction,
      accessor: row => row.values[index],
      render: row => {
        const cell = elements(rowMap.get(row.id)?.props.children)[index];
        if (!cell) return null;
        const { children: content, colSpan: _colSpan, rowSpan: _rowSpan, ...props } = cell.props;
        return <div {...props} className={`udg-adapted-cell ${props.className || ""}`}>{content}</div>;
      },
    };
  });
  const signature = JSON.stringify(records);
  const source = useMemo(() => {
    let hash = 2166136261;
    for (let i = 0; i < signature.length; i++) hash = Math.imul(hash ^ signature.charCodeAt(i), 16777619);
    const local = localGridSource(`${scope}:${instance}:${hash >>> 0}`, records, columns, row => row.id);
    // Existing page exports retain their authorization. A table adapter cannot infer export permission.
    return allowExport ? local : { ...local, export: undefined, load: async (query: GridQuery, signal?: AbortSignal) => {
      const result = await local.load(query, signal);
      return { ...result, permissions: { ...result.permissions, export: false } };
    } };
  }, [scope, instance, signature, allowExport, headers.map(h => gridCellText(h.props.children)).join("|")]);
  if (!compatible) return <div className="udg-native" data-grid-id={gridId}><table {...attributes}>{children}</table></div>;
  const caption = gridCellText(sections.find(e => e.type === "caption")?.props.children).trim();
  return <div className="udg-table-adapter" data-source-table={gridId}>
    <SharedDataGrid<RecordRow> gridId={scope} title={attributes["aria-label"] || caption || "Records"}
      dataScope="loaded"
      columns={columns} dataSource={source} getRowId={row => row.id}
      selectionEnabled={!hasSelection} exportFormats={["csv", "clipboard"]}
      initialLayout={{ pinning: { left: hasSelection ? ["column-0", "column-1"] : ["column-0"], right: [] }, rowHeight: 64 }}
      height={Math.min(600, Math.max(240, records.length * 64 + 42))}
      rowProps={row => {
        const { children: _children, className: _className, style: _style, ...props } = rowMap.get(row.id)?.props || {};
        return props as HTMLAttributes<HTMLDivElement>;
      }}
      renderDetails={row => <dl className="udg-details-fields">{columns.filter(c => !/^(select|actions?|quick actions)$/i.test(c.title)).map(c => <div key={c.id}><dt>{c.title}</dt><dd>{String(c.accessor?.(row) || "—")}</dd></div>)}</dl>}
      statistics={result => <div className="udg-statistics"><div><span>Matching loaded rows</span><strong>{result.total.toLocaleString()}</strong></div><p className="udg-scope-note">Search, grouping and export apply to loaded rows. Use the page filters and pagination to load other records.</p></div>}
    />
  </div>;
}
