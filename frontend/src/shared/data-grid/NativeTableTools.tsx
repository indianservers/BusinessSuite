import RecordViewBar from "./RecordViewBar";
import { useRecordPreferences } from "./record-preferences";
import { Star, Eye, Copy } from "lucide-react";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";
import { writeClipboard } from "@/lib/clipboard";
import { ChevronDown, ChevronRight, ChevronsDownUp, ChevronsUpDown, Columns3, Layers, Plus } from "lucide-react";
import GroupLabel, { RecordStatusIcon } from "./GroupLabel";
import { Children, Fragment, cloneElement, isValidElement, useEffect, useMemo, useState, type ReactElement, type ReactNode, type TableHTMLAttributes } from "react";
import { useAuthStore } from "@/store/authStore";
import { gridCellText, gridHeaderText, hasRecordStatusIcon, hasRecordOpenControl } from "./cell-content";
import "./native-table-tools.css";

type Element = ReactElement<Record<string, any>>;
const nodes = (children: ReactNode): Element[] => Children.toArray(children).flatMap(child => !isValidElement(child) ? [] : child.type === Fragment ? nodes((child.props as {children?: ReactNode}).children) : [child as Element]);
type PersonalLayout = { hidden?: number[]; order?: number[]; density?: string; group?: string };
type Props = { children: ReactNode; scope: string; attributes: TableHTMLAttributes<HTMLTableElement>; staticLayout?: boolean; defaultGroupBy?: string; defaultHiddenColumns?: string[]; groupCreate?: { field: string; label: string; onCreate: (value: string) => void } };

