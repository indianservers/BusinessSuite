import { businessGroupColumn } from "./business-grouping";
import { groupAppearance } from "./GroupLabel";
import "./record-group.css";
import { cellPriority } from "@/shared/priority/priority-cell";
import CollectionOverview from "./CollectionOverview";
import { ColumnHeadingIcon, columnValue } from "./column-presentation";
import RecordViewBar from "./RecordViewBar";
import { useRecordPreferences } from "./record-preferences";
import { Star, Eye, Copy } from "lucide-react";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";
import { writeClipboard } from "@/lib/clipboard";
import { ChevronDown, ChevronRight, ChevronsDownUp, ChevronsUpDown, Columns3, Layers, Plus, GripVertical, Pin } from "lucide-react";
import GroupLabel, { RecordStatusIcon } from "./GroupLabel";
import { Children, Fragment, cloneElement, isValidElement, useEffect, useMemo, useRef, useState, type CSSProperties, type ReactElement, type ReactNode, type TableHTMLAttributes } from "react";
import { useAuthStore } from "@/store/authStore";
import { gridCellText, gridHeaderText, hasRecordStatusIcon, hasRecordOpenControl } from "./cell-content";
import "./native-table-tools.css";

type Element = ReactElement<Record<string, any>>;
const nodes = (children: ReactNode): Element[] => Children.toArray(children).flatMap(child => !isValidElement(child) ? [] : child.type === Fragment ? nodes((child.props as {children?: ReactNode}).children) : [child as Element]);
type PersonalLayout = { hidden?: number[]; order?: number[]; density?: string; group?: string; widths?: Record<number, number>; pinned?: number[]; businessGrouping?: boolean };
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
      return {businessGrouping: value.businessGrouping === true, widths: value.widths && typeof value.widths === "object" ? Object.fromEntries(Object.entries(value.widths).filter(([key, width]) => /^\d+$/.test(key) && typeof width === "number" && Number.isFinite(width) && width >= 32 && width <= 800).map(([key,width]) => [key, Number(width)])) : {}, pinned: Array.isArray(value.pinned) ? value.pinned.filter(Number.isInteger) : [], hidden:Array.isArray(value.hidden)?value.hidden.filter(Number.isInteger):undefined,order:Array.isArray(value.order)?value.order.filter(Number.isInteger):undefined,density:["compact","comfortable","spacious"].includes(value.density)?value.density:undefined,group:typeof value.group==="string"?value.group:undefined};
    } catch { return {}; }
  }, [key]);
  const businessColumn = businessGroupColumn(labels.map((title,index)=>({id:String(index),title,groupable:!/^select$|^actions?$/i.test(title)})),scope);
  const businessDefault = defaultGroupBy && !/priority/i.test(defaultGroupBy) ? defaultGroupBy : businessColumn?.title || "";
  const initialGroup = !initial.businessGrouping && (!initial.group || /priority/i.test(initial.group)) ? businessDefault : initial.group ?? businessDefault;
  const [loadedKey, setLoadedKey] = useState(key);
  const [widths, setWidths] = useState<Record<number, number>>(initial.widths || {});
  const [pinned, setPinned] = useState<number[]>(initial.pinned || []);
  const resize = useRef<{ index: number; x: number; width: number } | null>(null);
  const defaultHidden = headers.map((_,i) => i).filter(i => defaultHiddenColumns.includes(labels[i]));
  const [hidden, setHidden] = useState<number[]>(initial.hidden || defaultHidden);
  const [order, setOrder] = useState<number[]>(initial.order || []);
  const [density, setDensity] = useState(initial.density || "compact");
  const [group, setGroup] = useState(initialGroup);
  const [collapsed, setCollapsed] = useState<Set<string>>(new Set());
  useEffect(() => {
    setWidths(initial.widths || {}); setPinned(initial.pinned || []);
    setHidden(initial.hidden || defaultHidden); setOrder(initial.order || []); setDensity(initial.density || "compact");
    setGroup(initialGroup); setCollapsed(new Set()); setLoadedKey(key);
  }, [key]);
  const indices = [...new Set([...order.filter(i => Number.isInteger(i) && i >= 0 && i < headers.length), ...headers.map((_, i) => i)])];
  const visibleIndices = indices.filter(i => !hidden.includes(i) || i === 0);
  const visible = [...visibleIndices.filter(i => pinned.includes(i)), ...visibleIndices.filter(i => !pinned.includes(i))];
  const minColumnWidth=(index:number)=>labels[index]==="Select"?32:64;
  const columnWidth=(index:number)=>{
    const original=headers[index]?.props.style?.width;
    const width=widths[index]??(typeof original==="number"?original:labels[index]==="Select"?44:160);
    return Math.max(minColumnWidth(index),Math.min(800,width));
  };
  const columnStyle = (index: number) => ({
    width: columnWidth(index), minWidth: columnWidth(index),
    ...(labels[index]==="Select"?{paddingLeft:5,paddingRight:5}:{}),
    ...(pinned.includes(index) ? { position: "sticky" as const, left: visible.slice(0, visible.indexOf(index)).filter(i => pinned.includes(i)).reduce((sum, i) => sum + columnWidth(i), 0), zIndex: 2, background: "hsl(var(--card))" } : {}),
  });
  useEffect(() => { if(loadedKey!==key)return; try { localStorage.setItem(key, JSON.stringify({ hidden, order, density, group, widths, pinned, businessGrouping:true })); } catch { /* Personal layout remains optional. */ } }, [key, loadedKey, hidden, order, density, group, widths, pinned]);
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
  if (staticLayout || !rectangular) {
    const staticSections=sections.map(section=>section.type!=="thead"?section:cloneElement(section,{},nodes(section.props.children).map(row=>row.type!=="tr"?row:cloneElement(row,{},nodes(row.props.children).map((cell,index)=>!["th","td"].includes(String(cell.type))?cell:cloneElement(cell,{key:cell.key??index},<span className="native-static-heading">{!nodes(cell.props.children).some(child=>child.type==="input"&&child.props.type==="checkbox")&&<ColumnHeadingIcon title={gridHeaderText(cell.props.children)||`Column ${index+1}`}/>} {cell.props.children}</span>))))));
    return <div className="native-table-static" data-layout-mode="matrix"><table {...attributes}>{staticSections}</table></div>;
  }
  const statusIndex = labels.findIndex(label => /^(status|stage|state|approval status|billing status|employment status)$/i.test(label));
  const namedIdentity = labels.findIndex(label => /^(sales order|billing plan|engagement|name|title|task|project|employee|lead|contact|company|customer|account|record|document|file|item|product|invoice|order|contract|campaign)(\s*\/.*)?$/i.test(label));
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
    const priorityIndex=labels.findIndex(label=>/\bpriority\b/i.test(label.trim()));
    const priority=priorityIndex>=0?cellPriority(cells[priorityIndex]):undefined;
    const colorIndex = groupBy >= 0 && !/priority/i.test(labels[groupBy]) ? groupBy : businessColumn ? Number(businessColumn.id) : -1;
    const colorValue = colorIndex >= 0 ? gridCellText(cells[colorIndex]).trim() || "Not set" : "";
    const colorProps = colorIndex >= 0 ? {"data-record-group-tone":groupAppearance(colorValue,labels[colorIndex]).tone,"data-record-group-field":labels[colorIndex],"data-record-group-value":colorValue} : {};
    const {color} = groupAppearance(colorValue,colorIndex >= 0 ? labels[colorIndex] : "");
    const colorStyle = color ? {"--record-group-accent":color,"--record-group-bg":`color-mix(in srgb, ${color} 7%, hsl(var(--card)))`,"--record-group-hover":`color-mix(in srgb, ${color} 13%, hsl(var(--card)))`} as CSSProperties : {};
    return cloneElement(row, {style:{...row.props.style,...colorStyle},...colorProps,"data-priority-row":priority?true:row.props["data-priority-row"],"data-priority":priority||row.props["data-priority"],onClickCapture:(event:any)=>capture(row,event)}, [...visible.map(i => {
      const cell = cells[i], content = columnValue(labels[i], cell.props.children);
      const marked = i === identityIndex && status && !hasRecordStatusIcon(content);
      return cloneElement(cell, {key:i,"data-column-index":i,style:{...cell.props.style,...columnStyle(i)}}, marked ? <div className="native-record-identity"><span aria-hidden="true"><RecordStatusIcon label={status} field={labels[statusIndex]}/></span><div className="native-cell-content">{content}</div></div> : content);
    }),...(!ownTools?[<td key="personal-tools" style={{position:"static",minWidth:94,width:94}}>{tools(row)}</td>]:[])]);
  };
  function transform(section: Element) {
    if (!["thead", "tbody"].includes(String(section.type))) return section;
    const sectionRows = section.type === "tbody" ? shown.filter(row=>nodes(section.props.children).some(member=>String(member.key)===String(row.key))||bodies.length===1) : nodes(section.props.children);
    if(section.type==="thead")return cloneElement(section,{},sectionRows.map(row=>cloneElement(row,{},[...visible.map(i=>{
      const cell=nodes(row.props.children)[i];
      return cloneElement(cell,{key:i,style:{...cell.props.style,...columnStyle(i)},onDragOver:(event:React.DragEvent)=>{if(event.dataTransfer.types.includes("application/x-suite-column"))event.preventDefault();},onDrop:(event:React.DragEvent)=>{const raw=event.dataTransfer.getData("application/x-suite-column");if(!raw)return;event.preventDefault();const from=Number(raw);if(from===i||from===0||i===0||!indices.includes(from))return;const next=indices.filter(index=>index!==from);next.splice(indices.indexOf(i),0,from);setOrder(next);}},
        <div className="native-column-heading"><button type="button" className="native-column-drag" draggable={i!==0} disabled={i===0} aria-label={`Drag ${labels[i]} column`} onDragStart={event=>{event.dataTransfer.setData("application/x-suite-column",String(i));event.dataTransfer.effectAllowed="move";}}><GripVertical size={12} aria-hidden="true"/></button>{labels[i]!=="Select"&&<ColumnHeadingIcon title={labels[i]}/>}<div className="native-column-label">{cell.props.children}</div><span role="separator" aria-orientation="vertical" aria-label={`Resize ${labels[i]} column`} aria-valuemin={minColumnWidth(i)} aria-valuemax={800} aria-valuenow={Math.round(columnWidth(i))} tabIndex={0} className="native-column-resize" onPointerDown={event=>{event.preventDefault();resize.current={index:i,x:event.clientX,width:event.currentTarget.closest("th")?.getBoundingClientRect().width||columnWidth(i)};event.currentTarget.setPointerCapture(event.pointerId);}} onPointerMove={event=>{const current=resize.current;if(current?.index===i)setWidths(value=>({...value,[i]:Math.max(minColumnWidth(i),Math.min(800,current.width+event.clientX-current.x))}));}} onPointerUp={()=>{resize.current=null;}} onPointerCancel={()=>{resize.current=null;}} onKeyDown={event=>{if(event.key!=="ArrowLeft"&&event.key!=="ArrowRight")return;event.preventDefault();setWidths(value=>({...value,[i]:Math.max(minColumnWidth(i),Math.min(800,columnWidth(i)+(event.key==="ArrowRight"?16:-16)))}));}}/></div>);
    }),...(!ownTools?[<th key="personal-tools" style={{position:"static",minWidth:94,width:94}}><span className="native-column-heading"><ColumnHeadingIcon title="Quick tools"/>Quick tools</span></th>]:[])])));
    if (groupBy < 0) return cloneElement(section, {}, sectionRows.map(renderRow));
    const groups = new Map<string, Element[]>();
    sectionRows.forEach(row => { const label = labelFor(row); const members = groups.get(label); if (members) members.push(row); else groups.set(label, [row]); });
    return cloneElement(section, {}, [...groups].flatMap(([label, members]) => [
      <tr key={`group:${label}`} className="native-group-row"><td colSpan={visible.length+(ownTools?0:1)}><button type="button" aria-expanded={!collapsed.has(label)} aria-label={`${collapsed.has(label) ? "Expand" : "Collapse"} ${group}: ${label}`} onClick={() => setCollapsed(current => { const next = new Set(current); if(next.has(label)) next.delete(label); else next.add(label); return next; })}>{collapsed.has(label) ? <ChevronRight size={13} aria-hidden="true"/> : <ChevronDown size={13} aria-hidden="true"/>}<GroupLabel label={label} field={group} count={members.length}/></button></td></tr>,
      ...(collapsed.has(label) ? [] : [
        ...members.map(renderRow),
        ...(groupCreate?.field === group ? [<tr key={`create:${label}`} className="native-group-create"><td colSpan={visible.length+(ownTools?0:1)}><button type="button" onClick={() => groupCreate.onCreate(label)} aria-label={`${groupCreate.label} in ${label}`}><Plus size={13} aria-hidden="true"/>{groupCreate.label}</button></td></tr>] : []),
      ]),
    ]));
  }
  const tableWidth=visible.reduce((sum,index)=>sum+columnWidth(index),0)+(ownTools?0:94);
  function move(index: number, delta: number) { const next = [...indices]; const at = next.indexOf(index), to = at + delta; if (to < 0 || to >= next.length || index === 0 || next[to] === 0) return; [next[at], next[to]] = [next[to], next[at]]; setOrder(next); }
  return <div className={`native-table-layout native-table-${density}`} data-columns-signature={signature}>
    {!scope.includes(":/pms/projects:") && <CollectionOverview rows={shown.filter(row=>nodes(row.props.children).some(cell=>gridCellText(cell).trim()))} fields={labels.map((title,index)=>({id:String(index),title,value:(row:Element)=>gridCellText(nodes(row.props.children)[index])}))} onOpen={row=>setDetail(row)}/>}
    <RecordViewBar scope={scope} view={personal.view} change={personal.setView} category={categoryIndex>=0?labels[categoryIndex]:undefined} tags={tagsIndex>=0}/>
    <div className="native-table-toolbar" aria-label="Table layout">
      <label className="native-group-control"><Layers size={13} aria-hidden="true"/><span>Group</span><select aria-label="Group loaded rows by" value={groupBy >= 0 ? group : ""} onChange={e => {setGroup(e.target.value);setCollapsed(new Set());}}><option value="">None</option>{groupable.map(i => <option key={i} value={labels[i]}>{labels[i]}</option>)}</select></label>
      {groupBy >= 0 && <><button type="button" className="native-layout-icon" aria-label="Expand all groups" title="Expand all groups" onClick={() => setCollapsed(new Set())}><ChevronsUpDown size={14}/></button><button type="button" className="native-layout-icon" aria-label="Collapse all groups" title="Collapse all groups" onClick={() => setCollapsed(new Set(rows.map(labelFor)))}><ChevronsDownUp size={14}/></button></>}
      <details className="native-layout-menu"><summary><Columns3 size={13} aria-hidden="true"/>Columns {visible.length}/{headers.length}</summary><div className="native-column-options">
        <label className="native-density-control">Row density <select aria-label="Row density" value={density} onChange={e => setDensity(e.target.value)}><option value="compact">Compact</option><option value="comfortable">Comfortable</option><option value="spacious">Spacious</option></select></label>
        {indices.map((index, at) => <div key={index}><label><input type="checkbox" checked={visible.includes(index)} disabled={index === 0} onChange={e => setHidden(h => e.target.checked ? h.filter(i => i !== index) : [...h, index])}/><ColumnHeadingIcon title={labels[index]}/>{labels[index]}</label><button type="button" aria-label={`Pin ${labels[index]} column`} aria-pressed={pinned.includes(index)} onClick={()=>setPinned(value=>value.includes(index)?value.filter(i=>i!==index):[...value,index])}><Pin size={13} aria-hidden="true"/></button><button type="button" disabled={index === 0 || at <= 1} aria-label={`Move ${labels[index]} left`} onClick={() => move(index, -1)}>←</button><button type="button" disabled={index === 0 || at === indices.length - 1} aria-label={`Move ${labels[index]} right`} onClick={() => move(index, 1)}>→</button></div>)}
        <button type="button" onClick={() => {setWidths({});setPinned([]);setHidden(defaultHidden);setOrder([]);setDensity("compact");setGroup(businessDefault);setCollapsed(new Set());}}>Reset table layout</button>
      </div></details>
      <span className="native-loaded-count" title="Grouping applies to the rows loaded on this page">{rows.length.toLocaleString()} loaded</span>
    </div>{notice&&<p role="status" className="suite-record-empty">{notice}</p>}
    {["table","favorites","frequent"].includes(personal.view)?<table {...attributes} style={{...attributes.style,width:tableWidth,minWidth:tableWidth,tableLayout:"fixed"}}>{sections.map(transform)}</table>:<div className={`suite-native-cards ${personal.view==="list"?"suite-record-list":""}`}>{(()=>{
      const index=personal.view==="category"?categoryIndex:personal.view==="tags"?tagsIndex:-1;
      const groups=new Map<string,Element[]>();for(const row of shown){const value=index>=0?gridCellText(nodes(row.props.children)[index]):"";const labels=personal.view==="tags"?value.split(",").map(value=>value.trim()).filter(Boolean):[value];for(const label of labels.length?labels:["Untagged"])groups.set(label,[...(groups.get(label)||[]),row]);}
      return [...groups].map(([label,records])=><section className="suite-record-group" key={label}>{label&&<h3><GroupLabel label={label} count={records.length}/></h3>}<div className={`suite-native-cards ${personal.view==="list"?"suite-record-list":""}`}>{records.map(row=><article key={idFor(row)} className="suite-native-card" onClickCapture={event=>capture(row,event)} onDoubleClickCapture={row.props.onDoubleClickCapture}>{visible.map(i=><div key={i}><small>{labels[i]}</small>{nodes(row.props.children)[i]?.props.children}</div>)}{tools(row)}</article>)}</div></section>);
    })()}</div>}
    {rows.length>0&&!shown.length&&<div className="suite-record-empty">No matching {personal.view}.<button type="button" onClick={()=>personal.setView("table")}>Browse loaded records</button></div>}
    <Dialog open={!!detail} onOpenChange={open=>{if(!open)setDetail(null);}}><DialogContent><DialogTitle>Record details</DialogTitle>{detail&&<dl className="udg-details-fields">{visible.filter(i=>!/select|action/i.test(labels[i])).map(i=><div key={i}><dt>{labels[i]}</dt><dd>{gridCellText(nodes(detail.props.children)[i])||"Not set"}</dd></div>)}</dl>}</DialogContent></Dialog>
  </div>;
}
