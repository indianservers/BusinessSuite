import { useSyncExternalStore } from "react";
import type { AxiosRequestConfig as BaseAxiosRequestConfig } from "axios";
import { useAuthStore } from "@/store/authStore";
import { confirmedMutation, resourcePath, matchesRecordQuery, type RecordSaved } from "@/lib/record-changes";
import type { QueryClient, QueryKey } from "@tanstack/react-query";

// The portal imports this store without loading the suite API's Axios augmentation.
type AxiosRequestConfig = BaseAxiosRequestConfig & { readOnlyPreview?: boolean; recordSync?: boolean; _recordSyncId?: string };

export type SyncPhase = "pending" | "saved" | "error" | "review";
export type SyncItem = { id:string; scope:string; resource:string; method:string; ids:(number|string)[]; operation:"create"|"update"|"delete"; patch:Record<string,unknown>; draft?:unknown; title:string; href:string; phase:SyncPhase; started:number; error?:string; confirmed?:Record<string,unknown>; durable?:boolean; origin?:HTMLElement|null };
let saveIntent:{at:number;element:HTMLElement|null}|undefined;
if(typeof document!=="undefined"){
 document.addEventListener("submit",event=>{const form=event.target as HTMLElement;saveIntent={at:Date.now(),element:form.closest<HTMLElement>('[role="dialog"]')||form};},true);
 document.addEventListener("click",event=>{const button=(event.target as HTMLElement)?.closest<HTMLButtonElement>('button');if(button&&/^(save|create|submit|update|delete|remove|archive|restore|apply|assign|publish|post|record)\b/i.test(button.textContent?.trim()||""))saveIntent={at:Date.now(),element:button.closest<HTMLElement>('[role="dialog"]')||button.closest('form')};},true);
}
let requestedReview:string|undefined;
export const browserReview=()=>requestedReview;
export function requestedBrowserCopy(){return items.find(item=>item.id===requestedReview&&item.scope===syncScope());}
export function consumeBrowserCopy(){requestedReview=undefined;emit();}
const listeners=new Set<()=>void>();
let items:SyncItem[]=[];
const requests=new Map<string,()=>Promise<unknown>>();
const before=new Map<string,Map<string,{key:QueryKey;data:unknown}>>();
let client:QueryClient|undefined,applying=false;
const secret=/password|token|secret|credential|authorization|cvv|card_number|bank.?account|account.?number|api.?key|private.?key|one.?time.?code|otp/i;
const safeDraft=(data:unknown):unknown=>Array.isArray(data)?data.map(safeDraft):data&&typeof data==="object"?Object.fromEntries(Object.entries(data).filter(([key])=>!secret.test(key)).map(([key,value])=>[key,safeDraft(value)])):data;
const safe=(data:unknown):Record<string,unknown>=>Object.fromEntries(Object.entries(data&&typeof data==="object"&&!Array.isArray(data)?data:{}).filter(([key,value])=>!secret.test(key)&&["string","number","boolean"].includes(typeof value)));
export function syncScope(){const u=useAuthStore.getState().user;return JSON.stringify([u?.id,u?.access?.companyId,sessionStorage.getItem("suite-tenant"),sessionStorage.getItem("suite-organization"),sessionStorage.getItem("suite-branch")]);}
const emit=()=>listeners.forEach(fn=>fn());
const visible=()=>items;
export const subscribeSync=(listener:()=>void)=>{listeners.add(listener);return()=>{listeners.delete(listener);};};
export function useRecordSync(){useAuthStore(s=>s.user?.id);return useSyncExternalStore(subscribeSync,visible,visible).filter(item=>item.scope===syncScope());}

