import { cellPriority } from "@/shared/priority/priority-cell";
import NativeTableTools from "./NativeTableTools";
import { columnValue } from "./column-presentation";
import { useId, useMemo, type HTMLAttributes, type ReactElement, type ReactNode, type TableHTMLAttributes } from "react";
import { elements, gridCellText, gridHeaderText, hasRecordStatusIcon, hasRecordOpenControl } from "./cell-content";
export { gridCellText } from "./cell-content";
import { RecordStatusIcon } from "./GroupLabel";
import { useLocation } from "react-router-dom";
import SharedDataGrid from "./SharedDataGrid";
import { localGridSource } from "./local-source";
import type { GridColumn, GridQuery } from "./types";

type Element = ReactElement<Record<string, any>>;
type RecordRow = { id: string; values: string[] };

function contains(node: ReactNode, predicate: (element: Element) => boolean): boolean {
  return elements(node).some(element => predicate(element) || contains(element.props.children, predicate));
}
const checkbox = (element: Element) => element.type === "input" && element.props.type === "checkbox";
const editor = (element: Element) => element.type === "input" && element.props.type !== "checkbox" || element.type === "textarea" || typeof element.type !== "string" && /Input|Editor|Composer/.test((element.type as { displayName?: string; name?: string }).displayName || (element.type as { name?: string }).name || "");

