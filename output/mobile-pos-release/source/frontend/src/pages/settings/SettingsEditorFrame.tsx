import { Button } from "@/components/ui/button";
import { registerSettingsDraftGuard } from "./settingsNavigationGuard";
import { useEffect, useRef, useState, type ReactNode } from "react";

import { useAuthStore } from "@/store/authStore";
import { api } from "@/services/api";

import { CheckCircle2, CircleAlert, History, Loader2 } from "lucide-react";

import { useQuery } from "@tanstack/react-query";



// Observe native forms without replacing their validation, submit or API logic.

export default function SettingsEditorFrame({children,section}:{children:ReactNode;section:string}){

 const root=useRef<HTMLDivElement>(null),active=useRef<HTMLFormElement|null>(null),dirtyForms=useRef(new Set<HTMLFormElement>()),baselines=useRef(new Map<HTMLFormElement,string>()),submitting=useRef<HTMLFormElement|null>(null);

 const [dirty,setDirty]=useState(false),[saving,setSaving]=useState(false),[notice,setNotice]=useState("");

 const signature=(form:HTMLFormElement)=>JSON.stringify(Array.from(form.elements).filter((e):e is HTMLInputElement|HTMLSelectElement|HTMLTextAreaElement=>e instanceof HTMLInputElement||e instanceof HTMLSelectElement||e instanceof HTMLTextAreaElement).filter(e=>e.type!=="submit").map(e=>[e.name||e.id,e.type,e.type==="checkbox"||e.type==="radio"?(e as HTMLInputElement).checked:e.value]));

 useEffect(()=>{

  const remember=(event:Event)=>{const target=event.target;if(!(target instanceof HTMLElement))return;const form=target.closest("form");if(form&&root.current?.contains(form)&&!baselines.current.has(form))baselines.current.set(form,signature(form));};

  const change=(event:Event)=>{const target=event.target;if(!(target instanceof HTMLElement))return;const form=target.closest("form");if(!form||!root.current?.contains(form))return;active.current=form;if(baselines.current.get(form)!==signature(form))dirtyForms.current.add(form);else dirtyForms.current.delete(form);setDirty(dirtyForms.current.size>0);setNotice("");};

  let submitTimer:ReturnType<typeof setTimeout>|undefined;
  const submit=(event:Event)=>{if(event.target instanceof HTMLFormElement&&root.current?.contains(event.target)){submitting.current=event.target;clearTimeout(submitTimer);submitTimer=setTimeout(()=>{submitting.current=null;},0);}};

  const leave=(event:BeforeUnloadEvent)=>{if(dirtyForms.current.size){event.preventDefault();event.returnValue="";}};

  const click=(event:MouseEvent)=>{const target=event.target;if(!(target instanceof Element))return;const anchor=target.closest<HTMLAnchorElement>("a[href]");if(anchor&&dirtyForms.current.size&&anchor.href!==location.href&&!anchor.hash&&!window.confirm("Discard your unsaved settings changes?")){event.preventDefault();event.stopPropagation();}};

  const contextChange=(event:Event)=>{if(dirtyForms.current.size){event.preventDefault();window.alert("Save or cancel your settings changes before switching branch.");}};
  window.addEventListener("suite:before-context-change",contextChange);
  const releaseGuard=registerSettingsDraftGuard(()=>dirtyForms.current.size>0);
  const inputRoot=root.current;

  const scan=()=>{let removed=false;dirtyForms.current.forEach(form=>{if(!form.isConnected){dirtyForms.current.delete(form);baselines.current.delete(form);removed=true;}});if(removed)setDirty(dirtyForms.current.size>0);inputRoot?.querySelectorAll("form").forEach(form=>{if((!baselines.current.has(form)||!dirtyForms.current.has(form))&&Array.from(form.elements).some(e=>e instanceof HTMLInputElement||e instanceof HTMLSelectElement||e instanceof HTMLTextAreaElement))baselines.current.set(form,signature(form));});};

  scan();const observer=new MutationObserver(scan);if(inputRoot)observer.observe(inputRoot,{childList:true,subtree:true,attributes:true,attributeFilter:["value","checked"]});

  inputRoot?.addEventListener("focusin",remember);inputRoot?.addEventListener("beforeinput",remember);inputRoot?.addEventListener("change",change);inputRoot?.addEventListener("input",change);inputRoot?.addEventListener("submit",submit,true);document.addEventListener("click",click,true);window.addEventListener("beforeunload",leave);

  const requests=new WeakMap<object,{form:HTMLFormElement;snapshot:string}>();

  const requestId=api.interceptors.request.use(config=>{if(submitting.current&&root.current?.contains(submitting.current)&&["post","put","patch","delete"].includes(config.method||"")&&!/preview|validate|check|export|test/.test(config.url||"")){requests.set(config,{form:submitting.current,snapshot:signature(submitting.current)});setSaving(true);}return config;});

  const responseId=api.interceptors.response.use(response=>{const saved=requests.get(response.config);if(saved){const {form,snapshot}=saved;baselines.current.set(form,snapshot);if(signature(form)===snapshot)dirtyForms.current.delete(form);else dirtyForms.current.add(form);setDirty(dirtyForms.current.size>0);setSaving(false);submitting.current=null;setNotice(dirtyForms.current.size?"Saved request completed; newer edits are still unsaved.":`Saved at ${new Date().toLocaleTimeString([], {hour:"2-digit",minute:"2-digit"})}. See the section confirmation for when changes apply.`);}return response;},error=>{if(requests.has(error.config)){setSaving(false);submitting.current=null;setNotice("Changes were not saved. Review the form error and try again.");}return Promise.reject(error);});

  return()=>{clearTimeout(submitTimer);observer.disconnect();inputRoot?.removeEventListener("focusin",remember);inputRoot?.removeEventListener("beforeinput",remember);inputRoot?.removeEventListener("change",change);inputRoot?.removeEventListener("input",change);inputRoot?.removeEventListener("submit",submit,true);document.removeEventListener("click",click,true);window.removeEventListener("beforeunload",leave);releaseGuard();window.removeEventListener("suite:before-context-change",contextChange);api.interceptors.request.eject(requestId);api.interceptors.response.eject(responseId);};

 },[section]);

 return <div ref={root} className="settings-editor-frame">{children}{(dirty||notice)&&<div className="settings-save-bar"><span role="status" aria-live="polite">{saving?<Loader2 size={18} className="animate-spin"/>:dirty?<CircleAlert size={18}/>:<CheckCircle2 size={18}/>} {saving?"Saving your changes…":dirty?"You have unsaved changes":notice}</span>{dirty&&<div><button type="button" disabled={saving} onClick={()=>{if(window.confirm("Discard all unsaved changes on this page?")){dirtyForms.current.clear();window.location.reload();}}}>Cancel changes</button><Button variant="outline" type="button" className="settings-primary" disabled={saving} onClick={()=>{const form=active.current&&dirtyForms.current.has(active.current)&&active.current.isConnected?active.current:Array.from(dirtyForms.current).find(item=>item.isConnected);if(form&&form.isConnected){const disabledSubmit=form.querySelector('button[type="submit"]:disabled');if(disabledSubmit){form.reportValidity();return;}form.requestSubmit();}}}>Save changes</Button></div>}</div>}</div>;

}