let database:Promise<IDBDatabase>|undefined;
function db(){return database??=new Promise<IDBDatabase>((resolve,reject)=>{const r=indexedDB.open("suite-pending-records-v1",1);r.onupgradeneeded=()=>r.result.createObjectStore("mutations",{keyPath:"id"});r.onsuccess=()=>resolve(r.result);r.onerror=()=>reject(r.error);});}
async function persist(item:SyncItem,remove=false){try{const database=await db();await new Promise<void>((resolve,reject)=>{const tx=database.transaction("mutations","readwrite");if(remove)tx.objectStore("mutations").delete(item.id);else{const {origin,...record}=item;tx.objectStore("mutations").put(record);}tx.oncomplete=()=>resolve();tx.onerror=()=>reject(tx.error);tx.onabort=()=>reject(tx.error);});return true;}catch{return false;}}
export async function recoverRecordSync(){try{const database=await db(),rows=await new Promise<SyncItem[]>((resolve,reject)=>{const r=database.transaction("mutations").objectStore("mutations").getAll();r.onsuccess=()=>resolve(r.result);r.onerror=()=>reject(r.error);});const scope=syncScope();for(const row of rows)if(row.scope===scope&&!items.some(item=>item.id===row.id))items=[...items,{...row,phase:"review",error:"Saved in this browser. Review the server record before resubmitting."}];emit();}catch{/* The active editor still retains its draft. */}}

