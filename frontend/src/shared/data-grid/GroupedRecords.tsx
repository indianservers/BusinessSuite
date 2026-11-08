import { hasRecordOpenControl } from "./cell-content";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";
import { writeClipboard } from "@/lib/clipboard";
import RecordViewBar from "./RecordViewBar";
import { useRecordPreferences, recordIdentity } from "./record-preferences";
import { Star, Eye, Copy } from "lucide-react";
import { useEffect, useMemo, useState, type ReactNode } from "react";
import { useLocation } from "react-router-dom";
import { ChevronDown, ChevronRight, ChevronsDownUp, ChevronsUpDown, Layers } from "lucide-react";
import { useAuthStore } from "@/store/authStore";
import GroupLabel from "./GroupLabel";
import "./grouped-records.css";

export type CollectionGroupField<T> = { id:string; label:string; value:(item:T)=>unknown };
/** Groups page-owned cards without introducing another API or write path. */
export default function GroupedRecords<T>({scope,items,fields,renderItem,gridClassName="",personalViews=true}:{scope:string;items:T[];fields:CollectionGroupField<T>[];renderItem:(item:T,index:number)=>ReactNode;gridClassName?:string;personalViews?:boolean}) {
  const user=useAuthStore(state=>state.user),location=useLocation();
  const key=`suite-card-groups:${user?.access?.companyId}:${user?.id}:${location.pathname}:${scope}`;
  const stored=useMemo(()=>{try{return localStorage.getItem(key)||"";}catch{return "";}},[key]);
  const [group,setGroup]=useState(stored),[collapsed,setCollapsed]=useState<Set<string>>(new Set()),[loaded,setLoaded]=useState(key);
  useEffect(()=>{setGroup(stored);setCollapsed(new Set());setLoaded(key);},[key]);
  useEffect(()=>{if(loaded===key)try{localStorage.setItem(key,group);}catch{/* Personal layout is optional. */}},[key,loaded,group]);
  const [previewItem,setPreviewItem]=useState<T|undefined>(),[notice,setNotice]=useState("");
  const personal=useRecordPreferences(`${location.pathname}:${scope}`,"cards");
  const category=fields.find(field=>/category|department|type|stage|status|module|owner|group/i.test(field.label));
  const tagField=fields.find(field=>/tags?|labels/i.test(field.label));
  const mode=personalViews?personal.view:"cards";
  const usable=items.some(item=>recordIdentity(item)!==undefined);
  const displayed=items.filter(item=>mode!=="favorites"||personal.favorites.includes(recordIdentity(item)||""))
    .filter(item=>mode!=="frequent"||!!personal.activity[recordIdentity(item)||""]);
  if(mode==="frequent")displayed.sort((a,b)=>(personal.activity[recordIdentity(b)||""]?.count||0)-(personal.activity[recordIdentity(a)||""]?.count||0)||(personal.activity[recordIdentity(b)||""]?.last||0)-(personal.activity[recordIdentity(a)||""]?.last||0));
  const field=mode==="category"?category:mode==="tags"?tagField:fields.find(field=>field.id===group);
  const render=(item:T,index:number)=>{const id=recordIdentity(item),row=item as any;const label=String(row.name||row.title||row.full_name||[row.first_name,row.last_name].filter(Boolean).join(" ")||row.agent?.name||row.field_label||id||"record");const card=renderItem(item,index);return <div className="suite-record-card-shell" key={id||index} onClickCapture={event=>{if(id&&(event.target as HTMLElement).closest("button,a,input,select")&&!(event.target as HTMLElement).closest("[data-record-personal]"))personal.use(id);}}>{personalViews&&id&&<button type="button" className="suite-record-star" data-record-personal aria-label={`${personal.favorites.includes(id)?"Unfavorite":"Favorite"} ${label}`} aria-pressed={personal.favorites.includes(id)} onClick={()=>personal.toggle(id)}><Star size={15} fill={personal.favorites.includes(id)?"currentColor":"none"}/></button>}{card}{personalViews&&<div className="suite-record-card-tools" data-record-personal>{!hasRecordOpenControl(card)&&<button type="button" className="suite-record-star" aria-label={`Preview ${label}`} title="Preview record" onClick={()=>{if(id)personal.use(id);setPreviewItem(item);}}><Eye size={14}/></button>}<button type="button" className="suite-record-star" aria-label={`Copy name for ${label}`} title="Copy record name" onClick={()=>{void writeClipboard(label).then(()=>setNotice("Record name copied")).catch(()=>setNotice("Could not copy the record name"));}}><Copy size={14}/></button></div>}</div>;};
  const groups=new Map<string,{item:T;index:number}[]>();
  displayed.forEach((item,index)=>{const raw=field?.value(item);const values=mode==="tags"?(Array.isArray(raw)?raw:String(raw||"").split(",").map(value=>value.trim()).filter(Boolean)):[raw];for(const value of values.length?values:["Untagged"]){const label=value==null||String(value).trim()===""?"Not set":String(value).replace(/_/g," ");const list=groups.get(label);if(list)list.push({item,index});else groups.set(label,[{item,index}]);}});

  return <section className="suite-grouped-records" data-card-collection={scope}>
    {personalViews&&<RecordViewBar scope={scope} view={mode==="table"?"cards":mode} change={personal.setView} category={category?.label} tags={!!tagField} table={false} personal={usable}/> }
    <div className="suite-card-group-tools" aria-label="Card grouping"><label><Layers size={13} aria-hidden="true"/><span>Group</span><select aria-label="Group cards by" value={field?field.id:""} onChange={event=>{setGroup(event.target.value);if(personalViews)personal.setView("cards");setCollapsed(new Set());}}><option value="">None</option>{fields.map(field=><option key={field.id} value={field.id}>{field.label}</option>)}</select></label>
      {field&&<><button type="button" aria-label="Expand all card groups" title="Expand all groups" onClick={()=>setCollapsed(new Set())}><ChevronsUpDown size={14}/></button><button type="button" aria-label="Collapse all card groups" title="Collapse all groups" onClick={()=>setCollapsed(new Set(groups.keys()))}><ChevronsDownUp size={14}/></button></>}
      <small title="Grouping applies to the records loaded on this page">{displayed.length.toLocaleString()} loaded</small>
    </div>
    {!field?<div className={`${gridClassName} ${mode==="list"?"suite-record-list":""}`}>{displayed.map(render)}</div>:[...groups].map(([label,members])=><section className="suite-card-group" key={label}><button type="button" className="suite-card-group-heading" aria-label={`${collapsed.has(label)?"Expand":"Collapse"} ${field.label}: ${label}`} aria-expanded={!collapsed.has(label)} onClick={()=>setCollapsed(current=>{const next=new Set(current);next.has(label)?next.delete(label):next.add(label);return next;})}>{collapsed.has(label)?<ChevronRight size={13}/>:<ChevronDown size={13}/>}<GroupLabel label={label} field={field.label} count={members.length}/></button>{!collapsed.has(label)&&<div className={`${gridClassName} ${mode==="list"?"suite-record-list":""}`}>{members.map(({item,index})=>render(item,index))}</div>}</section>)}
    {notice&&<p role="status" className="suite-record-empty">{notice}</p>}
    <Dialog open={previewItem!==undefined} onOpenChange={open=>{if(!open)setPreviewItem(undefined);}}><DialogContent className="max-h-[90dvh] overflow-auto"><DialogTitle>Record preview</DialogTitle>{previewItem!==undefined&&renderItem(previewItem,0)}</DialogContent></Dialog>
    {items.length>0&&!displayed.length&&<div className="suite-record-empty">No matching {mode}.<button type="button" onClick={()=>personal.setView("cards")}>Browse loaded records</button></div>}
  </section>;
}
