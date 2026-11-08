import { useEffect, useState } from "react";
import { useAuthStore } from "@/store/authStore";
export type RecordView = "table"|"cards"|"list"|"category"|"tags"|"favorites"|"frequent";
type Preferences={view:RecordView;favorites:string[];activity:Record<string,{count:number;last:number}>};
const modes:RecordView[]=["table","cards","list","category","tags","favorites","frequent"];
const defaults=():Preferences=>({view:"table",favorites:[],activity:{}});
function read(key:string,defaultView:RecordView="table"):Preferences{try{const value=JSON.parse(localStorage.getItem(key)||"{}");return {view:modes.includes(value.view)?value.view:defaultView,favorites:Array.isArray(value.favorites)?[...new Set<string>(value.favorites.filter((id:unknown)=>typeof id==="string"&&id.length>0&&id.length<180))].slice(0,300):[],activity:Object.fromEntries(Object.entries(value.activity||{}).filter(([id,v])=>id.length<180&&v&&typeof v==="object"&&Number.isFinite((v as any).count)&&(v as any).count>0&&Number.isFinite((v as any).last)).slice(0,300))} as Preferences;}catch{return {...defaults(),view:defaultView};}}
/** Personal browser state contains identifiers only; data is always reloaded under current access. */
export function useRecordPreferences(scope:string,defaultView:RecordView="table"){
 const user=useAuthStore(s=>s.user),key=`suite-record-views:v1:${user?.access?.companyId||sessionStorage.getItem("suite-organization")||0}:${user?.id||0}:${scope}`;
 const [state,setState]=useState(()=>({key,value:read(key,defaultView)}));
 const current=state.key===key?state.value:read(key,defaultView);
 useEffect(()=>{setState({key,value:read(key,defaultView)});const sync=(event:StorageEvent)=>{if(event.key===key)setState({key,value:read(key,defaultView)});};window.addEventListener("storage",sync);return()=>window.removeEventListener("storage",sync);},[key]);
 const update=(change:(previous:Preferences)=>Preferences)=>setState(previous=>{const next=change(previous.key===key?previous.value:read(key,defaultView));try{localStorage.setItem(key,JSON.stringify(next));}catch{/* Preferences remain usable for this visit. */}return {key,value:next};});
 return {...current,key,setView:(view:RecordView)=>update(previous=>({...previous,view})),toggle:(id:string)=>update(previous=>({...previous,favorites:previous.favorites.includes(id)?previous.favorites.filter(value=>value!==id):[id,...previous.favorites].slice(0,300)})),use:(id:string)=>update(previous=>({...previous,activity:Object.fromEntries(Object.entries({...previous.activity,[id]:{count:(previous.activity[id]?.count||0)+1,last:Date.now()}}).sort((a,b)=>b[1].last-a[1].last).slice(0,300))}))};
}
export function recordIdentity(item:unknown):string|undefined{if(!item||typeof item!=="object")return;const row=item as any;const id=row.key??row.id??row.agent?.id??row.record?.id;if(id==null||String(id)==="")return;return String(id);}