export function describeSync(config:AxiosRequestConfig):Omit<SyncItem,"id"|"scope"|"phase"|"started"|"origin"|"durable">|undefined{
 const method=(config.method||"get").toLowerCase(),url=config.url||"";
 if(["get","head","options"].includes(method)||config.readOnlyPreview||config.recordSync===false||!/^(?:\/api\/v1)?\//.test(url))return;
 let path=resourcePath(url).replace(/^\/crm\/lead-management\/leads/,"/crm/leads").replace(/^\/crm\/contact-directory/,"/crm/contacts");
 if(/^\/(?:auth|platform|metrics|ai-operator)(?:\/|$)/.test(path)||/^\/project-management\/notes(?:\/|$)/.test(path)||/(?:\/|^)(?:query|search|preview|calculate|validate|render|export|suggestions|options|lookup|resolve|sync-check)(?:\/|$)/.test(path))return;
 if(/\/(?:preferences|layout|ui-state)$/.test(path)&&config.recordSync!==true)return;
 let input:unknown=config.data;if(typeof input==="string")try{input=JSON.parse(input);}catch{input={};}
 const body=input&&typeof input==="object"?input as Record<string,unknown>:{};
 const change=confirmedMutation(url,method,body,{});
 const identity=path.match(/\/(\d+)(?:\/|$)/),bulk=/\/(?:bulk|batch|trash|archive|restore|unarchive)$/.test(path);
 const resource=identity?path.slice(0,identity.index):bulk?path.replace(/\/[^/]+$/,""):path;
 const patch=safe(body.values||body.task||body.patch||body);
 const operation=change.operation==="delete"?"delete":method==="post"&&!identity&&!bulk?"create":"update";
 const title=String(patch.title||patch.full_name||patch.fullName||patch.name||[patch.first_name,patch.last_name].filter(Boolean).join(" ")||patch.voucher_number||patch.invoice_number||patch.subject||patch.filename||`${operation==="create"?"New ":""}${resource.split("/").pop()?.replace(/-/g," ")||"record"}${identity?` #${identity[1]}`:""}`).slice(0,180);
 return {resource,method,draft:safeDraft(body),ids:identity?[identity[1]]:change.ids||[],operation,patch,title,href:location.pathname+location.search};
}
function mutation(item:SyncItem,record=item.patch):RecordSaved{return {url:item.resource,resource:item.resource,method:item.method,ids:item.ids,operation:item.operation==="delete"?"delete":"update",record:{},patch:record};}
function project(data:unknown,item:SyncItem):unknown{
 if(!data||typeof data!=="object")return data;
 const confirmed=item.confirmed as Record<string,unknown>|undefined;
 const confirmedRecord=(confirmed?.task||confirmed?.record||confirmed?.employee||confirmed) as Record<string,unknown>|undefined;
 const patch=item.phase==="saved"&&confirmedRecord?.id!=null?confirmedRecord:item.patch;
 const row=(value:Record<string,any>)=>{if(!item.ids.map(String).includes(String(value.id)))return value;if(item.phase==="saved"&&Number(value.version)>Number(confirmedRecord?.version||0))return value;
  const next={...value,...Object.fromEntries(Object.entries(patch).filter(([key])=>key in value&&!/[._]id$|^id$|expected_version/.test(key)))};
  if(value.values&&typeof value.values==="object"&&!Array.isArray(value.values))next.values={...value.values,...Object.fromEntries(Object.entries(patch).filter(([key])=>key in value.values))};return next;
 };
 if(Array.isArray(data))return data.filter(value=>!(item.operation==="delete"&&item.ids.map(String).includes(String(value?.id)))).map(value=>value&&typeof value==="object"?row(value):value);
 const value=data as Record<string,any>;
 if(value.id!=null)return item.operation==="delete"?value:row(value);
 if(value.data)return {...value,data:project(value.data,item)};
 const key=["rows","items","results","records"].find(key=>Array.isArray(value[key]));if(!key)return data;
 const next=project(value[key],item) as unknown[],removed=value[key].length-next.length;
 return {...value,[key]:next,...Object.fromEntries(["total","pageTotal","count"].filter(key=>typeof value[key]==="number").map(key=>[key,Math.max(0,value[key]-removed)]))};
}
export function projectSyncRecords<T>(rows:T[],entries:SyncItem[],resource:string):T[]{let result:unknown=rows;for(const item of entries)if(item.resource===resource&&["pending","saved"].includes(item.phase)&&item.operation!=="create")result=project(result,item);return result as T[];}
export function useSyncedRecords<T>(rows:T[],resource:string){return projectSyncRecords(rows,useRecordSync(),resource);}
function matching(key:readonly unknown[],item:SyncItem){return matchesRecordQuery(key,mutation(item));}
function apply(item:SyncItem){if(!client||item.operation==="create")return;applying=true;try{let snapshots=before.get(item.id);if(!snapshots){snapshots=new Map();before.set(item.id,snapshots);}for(const query of client.getQueryCache().getAll()){if(!query.isActive()||!matching(query.queryKey,item))continue;const data=query.state.data;if(!snapshots.has(query.queryHash))snapshots.set(query.queryHash,{key:query.queryKey,data});const next=project(data,item);if(JSON.stringify(next)!==JSON.stringify(data))client.setQueryData(query.queryKey,next);}}finally{applying=false;}}
export async function startRecordSync(config:AxiosRequestConfig,retry:()=>Promise<unknown>):Promise<string|undefined>{
 if(config._recordSyncId){const old=items.find(item=>item.id===config._recordSyncId);if(old&&old.scope===syncScope()){items=items.map(item=>item.id===old.id?{...item,phase:"pending",error:undefined}:item);apply({...old,phase:"pending"});emit();return old.id;}return;}
 const description=describeSync(config);if(!description||!useAuthStore.getState().user)return;
 const origin=saveIntent&&Date.now()-saveIntent.at<3000&&saveIntent.element?.isConnected?saveIntent.element:null;
 const item:SyncItem={...description,id:globalThis.crypto?.randomUUID?.()||`local-${Date.now()}-${Math.random().toString(36).slice(2)}`,scope:syncScope(),phase:"pending",started:Date.now(),origin};
 for(const old of items.filter(old=>old.phase==="error"&&old.origin&&old.origin===item.origin&&old.resource===item.resource)){void persist(old,true);requests.delete(old.id);before.delete(old.id);items=items.filter(row=>row.id!==old.id);}
 requests.set(item.id,retry);item.durable=await persist(item);if(item.scope!==syncScope())return;
 items=[...items,item];apply(item);emit();return item.id;
}
function rollback(data:unknown,old:unknown,item:SyncItem):unknown{
 if(!data||typeof data!=="object"||!old||typeof old!=="object")return data;
 if(!Array.isArray(data)&&"data" in data&&"data" in old){const current=data as Record<string,unknown>,prior=old as Record<string,unknown>;return {...current,data:rollback(current.data,prior.data,item)};}
 const value=data as Record<string,any>,prior=old as Record<string,any>,key=Array.isArray(data)?null:["rows","items","results","records"].find(key=>Array.isArray(value[key]));
 const restoreRow=(row:Record<string,unknown>,previous:Record<string,unknown>)=>{const result={...row};if(row.values&&previous.values&&typeof row.values==="object"&&!Array.isArray(row.values)){result.values={...(row.values as object)};for(const [key,requested]of Object.entries(item.patch))if(JSON.stringify((row.values as Record<string,unknown>)[key])===JSON.stringify(requested))(result.values as Record<string,unknown>)[key]=(previous.values as Record<string,unknown>)[key];}for(const [key,requested]of Object.entries(item.patch))if(key in previous&&JSON.stringify(result[key])===JSON.stringify(requested))result[key]=previous[key];return result;};
 if(key===undefined){if(value.id!=null&&item.ids.map(String).includes(String(value.id)))return restoreRow(value,prior);return data;}
 const rows=(key===null?data:value[key]) as Record<string,any>[],previous=(key===null?old:prior[key]) as Record<string,any>[];if(!Array.isArray(previous))return data;
 const ids=new Set(item.ids.map(String));let restored=rows.map(row=>{const original=previous.find(old=>String(old.id)===String(row.id));return ids.has(String(row.id))&&original?restoreRow(row,original):row;});
 const missing=item.operation==="delete"?previous.filter(row=>ids.has(String(row.id))&&!restored.some(current=>String(current.id)===String(row.id))):[];restored=[...missing,...restored];
 if(key===null)return restored;return {...value,[key]:restored,...Object.fromEntries(["total","pageTotal","count"].filter(name=>typeof value[name]==="number").map(name=>[name,value[name]+missing.length]))};
}
export function finishRecordSync(id:string|undefined,record?:unknown,error?:unknown){if(!id)return;const item=items.find(item=>item.id===id);if(!item||item.scope!==syncScope()||item.phase!=="pending")return;
 const result=record&&typeof record==="object"?record as Record<string,unknown>:{};
 if(!error&&(result.success===false||result.saved===false||result.ok===false||Number(result.failed_count||result.error_count||0)>0||[result.failed_ids,result.errors,result.failed].some(value=>Array.isArray(value)&&value.length>0))){finishRecordSync(id,undefined,{response:{data:{detail:"Some records were not saved. Review the failed records before retrying."}}});void client?.invalidateQueries({predicate:query=>matching(query.queryKey,item)});return;}
 if(error){
  // Roll back only this operation's projected fields. Do not erase a newer edit.
  if(client){applying=true;try{for(const snapshot of before.get(id)?.values()||[]){const others=items.filter(other=>other.id!==id&&other.scope===item.scope&&["pending","saved"].includes(other.phase)&&matching(snapshot.key,other));let restored=rollback(client.getQueryData(snapshot.key),snapshot.data,item);for(const other of others)restored=project(restored,other);client.setQueryData(snapshot.key,restored);}}finally{applying=false;}}
  const detail=(error as {response?:{data?:{detail?:unknown}}})?.response?.data?.detail;items=items.map(row=>row.id===id?{...row,phase:"error",error:typeof detail==="string"?detail:"Could not sync. Your browser copy is retained."}:row);void persist(items.find(row=>row.id===id)!);before.delete(id);
 }else{const value=record&&typeof record==="object"?record as Record<string,unknown>:{};items=items.map(row=>row.id===id?{...row,phase:"saved",confirmed:value}:row);void persist(item,true);requests.delete(id);setTimeout(()=>{items=items.filter(row=>row.id!==id);before.delete(id);emit();},2500);}
 emit();
}
export function confirmRecoveredSync(url:string,data:unknown,status=200){
 const path=resourcePath(url),values=Array.isArray(data)?data:data&&typeof data==="object"?((data as Record<string,any>).rows||(data as Record<string,any>).items||(data as Record<string,any>).records||[data]):[];
 for(const item of items.filter(item=>item.phase==="review"&&item.scope===syncScope())){
  const canonicalPath=path.replace(/^\/crm\/lead-management\/leads/,"/crm/leads").replace(/^\/crm\/contact-directory/,"/crm/contacts");
  if(canonicalPath!==item.resource&&!item.ids.some(id=>canonicalPath===item.resource+"/"+id))continue;
  const row=values.find((row:Record<string,any>)=>row&&item.ids.map(String).includes(String(row.id)));
  const fields=Object.entries(item.patch).filter(([key])=>!["id","expected_version","version","action","operation"].includes(key));
  const confirmed=item.operation==="delete"&&status===404&&item.ids.some(id=>canonicalPath===item.resource+"/"+id)||item.operation==="update"&&row&&fields.length>0&&fields.every(([key,value])=>JSON.stringify(row[key]??row.values?.[key])===JSON.stringify(value));
  if(confirmed){items=items.map(row=>row.id===item.id?{...row,phase:"saved"}:row);void persist(item,true);setTimeout(()=>dismissRecordSync(item.id),2000);emit();}
 }
}
export function retryRecordSync(id:string){const item=items.find(row=>row.id===id);if(!item||item.scope!==syncScope())return;if(["put","patch","delete"].includes(item.method)&&requests.has(id))void requests.get(id)!().catch(()=>{});else reviewRecordSync(id);}
export function reviewRecordSync(id:string){const item=items.find(row=>row.id===id);if(!item||item.scope!==syncScope())return;if(item.origin?.isConnected){item.origin.scrollIntoView({block:"center"});item.origin.querySelector<HTMLElement>('input,textarea,button')?.focus();}else {requestedReview=id;emit();const createPaths:Record<string,string>={"/employees":"/hrms/employees/new","/project-management/tasks":"/pms/tasks/new","/project-management/projects":"/pms/projects/new","/fam/vouchers":"/fam/vouchers/new","/fam/purchase-bills":"/fam/purchase-bills/new","/fam/expenses":"/fam/expenses/new","/power-apps/automations":"/power-apps/automations/new"};const href=item.operation==="create"?(createPaths[item.resource]||(/^\/crm\/(leads|contacts|companies|deals|tickets|campaigns|activities|quotations)$/.test(item.resource)?item.resource+"?new="+item.resource.split("/").pop():item.href)):item.href;window.dispatchEvent(new CustomEvent("suite:review-pending-record",{detail:{href,id}}));}}
export function dismissRecordSync(id:string){const item=items.find(row=>row.id===id);if(!item||item.phase==="pending")return;void persist(item,true);items=items.filter(row=>row.id!==id);before.delete(id);requests.delete(id);emit();}
export function installRecordSync(queryClient:QueryClient){client=queryClient;client.getQueryCache().subscribe(event=>{if(applying||event.type!=="updated")return;for(const item of items)if(item.scope===syncScope()&&["pending","saved"].includes(item.phase)&&matching(event.query.queryKey,item))apply(item);});let scope=syncScope();useAuthStore.subscribe(()=>{const next=syncScope();if(next!==scope){scope=next;items=[];before.clear();requests.clear();emit();void recoverRecordSync();}});for(const name of ["suite:organization-changed","suite:branch-changed"]){window.addEventListener(name,()=>{scope=syncScope();items=[];before.clear();requests.clear();emit();void recoverRecordSync();});}void recoverRecordSync();}
export function rowSync(items:SyncItem[],ids:(string|number)[],hint:string){const normalized=resourcePath(hint).replace(/\/(?:new|create|edit)$/,"");return items.filter(item=>(normalized===item.resource||normalized.startsWith(item.resource+"/"))&&item.ids.some(id=>ids.map(String).includes(String(id)))&&item.phase!=="saved");}
