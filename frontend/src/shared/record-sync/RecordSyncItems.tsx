import { Check, RotateCw, X } from "lucide-react";
import { useEffect, useState, useRef } from "react";
import { useMobile } from "@/components/mobile/useMobile";
import { MobileSheet } from "@/components/mobile/MobilePrimitives";
import { Button } from "@/components/ui/button";
import { useNavigate } from "react-router-dom";
import { useRecordSync, retryRecordSync, reviewRecordSync, dismissRecordSync, type SyncItem } from "./store";
import "./record-sync.css";
export function SyncRing({item}:{item:SyncItem}){return item.phase==="pending"?<span className="record-sync-ring" role="progressbar" aria-label={`Syncing ${item.title}`} title="Saved in browser. Syncing to server."/>:item.phase==="saved"?<Check size={13} aria-label="Confirmed by server"/>:<span className="record-sync-warning" role="img" aria-label="Not synced">!</span>;}
export default function RecordSyncItems({floating=false,resource,origin}:{floating?:boolean;resource?:string;origin?:HTMLElement|null}){
 const entries=useRecordSync(),navigate=useNavigate();
 const phone=useMobile(480),[expanded,setExpanded]=useState(false);
 const queuedReview=useRef<{id:string;retry:boolean}|null>(null);
 const act=(item:SyncItem,retry:boolean)=>{
  if(phone && floating && (!retry || !["put","patch","delete"].includes(item.method))){queuedReview.current={id:item.id,retry};setExpanded(false);return;}
  if(retry)retryRecordSync(item.id);else reviewRecordSync(item.id);
 };
 const afterClose=()=>{const next=queuedReview.current;queuedReview.current=null;if(next){if(next.retry)retryRecordSync(next.id);else reviewRecordSync(next.id);}};
 useEffect(()=>{if(!floating)return;const review=(event:Event)=>navigate((event as CustomEvent<{href:string}>).detail.href);window.addEventListener("suite:review-pending-record",review);return()=>window.removeEventListener("suite:review-pending-record",review);},[floating,navigate]);
 const rows=entries.filter(item=>(!resource||item.resource===resource)&&(!origin||item.origin===origin));
 useEffect(()=>{if(!phone || !rows.length)setExpanded(false);},[phone,rows.length]);
 if(!rows.length)return null;
 const content=(phone && floating && !expanded ? [] : rows).map(item=><article className={`record-sync-item is-${item.phase}`} key={item.id} data-sync-item={item.id}><SyncRing item={item}/><div><strong>{item.title}</strong><small>{item.phase==="pending"?`${item.operation==="delete"?"Removed locally":"Saved in browser"} · Syncing`:item.phase==="saved"?"Synced":item.error||"Saved in browser. Needs review."}</small></div>{item.phase==="error"&&<button type="button" onClick={()=>act(item,true)} aria-label={`Retry ${item.title}`}><RotateCw size={12}/>{["put","patch","delete"].includes(item.method)?"Retry":"Review"}</button>}{item.phase==="review"&&<button type="button" onClick={()=>act(item,false)}>Review</button>}{item.phase!=="pending"&&<button type="button" onClick={()=>{if(item.phase==="saved"||window.confirm("Discard this browser copy? Server records will not be changed."))dismissRecordSync(item.id);}} aria-label={`${item.phase==="saved"?"Dismiss":"Discard browser copy for"} ${item.title}`}><X size={12}/></button>}</article>);
 if(phone && floating){
  const pending=rows.find(item=>item.phase==="pending"),issue=rows.find(item=>item.phase==="error"||item.phase==="review"),lead=pending||issue||rows[rows.length-1];
  const state=pending ? "Syncing" : issue ? "Needs review" : "Synced";
  return <section className="record-sync-floating record-sync-phone" aria-label="Browser-saved changes"><Button className="record-sync-phone-trigger" variant="outline" aria-expanded={expanded} onClick={()=>setExpanded(true)}><SyncRing item={lead}/><span>{rows.length} {rows.length===1?"change":"changes"} · {state}</span></Button>{expanded&&<MobileSheet open title="Sync status" onClose={()=>setExpanded(false)} fallbackFocus={document.getElementById("suite-main")} onClosed={afterClose}><div className="record-sync-items record-sync-phone-details">{content}</div></MobileSheet>}</section>;
 }
 return <section className={`record-sync-items ${floating?"record-sync-floating":""}`} aria-label="Browser-saved changes">{content}</section>;
}
