import { Clock3, FolderTree, LayoutGrid, List, Star, Table2, Tags } from "lucide-react";
import type { RecordView } from "./record-preferences";
import "./record-views.css";
import { useEffect, useId } from "react";
import { createPortal } from "react-dom";
import { useRecordViewHost } from "./RecordViewHost";
const options=[{id:"table",label:"Table",Icon:Table2},{id:"cards",label:"Cards",Icon:LayoutGrid},{id:"list",label:"List",Icon:List},{id:"category",label:"Categories",Icon:FolderTree},{id:"tags",label:"Tags",Icon:Tags},{id:"frequent",label:"Frequent",Icon:Clock3},{id:"favorites",label:"Favorites",Icon:Star}] as const;
export default function RecordViewBar({scope,view,change,category,tags,table=true,personal=true,server=false,compact=false}:{compact?:boolean;scope:string;view:RecordView;change:(view:RecordView)=>void;category?:string;tags?:boolean;table?:boolean;personal?:boolean;server?:boolean}){
 const host=useRecordViewHost(),owner=useId(),register=host?.register,unregister=host?.unregister;
 useEffect(()=>{register?.({owner,table});},[register,owner,table]);
 useEffect(()=>()=>unregister?.(owner),[unregister,owner]);
 const available=options.filter(option=>option.id!=="category"||category).filter(option=>option.id!=="tags"||tags).filter(option=>option.id!=="table"||table).filter(option=>personal||!["frequent","favorites"].includes(option.id));
 const tabs=<div className="suite-record-view-tools" data-record-views={scope}><div className="suite-record-view-tabs" role="tablist" aria-label="Record views">{available.map(({id,label,Icon},index)=><button type="button" role="tab" key={id} aria-selected={view===id} onClick={()=>change(id)} onKeyDown={event=>{if(!["ArrowRight","ArrowLeft","Home","End"].includes(event.key))return;event.preventDefault();const target=event.key==="Home"?0:event.key==="End"?available.length-1:(index+(event.key==="ArrowRight"?1:-1)+available.length)%available.length;change(available[target].id);const buttons=event.currentTarget.parentElement?.querySelectorAll<HTMLButtonElement>('[role="tab"]');buttons?.[target]?.focus();}}><Icon size={14}/>{id==="category"&&category!=="Category"?`By ${category}`:label}</button>)}</div>{["favorites","frequent","category","tags"].includes(view)&&<small>{view==="favorites"?`Your favorites · ${server?"all accessible matching records":"loaded records only"}`:view==="frequent"?`Most used by you · ${server?"all accessible matching records":"loaded records only"}`:"Loaded records"}</small>}</div>;
 const content=compact?<details className="suite-compact-views"><summary>Presentation · {available.find(option=>option.id===view)?.label || view}</summary>{tabs}</details>:tabs;
 return host?.host&&host.registration?.owner===owner?createPortal(content,host.host):content;
}
