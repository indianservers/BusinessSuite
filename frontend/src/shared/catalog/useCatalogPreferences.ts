import { useEffect, useState } from "react";
import { useAuthStore } from "@/store/authStore";

export type CatalogView = "cards" | "list" | "categories" | "tags" | "frequent" | "favorites";
type Preferences = { view: CatalogView; favorites: string[]; opened: Record<string, {count:number;last:number}> };
const views: CatalogView[] = ["cards","list","categories","tags","frequent","favorites"];
const empty = (): Preferences => ({view:"cards",favorites:[],opened:{}});
function read(key:string):Preferences {
  try {
    const saved=JSON.parse(localStorage.getItem(key)||"{}");
    const opened=Object.fromEntries(Object.entries(saved.opened||{}).filter(([id,value])=>/^(product|service):\d+$/.test(id)&&typeof value==="object"&&value!==null&&Number.isFinite((value as {count:number}).count)&&Number.isFinite((value as {last:number}).last)).slice(0,500));
    return {view:views.includes(saved.view)?saved.view:"cards",favorites:Array.isArray(saved.favorites)?saved.favorites.filter((id:unknown)=>typeof id==="string"&&/^(product|service):\d+$/.test(id)).slice(0,500):[],opened} as Preferences;
  } catch {return empty();}
}
export const catalogItemKey=(item:{kind:string;id:number})=>`${item.kind}:${item.id}`;
export default function useCatalogPreferences(){
  const user=useAuthStore(s=>s.user);
  const key=`catalog-personal:v1:${user?.access?.companyId||sessionStorage.getItem("suite-organization")||1}:${user?.id||0}`;
  const [saved,setSaved]=useState(()=>({key,value:read(key)}));
  const value=saved.key===key?saved.value:read(key);
  useEffect(()=>{setSaved({key,value:read(key)});const sync=(event:StorageEvent)=>{if(event.key===key)setSaved({key,value:read(key)});};window.addEventListener("storage",sync);return()=>window.removeEventListener("storage",sync);},[key]);
  const update=(change:(value:Preferences)=>Preferences)=>setSaved(current=>{
    const next=change(current.key===key?current.value:read(key));
    try{localStorage.setItem(key,JSON.stringify(next));}catch{/* Preferences still work for this visit. */}
    return {key,value:next};
  });
  return {...value,scope:key,setView:(view:CatalogView)=>update(current=>({...current,view})),toggleFavorite:(id:string)=>update(current=>({...current,favorites:current.favorites.includes(id)?current.favorites.filter(value=>value!==id):[id,...current.favorites].slice(0,500)})),recordOpen:(id:string)=>update(current=>({...current,opened:Object.fromEntries(Object.entries({...current.opened,[id]:{count:(current.opened[id]?.count||0)+1,last:Date.now()}}).sort((a,b)=>b[1].last-a[1].last).slice(0,500))}))};
}