/** Preserves page-owned cells, permissions, and editors while sharing list controls. */
export default function NativeTableTools({ children, scope, attributes, defaultGroupBy, defaultHiddenColumns = [], groupCreate, staticLayout }: Props) {
  const user = useAuthStore(s => s.user);
  const key = `native-table-layout:${user?.access?.companyId}:${user?.id}:${scope}`;
  const sections = nodes(children), header = nodes(sections.find(s => s.type === "thead")?.props.children)[0];
  const headers = nodes(header?.props.children);
  const labels = headers.map((h, i) => gridHeaderText(h.props.children) || (i === 0 ? "Select" : `Column ${i + 1}`));
  const signature = labels.join("|");
  const initial = useMemo<PersonalLayout>(() => {
    try {
      const value = JSON.parse(localStorage.getItem(key) || "{}");
      if (!value || typeof value !== "object" || Array.isArray(value)) return {};
      return {hidden:Array.isArray(value.hidden)?value.hidden.filter(Number.isInteger):undefined,order:Array.isArray(value.order)?value.order.filter(Number.isInteger):undefined,density:["compact","comfortable","spacious"].includes(value.density)?value.density:undefined,group:typeof value.group==="string"?value.group:undefined};
    } catch { return {}; }
  }, [key]);
  const [loadedKey, setLoadedKey] = useState(key);
  const defaultHidden = headers.map((_,i) => i).filter(i => defaultHiddenColumns.includes(labels[i]));
  const [hidden, setHidden] = useState<number[]>(initial.hidden || defaultHidden);
  const [order, setOrder] = useState<number[]>(initial.order || []);
  const [density, setDensity] = useState(initial.density || "compact");
  const [group, setGroup] = useState(initial.group ?? defaultGroupBy ?? "");
  const [collapsed, setCollapsed] = useState<Set<string>>(new Set());
  useEffect(() => {
    setHidden(initial.hidden || defaultHidden); setOrder(initial.order || []); setDensity(initial.density || "compact");
    setGroup(initial.group ?? defaultGroupBy ?? ""); setCollapsed(new Set()); setLoadedKey(key);
  }, [key]);
  const indices = [...new Set([...order.filter(i => Number.isInteger(i) && i >= 0 && i < headers.length), ...headers.map((_, i) => i)])];
  const visible = indices.filter(i => !hidden.includes(i) || i === 0);
  useEffect(() => { if(loadedKey!==key)return; try { localStorage.setItem(key, JSON.stringify({ hidden, order, density, group })); } catch { /* Personal layout remains optional. */ } }, [key, loadedKey, hidden, order, density, group]);
  const groupable = headers.map((_, i) => i).filter(i => !/^(select|actions?|quick actions|column \d+)$/i.test(labels[i]));
  const groupBy = groupable.find(i => labels[i] === group) ?? -1;
  const bodies = sections.filter(s => s.type === "tbody");
  const rows = bodies.flatMap(body => nodes(body.props.children));
  const personal=useRecordPreferences(scope);
  const [detail,setDetail]=useState<Element|null>(null),[notice,setNotice]=useState("");
  const rectangular = headers.length > 1 && !sections.some(s => s.type === "tfoot") && rows.every(row => row.type === "tr" && nodes(row.props.children).length === headers.length && nodes(row.props.children).every(cell => !cell.props.colSpan && !cell.props.rowSpan));
  const labelFor = (row: Element) => {
    const value = gridCellText(nodes(row.props.children)[groupBy]).trim();
    return value && !/^[—–-]$/.test(value) ? value : /owner|assignee|employee|team/i.test(group) ? "Unassigned" : "Not set";
  };
  if (staticLayout || !rectangular) return <div className="native-table-static" data-layout-mode="matrix"><table {...attributes}>{children}</table></div>;
  const statusIndex = labels.findIndex(label => /^(status|stage|state|approval status|billing status|employment status)$/i.test(label));
  const namedIdentity = labels.findIndex(label => /^(name|title|task|project|employee|lead|contact|company|customer|account|record|document|file|item|product|invoice|order|contract|campaign)(\s*\/.*)?$/i.test(label));
  const identityIndex = namedIdentity >= 0 ? namedIdentity : labels[0] === "Select" ? 1 : 0;
  const categoryIndex=labels.findIndex(label=>/^(category|department|type|stage|status|team|group)$/i.test(label));
  const tagsIndex=labels.findIndex(label=>/^(tags?|labels)$/i.test(label));
  const idFor=(row:Element)=>String(row.props["data-record-id"]??(String(row.key).includes("$")?row.key:gridCellText(nodes(row.props.children)[identityIndex])));
  const starFor=(row:Element):Element|undefined=>{const walk=(children:ReactNode):Element|undefined=>{for(const child of nodes(children)){if(child.type==="button"&&/^un?star |^star |^unfavorite |^favorite /i.test(String(child.props["aria-label"]||""))&&typeof child.props["aria-pressed"]==="boolean")return child;const nested=walk(child.props.children);if(nested)return nested;}};return walk(row.props.children);};
  const isFavorite=(row:Element)=>{const native=starFor(row);return native?native.props["aria-pressed"]:personal.favorites.includes(idFor(row));};
  const toggle=(row:Element)=>{const native=starFor(row);if(native&&typeof native.props.onClick==="function")native.props.onClick({stopPropagation(){},preventDefault(){}});else personal.toggle(idFor(row));};
  const shown=rows.filter(row=>personal.view!=="favorites"||isFavorite(row)).filter(row=>personal.view!=="frequent"||!!personal.activity[idFor(row)]);
  if(personal.view==="frequent")shown.sort((a,b)=>(personal.activity[idFor(b)]?.count||0)-(personal.activity[idFor(a)]?.count||0)||(personal.activity[idFor(b)]?.last||0)-(personal.activity[idFor(a)]?.last||0));
  const ownTools=rows.length>0&&rows.every(row=>!!starFor(row)&&hasRecordOpenControl(row.props.children));
  const tools=(row:Element)=>ownTools?null:<span className="suite-record-card-tools" data-record-personal>{!starFor(row)&&<button type="button" className="suite-record-star" aria-label={`${isFavorite(row)?"Unfavorite":"Favorite"} ${gridCellText(nodes(row.props.children)[identityIndex])}`} aria-pressed={isFavorite(row)} onClick={()=>toggle(row)}><Star size={14} fill={isFavorite(row)?"currentColor":"none"}/></button>}{!row.props.onClick&&!row.props.onClickCapture&&!hasRecordOpenControl(row.props.children)&&<button type="button" className="suite-record-star" title="Preview record" aria-label="Preview record" onClick={()=>{personal.use(idFor(row));setDetail(row);}}><Eye size={14}/></button>}<button type="button" className="suite-record-star" title="Copy record name" aria-label="Copy record name" onClick={()=>{void writeClipboard(gridCellText(nodes(row.props.children)[identityIndex])).then(()=>setNotice("Record name copied")).catch(()=>setNotice("Could not copy the record name"));}}><Copy size={14}/></button></span>;
  const capture=(row:Element,event:any)=>{row.props.onClickCapture?.(event);if((event.target as HTMLElement).closest("button,a")&&!(event.target as HTMLElement).closest("[data-record-personal],.portfolio-star"))personal.use(idFor(row));};
  const renderRow = (row: Element) => {
    const cells = nodes(row.props.children);
    const status = statusIndex >= 0 ? gridCellText(cells[statusIndex]).trim() : "";
    return cloneElement(row, {onClickCapture:(event:any)=>capture(row,event)}, [...visible.map(i => {
      const cell = cells[i], content = cell.props.children;
      const marked = i === identityIndex && status && !hasRecordStatusIcon(content);
      return cloneElement(cell, {key:i,"data-column-index":i}, marked ? <div className="native-record-identity"><span aria-hidden="true"><RecordStatusIcon label={status} field={labels[statusIndex]}/></span><div className="native-cell-content">{content}</div></div> : content);
    }),...(!ownTools?[<td key="personal-tools" style={{position:"static",minWidth:94,width:94}}>{tools(row)}</td>]:[])]);
  };
  function transform(section: Element) {
    if (!["thead", "tbody"].includes(String(section.type))) return section;
    const sectionRows = section.type === "tbody" ? shown.filter(row=>nodes(section.props.children).some(member=>String(member.key)===String(row.key))||bodies.length===1) : nodes(section.props.children);
    if(section.type==="thead")return cloneElement(section,{},sectionRows.map(row=>cloneElement(row,{},[...visible.map(i=>cloneElement(nodes(row.props.children)[i],{key:i})),...(!ownTools?[<th key="personal-tools" style={{position:"static",minWidth:94,width:94}}>Quick tools</th>]:[])])));
    if (groupBy < 0) return cloneElement(section, {}, sectionRows.map(renderRow));
    const groups = new Map<string, Element[]>();
    sectionRows.forEach(row => { const label = labelFor(row); const members = groups.get(label); if (members) members.push(row); else groups.set(label, [row]); });
    return cloneElement(section, {}, [...groups].flatMap(([label, members]) => [
      <tr key={`group:${label}`} className="native-group-row"><td colSpan={visible.length+(ownTools?0:1)}><button type="button" aria-expanded={!collapsed.has(label)} aria-label={`${collapsed.has(label) ? "Expand" : "Collapse"} ${group}: ${label}`} onClick={() => setCollapsed(current => { const next = new Set(current); next.has(label) ? next.delete(label) : next.add(label); return next; })}>{collapsed.has(label) ? <ChevronRight size={13} aria-hidden="true"/> : <ChevronDown size={13} aria-hidden="true"/>}<GroupLabel label={label} field={group} count={members.length}/></button></td></tr>,
      ...(collapsed.has(label) ? [] : [
        ...members.map(renderRow),
        ...(groupCreate?.field === group ? [<tr key={`create:${label}`} className="native-group-create"><td colSpan={visible.length+(ownTools?0:1)}><button type="button" onClick={() => groupCreate.onCreate(label)} aria-label={`${groupCreate.label} in ${label}`}><Plus size={13} aria-hidden="true"/>{groupCreate.label}</button></td></tr>] : []),
      ]),
    ]));
  }
  function move(index: number, delta: number) { const next = [...indices]; const at = next.indexOf(index), to = at + delta; if (to < 0 || to >= next.length || index === 0 || next[to] === 0) return; [next[at], next[to]] = [next[to], next[at]]; setOrder(next); }
  return <div className={`native-table-layout native-table-${density}`} data-columns-signature={signature}>
    <RecordViewBar scope={scope} view={personal.view} change={personal.setView} category={categoryIndex>=0?labels[categoryIndex]:undefined} tags={tagsIndex>=0}/>
    <div className="native-table-toolbar" aria-label="Table layout">
      <label className="native-group-control"><Layers size={13} aria-hidden="true"/><span>Group</span><select aria-label="Group loaded rows by" value={groupBy >= 0 ? group : ""} onChange={e => {setGroup(e.target.value);setCollapsed(new Set());}}><option value="">None</option>{groupable.map(i => <option key={i} value={labels[i]}>{labels[i]}</option>)}</select></label>
      {groupBy >= 0 && <><button type="button" className="native-layout-icon" aria-label="Expand all groups" title="Expand all groups" onClick={() => setCollapsed(new Set())}><ChevronsUpDown size={14}/></button><button type="button" className="native-layout-icon" aria-label="Collapse all groups" title="Collapse all groups" onClick={() => setCollapsed(new Set(rows.map(labelFor)))}><ChevronsDownUp size={14}/></button></>}
      <details className="native-layout-menu"><summary><Columns3 size={13} aria-hidden="true"/>Layout</summary><div className="native-column-options">
        <label className="native-density-control">Row density <select aria-label="Row density" value={density} onChange={e => setDensity(e.target.value)}><option value="compact">Compact</option><option value="comfortable">Comfortable</option><option value="spacious">Spacious</option></select></label>
        {indices.map((index, at) => <div key={index}><label><input type="checkbox" checked={visible.includes(index)} disabled={index === 0} onChange={e => setHidden(h => e.target.checked ? h.filter(i => i !== index) : [...h, index])}/>{labels[index]}</label><button type="button" disabled={index === 0 || at <= 1} aria-label={`Move ${labels[index]} left`} onClick={() => move(index, -1)}>←</button><button type="button" disabled={index === 0 || at === indices.length - 1} aria-label={`Move ${labels[index]} right`} onClick={() => move(index, 1)}>→</button></div>)}
        <button type="button" onClick={() => {setHidden(defaultHidden);setOrder([]);setDensity("compact");setGroup(defaultGroupBy ?? "");setCollapsed(new Set());}}>Reset table layout</button>
      </div></details>
      <span className="native-loaded-count" title="Grouping applies to the rows loaded on this page">{rows.length.toLocaleString()} loaded</span>
    </div>{notice&&<p role="status" className="suite-record-empty">{notice}</p>}
    {["table","favorites","frequent"].includes(personal.view)?<table {...attributes}>{sections.map(transform)}</table>:<div className={`suite-native-cards ${personal.view==="list"?"suite-record-list":""}`}>{(()=>{
      const index=personal.view==="category"?categoryIndex:personal.view==="tags"?tagsIndex:-1;
      const groups=new Map<string,Element[]>();for(const row of shown){const value=index>=0?gridCellText(nodes(row.props.children)[index]):"";const labels=personal.view==="tags"?value.split(",").map(value=>value.trim()).filter(Boolean):[value];for(const label of labels.length?labels:["Untagged"])groups.set(label,[...(groups.get(label)||[]),row]);}
      return [...groups].map(([label,records])=><section className="suite-record-group" key={label}>{label&&<h3><GroupLabel label={label} count={records.length}/></h3>}<div className={`suite-native-cards ${personal.view==="list"?"suite-record-list":""}`}>{records.map(row=><article key={idFor(row)} className="suite-native-card" onClickCapture={event=>capture(row,event)} onDoubleClickCapture={row.props.onDoubleClickCapture}>{visible.map(i=><div key={i}><small>{labels[i]}</small>{nodes(row.props.children)[i]?.props.children}</div>)}{tools(row)}</article>)}</div></section>);
    })()}</div>}
    {rows.length>0&&!shown.length&&<div className="suite-record-empty">No matching {personal.view}.<button type="button" onClick={()=>personal.setView("table")}>Browse loaded records</button></div>}
    <Dialog open={!!detail} onOpenChange={open=>{if(!open)setDetail(null);}}><DialogContent><DialogTitle>Record details</DialogTitle>{detail&&<dl className="udg-details-fields">{visible.filter(i=>!/select|action/i.test(labels[i])).map(i=><div key={i}><dt>{labels[i]}</dt><dd>{gridCellText(nodes(detail.props.children)[i])||"Not set"}</dd></div>)}</dl>}</DialogContent></Dialog>
  </div>;
}