/** Retains page-owned React cells and handlers; only the surrounding record grid changes. */
export default function GridTable({ children, gridId, allowExport = false, pinActions = false, variant = "records", groupCreate, defaultGroupBy, defaultHiddenColumns, hideSearch, externalPagination, staticLayout, ...attributes }: TableHTMLAttributes<HTMLTableElement> & { gridId: string; allowExport?: boolean; pinActions?: boolean; variant?: "records" | "matrix"; staticLayout?: boolean; defaultGroupBy?: string; defaultHiddenColumns?: string[]; hideSearch?: boolean; externalPagination?: boolean; groupCreate?: { field: string; label: string; onCreate: (value: string) => void } }) {
  const location = useLocation(), instance = useId();
  const sections = elements(children);
  const heads = elements(sections.find(e => e.type === "thead")?.props.children);
  const bodies = sections.filter(e => e.type === "tbody");
  const headers = elements(heads[0]?.props.children);
  const renderedRows = bodies.flatMap(body => elements(body.props.children));
  const emptyCell = renderedRows.length === 1 && elements(renderedRows[0].props.children).length === 1 ? elements(renderedRows[0].props.children)[0] : undefined;
  const emptyState = emptyCell && emptyCell.props.colSpan === headers.length && /^(no\b|nothing\b)/i.test(gridCellText(emptyCell).trim()) ? emptyCell.props.children : undefined;
  const rows = emptyState ? [] : renderedRows;
  const foot = sections.some(e => e.type === "tfoot");
  const rectangular = rows.every(row => row.type === "tr" && elements(row.props.children).length === headers.length && elements(row.props.children).every(cell => ["td", "th"].includes(String(cell.type)) && !(cell.props.colSpan > 1) && !(cell.props.rowSpan > 1)));
  // Matrices, entry forms, totals, loading/error rows, and render-prop wrappers retain native semantics.
  const placeholder = contains(children, element => /(?:^|\s)(?:skeleton|animate-pulse)(?:\s|$)/.test(element.props.className || ""));
  const compatible = !placeholder && !staticLayout && variant === "records" && heads.length === 1 && headers.length > 1 && bodies.length === 1 && !foot && rectangular && !contains(children, editor)
    && sections.every(e => ["thead", "tbody", "caption"].includes(String(e.type)))
    && !headers.some(h => h.props.colSpan > 1 || h.props.rowSpan > 1);
  const scope = `suite-table:${location.pathname}:${gridId}`;
  const rowMap = new Map(rows.map((row, i) => [String(row.key ?? i), row]));
  const records: RecordRow[] = rows.map((row, i) => ({ id: String(row.key ?? i), values: elements(row.props.children).map((cell,index) => /^priority$/i.test(gridHeaderText(headers[index]?.props.children).trim()) ? cellPriority(cell) || gridCellText(cell).trim() : gridCellText(cell).trim()) }));
  const hasSelection = headers.some(h => contains(h.props.children, checkbox)) || rows.some(row => contains(row.props.children, checkbox));
  const titles = headers.map(header => gridHeaderText(header.props.children));
  const statusIndex = titles.findIndex(title => /^(status|stage|state|approval status|billing status|employment status)$/i.test(title));
  const identityMatch = titles.findIndex(title => /^(sales order|billing plan|engagement|name|title|task|project|employee|lead|contact|company|customer|account|record|document|file|item|product|invoice|order|contract|campaign)(\s*\/.*)?$/i.test(title));
  const identityIndex = identityMatch >= 0 ? identityMatch : hasSelection ? 1 : 0;
  const columns: GridColumn<RecordRow>[] = headers.map((header, index) => {
    const title = gridHeaderText(header.props.children) || (index === 0 && hasSelection ? "Select" : `Column ${index + 1}`);
    const isAction = /^(actions?|quick actions|select)$/i.test(title);
    const hasControl = contains(header.props.children, e => e.type === "button" || checkbox(e) || typeof e.type !== "string");
    return {
      id: `column-${index}`, title, width: typeof header.props.style?.width === "number" ? header.props.style.width : /^select$/i.test(title) ? 40 : isAction ? 130 : index === identityIndex ? 220 : /score|progress|quantity/i.test(title) ? 75 : /status|stage|priority/i.test(title) ? 100 : /owner|assignee|assigned|employee|team/i.test(title) ? 135 : /next action/i.test(title) ? 170 : /date|updated|follow.up/i.test(title) ? 140 : 130,
      minWidth: /^select$/i.test(title) ? 32 : /score|progress|quantity/i.test(title) ? 60 : undefined,
      header: hasControl ? header.props.children : undefined,
      sortable: !isAction && !hasControl, filterable: !isAction, groupable: !isAction,
      accessor: row => row.values[index],
      render: row => {
        const cell = elements(rowMap.get(row.id)?.props.children)[index];
        if (!cell) return null;
        const { children: originalContent, colSpan: _colSpan, rowSpan: _rowSpan, ...props } = cell.props;
        const content = columnValue(title, originalContent);
        const marked = index === identityIndex && statusIndex >= 0 && row.values[statusIndex] && !hasRecordStatusIcon(content);
        return <div {...props} className={`udg-adapted-cell ${marked ? "udg-record-identity" : ""} ${props.className || ""}`}>{marked ? <><span aria-hidden="true"><RecordStatusIcon label={row.values[statusIndex]} field={titles[statusIndex]}/></span><div className="udg-cell-content">{content}</div></> : content}</div>;
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
  }, [scope, instance, signature, allowExport, headers.map(h => gridHeaderText(h.props.children)).join("|")]);
  if (placeholder) return <div className="native-table-static" aria-busy="true"><table {...attributes}>{children}</table></div>;
  if (!compatible) return <div className="udg-native" data-grid-id={gridId}><NativeTableTools scope={scope} attributes={attributes} defaultGroupBy={defaultGroupBy} defaultHiddenColumns={defaultHiddenColumns} groupCreate={groupCreate} staticLayout={staticLayout}>{children}</NativeTableTools></div>;
  const caption = gridCellText(sections.find(e => e.type === "caption")?.props.children).trim();
  return <div className="udg-table-adapter" data-source-table={gridId}>
    <SharedDataGrid<RecordRow> gridId={scope} title={attributes["aria-label"] || caption || "Records"}
      dataScope="loaded" emptyContent={emptyState} detailsEnabled={!rows.some(row=>typeof row.props.onClick==="function"||typeof row.props.onClickCapture==="function"||hasRecordOpenControl(row.props.children))}
      hideSearch={hideSearch} externalPagination={externalPagination}
      initialQuery={{...(externalPagination ? {pageSize:200} : {}),...(defaultGroupBy ? {grouping:columns.filter(column=>column.title===defaultGroupBy).map(column=>column.id)} : {})}}
      columns={columns} dataSource={source} getRowId={row => row.id}
      selectionEnabled={!hasSelection} exportFormats={["csv", "clipboard"]}
      initialLayout={{ visibility:Object.fromEntries(columns.filter(column=>defaultHiddenColumns?.includes(column.title)).map(column=>[column.id,false])), pinning: { left: hasSelection ? ["column-0", "column-1"] : ["column-0"], right: pinActions ? columns.filter(column => /^(actions?|quick actions)$/i.test(column.title)).map(column => column.id) : [] }, rowHeight: 42 }}
      rowProps={row => {
        const { children: _children, className: _className, style: _style, ...props } = rowMap.get(row.id)?.props || {};
        return props as HTMLAttributes<HTMLDivElement>;
      }}
      renderDetails={row => <dl className="udg-details-fields">{columns.filter(c => !/^(select|actions?|quick actions)$/i.test(c.title)).map(c => <div key={c.id}><dt>{c.title}</dt><dd>{String(c.accessor?.(row) || "—")}</dd></div>)}</dl>}
      statistics={() => null}
    />
  </div>;
}
