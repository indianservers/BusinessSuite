import { useEffect, useSyncExternalStore } from "react";
import { useLocation } from "react-router-dom";
import { browserReview, requestedBrowserCopy, consumeBrowserCopy, subscribeSync } from "./store";
const normalize=(key:string)=>key.toLowerCase().replace(/required|optional/g,"").replace(/[^a-z0-9]/g,"");
/** Restore an explicitly reviewed browser copy through the form's native input events. */
export default function BrowserDraftRecovery(){
 const id=useSyncExternalStore(subscribeSync,browserReview,browserReview),location=useLocation();
 useEffect(()=>{
  if(!id)return;const item=requestedBrowserCopy();if(!item?.draft)return;
  const fields=new Map<string,unknown>();
  const flatten=(value:unknown,path="")=>{if(Array.isArray(value)){value.forEach((item,index)=>flatten(item,path+"."+index));return;}if(value&&typeof value==="object"){for(const [key,child]of Object.entries(value)){if(child===null||typeof child!=="object"){fields.set(normalize(key),child);fields.set(normalize(path+"."+key),child);}else flatten(child,path+"."+key);}}};flatten(item.draft);
  let timer:ReturnType<typeof setTimeout>|undefined;
  const restore=()=>{const dialogs=[...document.querySelectorAll<HTMLElement>('[role="dialog"]')].filter(node=>node.getClientRects().length);const root=dialogs.at(-1)||document.querySelector('main form');if(!root)return;
   let count=0;for(const input of root.querySelectorAll<HTMLInputElement|HTMLSelectElement|HTMLTextAreaElement>('input,select,textarea')){
    if((input instanceof HTMLInputElement&&["password","file","hidden"].includes(input.type))||input.disabled)continue;
    const label=input.id?document.querySelector<HTMLLabelElement>(`label[for="${CSS.escape(input.id)}"]`)?.textContent:input.closest('label')?.textContent;
    const keys=[input.name,input.id,input.getAttribute('aria-label')||"",label||""].map(normalize);let key=keys.find(key=>fields.has(key));if(!key&&keys.some(key=>key==="employeename"||key==="recordname"))key=["fullname","name"].find(key=>fields.has(key));if(!key)continue;
    const value=fields.get(key);const prototype=input instanceof HTMLSelectElement?HTMLSelectElement.prototype:input instanceof HTMLTextAreaElement?HTMLTextAreaElement.prototype:HTMLInputElement.prototype;
    if(input instanceof HTMLInputElement&&["checkbox","radio"].includes(input.type)){Object.getOwnPropertyDescriptor(prototype,"checked")?.set?.call(input,Boolean(value));}else Object.getOwnPropertyDescriptor(prototype,"value")?.set?.call(input,String(value??""));
    input.dispatchEvent(new Event('input',{bubbles:true}));input.dispatchEvent(new Event('change',{bubbles:true}));count++;
   }
   if(count){consumeBrowserCopy();observer.disconnect();if(timer)clearTimeout(timer);}
  };
  const observer=new MutationObserver(()=>{if(timer)clearTimeout(timer);timer=setTimeout(restore,100);});observer.observe(document.body,{childList:true,subtree:true});timer=setTimeout(restore,250);const stop=setTimeout(()=>observer.disconnect(),12000);
  return()=>{observer.disconnect();if(timer)clearTimeout(timer);clearTimeout(stop);};
 },[id,location.pathname,location.search]);
 return null;
}