export function SettingsHistory({section}:{section:string}){

 const user=useAuthStore(state=>state.user);const context=[user?.id,sessionStorage.getItem("suite-organization")||user?.access?.companyId,sessionStorage.getItem("suite-branch")];
 const [open,setOpen]=useState(false);const query=useQuery<{items:{id:number;actor:string;at:string;fields:string[];outcome:string}[]}>({queryKey:["settings-history",...context,section],enabled:open,queryFn:async()=>(await api.get(`/access/settings/history/${section}`)).data,retry:false,staleTime:0});

 return <section className="settings-history"><button type="button" aria-expanded={open} onClick={()=>{setOpen(x=>!x);if(!open)void query.refetch();}}><History size={17}/>View change history</button>{open&&<div><h2>Recent changes</h2><p>Latest 30 relevant changes from the most recent 200 company profile updates. Values are omitted for privacy.</p>{query.isPending?<p role="status">Loading change history…</p>:query.isError?<p role="alert">Could not load history. <Button type="submit" variant="outline" onClick={()=>void query.refetch()}>Retry</Button></p>:query.data?.items.length?<ol>{query.data.items.map(row=><li key={row.id}><strong>{row.actor}</strong><time dateTime={row.at}>{new Date(row.at).toLocaleString()}</time><p>{row.fields.map(x=>x.replace(/_/g," ")).join(", ")} · {row.outcome}</p></li>)}</ol>:<p>No recorded changes yet.</p>}</div>}</section>;

}
