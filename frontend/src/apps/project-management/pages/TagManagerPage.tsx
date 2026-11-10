import { useMobileContext } from "@/components/mobile/useMobileContext";
import { syncScope } from "@/shared/record-sync/store";
import { useMobile } from "@/components/mobile/useMobile";
import { MobileDisclosure } from "@/components/mobile/MobilePrimitives";
import "./tag-manager-mobile.css";
import {SmartCreateSection} from "@/shared/creation/SmartCreateSection";
import { useInitialLoading } from "@/hooks/use-initial-loading";
import GridTable from "@/shared/data-grid/GridTable";
import { NativeSelect } from "@/components/ui/native-select";
import CompactForm from "@/components/forms/CompactForm";
import { recordPreviewProps } from "@/components/RecordQuickPreview";
import { useRefreshableEffect } from "@/lib/page-refresh";
import { useEffect, useRef, useState } from "react";
import * as AlertDialog from "@radix-ui/react-alert-dialog";
import { Link } from "react-router-dom";
import { api } from "@/services/api";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { workspaceError } from "./workspaceTypes";
type Tag = { id: number; name: string; color: string | null; usage: number; created_at: string; projects: { id: number; name: string }[] };
export default function TagManagerPage(){
  const phone=useMobile(480),scope=useMobileContext();
  if(phone&&scope!==syncScope())return <p role="status">Updating tag context…</p>;
  return <TagManagerContent key={scope}/>;
}
function TagManagerContent() {
  const phone=useMobile(480),phoneNow=useRef(false);phoneNow.current=phone;
  const ownerScope=useRef(syncScope());
  const currentOwner=()=>!phone||mounted.current&&ownerScope.current===syncScope();
  const owns=()=>mounted.current&&ownerScope.current===syncScope();
  const readRevision=useRef(0),minimumRead=useRef(0);
  const writeInFlight=useRef(false),confirmed=useRef<'save'|'delete'|null>(null);
  const [recovery,setRecovery]=useState<'save'|'delete'|null>(null);
  const previousPhone=useRef(phone);
  useEffect(()=>{const entering=phone&&!previousPhone.current;previousPhone.current=phone;if(entering)void refreshSource().catch(()=>undefined);},[phone]);
  const mounted=useRef(true),sourceInFlight=useRef(false),sourceRequest=useRef<Promise<void>|null>(null);
  useEffect(()=>{mounted.current=true;return()=>{mounted.current=false;};},[]);
  const [sourceBusy,setSourceBusy]=useState(true),[sourceError,setSourceError]=useState(''),[loadedOnce,setLoadedOnce]=useState(false),[permissionBlocked,setPermissionBlocked]=useState(false);
  const sourceReady=!phone||currentOwner()&&loadedOnce&&!sourceBusy&&!sourceError&&!permissionBlocked&&!recovery;
  const hideContent=phone&&(!loadedOnce||permissionBlocked);
  function refreshSource(){
    if(!owns())return Promise.reject(new Error('Tag context changed.'));
    if(sourceRequest.current)return sourceRequest.current;
    sourceInFlight.current=true;setSourceBusy(true);const revision=++readRevision.current;
    const request=Promise.resolve().then(async()=>{try{if(!owns())throw new Error('Tag context changed.');const {data}=await api.get<{tags:Tag[];can_manage:boolean}>("/project-management/tag-manager");if(owns()){setTags(data.tags);setManage(data.can_manage);if(!data.can_manage)setConfirm(false);setLoadedOnce(true);setPermissionBlocked(false);setSourceError('');if(revision>minimumRead.current)completeConfirmed();}}
    catch(error:any){if(owns()){setSourceError(workspaceError(error));if(error.response?.status===403||error.response?.status===401){setPermissionBlocked(true);setConfirm(false);}}throw error;}
    finally{sourceInFlight.current=false;sourceRequest.current=null;if(owns()){setSourceBusy(false);setLoading(false);}}});
    sourceRequest.current=request;return request;
  }
  const [savedRevision,setSavedRevision]=useState(0);
  const [tags, setTags] = useState<Tag[]>([]);
  const [manage, setManage] = useState(false);
  const [loading, setLoading] = useState(true);
  const initialLoading = useInitialLoading(loading);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [search, setSearch] = useState("");
  const [project, setProject] = useState("");
  const [sort, setSort] = useState("name");
  const [unused, setUnused] = useState(false);
  const [selected, setSelected] = useState<number[]>([]);
  const [confirm, setConfirm] = useState(false);
  const [editing, setEditing] = useState<number | null>(null);
  const [name, setName] = useState("");
  const [color, setColor] = useState("#7c3aed");
  function completeConfirmed(){
    const kind=confirmed.current;if(!kind||!currentOwner())return;
    confirmed.current=null;setRecovery(null);setConfirm(false);setName('');setEditing(null);setError('');
    if(kind==='delete')setSelected([]);
    setNotice(kind==='save'?'Tag saved':'Selected tags deleted');setSavedRevision(value=>value+1);
  }
  async function mutatePhone(kind:'save'|'delete'){
    if(!currentOwner()||writeInFlight.current||confirmed.current||!sourceReady||!manage)return;
    writeInFlight.current=true;setBusy(true);setError('');setNotice('');
    try{
      if(kind==='delete')await api.post('/project-management/tag-manager/delete',{tag_ids:selected});
      else if(editing)await api.put(`/project-management/tag-manager/${editing}`,{name,color});
      else await api.post('/project-management/tags',{name,color});
      if(!owns())return;
      minimumRead.current=readRevision.current;confirmed.current=kind;setRecovery(kind);setSavedRevision(value=>value+1);if(kind==='delete')setConfirm(false);
      if(sourceRequest.current)await sourceRequest.current.catch(()=>undefined);
      if(!owns())return;await refreshSource();if(owns())completeConfirmed();
    }catch(error){if(owns()&&!confirmed.current)setError(workspaceError(error));}
    finally{writeInFlight.current=false;if(owns())setBusy(false);}
  }
  const recoveryPanel=recovery&&<div className="pms-tag-source"><p role="status">{recovery==='save'?'Tag saved. Reload tags to update this view; do not submit again.':'Tags deleted. Reload tags to update this view; do not submit again.'}</p><Button type="button" variant="outline" disabled={busy||sourceBusy} onClick={()=>{if(!sourceInFlight.current&&!writeInFlight.current)void refreshSource().catch(()=>undefined);}}>Reload saved tags</Button></div>;
  async function load() { if(phone){await refreshSource();return;}const { data } = await api.get<{ tags: Tag[]; can_manage: boolean }>("/project-management/tag-manager"); setTags(data.tags); setManage(data.can_manage); }
  useRefreshableEffect(() => { if(phone){void refreshSource().catch(()=>undefined);return;}let active = true; api.get<{ tags: Tag[]; can_manage: boolean }>("/project-management/tag-manager").then(({ data }) => { if (active&&!phoneNow.current) { setTags(data.tags); setManage(data.can_manage); } }).catch(error => { if (active&&!phoneNow.current) setError(workspaceError(error)); }).finally(() => { if (active&&!phoneNow.current) setLoading(false); }); return () => { active = false; }; }, []);
  const projects = phone&&permissionBlocked?[]:[...new Map(tags.flatMap(tag => tag.projects).map(project => [project.id, project])).values()];
  const visible = tags.filter(tag => tag.name.toLowerCase().includes(search.trim().toLowerCase()) && (!project || tag.projects.some(item => item.id === Number(project))) && (!unused || tag.usage === 0)).sort((a, b) => sort === "usage" ? b.usage - a.usage || a.name.localeCompare(b.name) : sort === "newest" ? b.id - a.id : a.name.localeCompare(b.name));
  const styleColor = (value: string | null) => value && /^#[0-9a-fA-F]{6}$/.test(value) ? value : "#7c3aed";
  return <main className="pms-tag-manager mx-auto max-w-6xl space-y-5">
    <header className="flex flex-wrap justify-between gap-3"><div><h1 className="page-title">Tag Manager</h1><p className="page-description">Manage organization tags in one place. Usage counts and locations show only active tasks in projects you can access.</p></div><Link className="text-sm text-primary underline" to="/pms/settings">Settings</Link></header>
    {phone&&(recovery==='delete'||hideContent)&&recoveryPanel}
    {phone&&sourceError&&<div role="alert" className="pms-tag-source"><p>Could not load tags. {sourceError}</p>{loadedOnce&&!permissionBlocked&&<p>Showing last loaded tags. Changes are unavailable until refresh succeeds.</p>}<Button variant="outline" disabled={sourceBusy||busy} onClick={()=>{if(!sourceInFlight.current&&!busy)void refreshSource().catch(()=>undefined);}}>Retry tags</Button></div>}
    {phone&&sourceBusy&&loadedOnce&&<p role="status">Refreshing tags…</p>}
    {error && <p role="alert" className="text-destructive">{error}</p>}{notice && <p role="status">{notice}</p>}
    <div className="pms-tag-filters flex flex-wrap items-center gap-3"><Input aria-label="Search tags" className="max-w-sm" placeholder="Search tags…" value={search} onChange={event => setSearch(event.target.value)} /><MobileDisclosure maxWidth={480} title={`Location & filters${project || unused ? ` · ${Number(!!project)+Number(unused)} active` : ""}`}><div className="pms-tag-filter-options" style={{display:phone?"grid":"contents"}}><NativeSelect loading={phone&&sourceBusy} error={phone&&!!sourceError} disabled={phone&&(!loadedOnce||sourceBusy||permissionBlocked)} aria-label="Filter tag location" className="h-10 rounded-md border bg-background px-3" value={project} onChange={event => setProject(event.target.value)}><option value="">All accessible locations</option>{phone&&permissionBlocked&&project&&<option value={project} disabled>Location {project} (not verified)</option>}{projects.map(project => <option key={project.id} value={project.id}>{project.name}</option>)}</NativeSelect><NativeSelect aria-label="Sort tags" className="h-10 rounded-md border bg-background px-3" value={sort} onChange={event => setSort(event.target.value)}><option value="name">Name A–Z</option><option value="usage">Most used</option><option value="newest">Newest first</option></NativeSelect><label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={unused} onChange={event => setUnused(event.target.checked)} />No accessible usage</label></div></MobileDisclosure></div>
    {hideContent ? (sourceBusy?<p role="status">Loading tags…</p>:null) : initialLoading ? <p role="status">Loading tags…</p> : <><div className="flex flex-wrap justify-between gap-3 text-sm"><span>{visible.length} tags shown · {selected.length} selected across filters</span>{manage && selected.length > 0 && <Button variant="destructive" disabled={busy||!sourceReady} onClick={() => setConfirm(true)}>Delete {selected.length} selected</Button>}</div>
      <div className="overflow-x-auto rounded-lg border"><GridTable gridId="apps/project-management/pages/TagManagerPage:table-1" className="w-full text-left text-sm"><thead className="border-b bg-muted/30"><tr>{manage && <th className="p-3"><input aria-label="Select all shown tags" type="checkbox" disabled={busy || !sourceReady || !visible.length} checked={visible.length > 0 && visible.every(tag => selected.includes(tag.id))} onChange={event => setSelected(current => event.target.checked ? [...new Set([...current, ...visible.map(tag => tag.id)])] : current.filter(id => !visible.some(tag => tag.id === id)))} /></th>}<th className="p-3">Tag name</th><th className="p-3">Color</th><th className="p-3">Accessible usage</th><th className="p-3">Locations</th><th className="p-3">Created</th>{manage && <th className="p-3">Actions</th>}</tr></thead><tbody>{visible.map(tag => <tr {...recordPreviewProps(tag)} key={tag.id} className="border-b">{manage && <td className="p-3"><input aria-label={`Select ${tag.name}`} type="checkbox" disabled={busy||!sourceReady} checked={selected.includes(tag.id)} onChange={event => setSelected(current => event.target.checked ? [...current, tag.id] : current.filter(id => id !== tag.id))} /></td>}<td className="p-3"><span className="inline-flex items-center gap-2 rounded-md border px-2 py-1"><span aria-hidden="true" className="h-2 w-2 rounded-full" style={{ backgroundColor: styleColor(tag.color) }} />{tag.name}</span></td><td className="p-3"><span className="inline-block h-4 w-4 rounded-full border" aria-label={`Color ${tag.color || "default"}`} style={{ backgroundColor: styleColor(tag.color) }} /></td><td className="p-3">{tag.usage} tasks</td><td className="p-3">{tag.projects.map(project => <Link key={project.id} to={`/pms/projects/${project.id}`} className="mr-2 text-primary underline">{project.name}</Link>)}</td><td className="whitespace-nowrap p-3">{tag.created_at ? new Date(tag.created_at).toLocaleDateString() : "—"}</td>{manage && <td className="p-3"><Button size="sm" variant="ghost" disabled={busy||!sourceReady} aria-label={`Edit ${tag.name}`} onClick={() => { setEditing(tag.id); setName(tag.name); setColor(styleColor(tag.color)); }}>Edit</Button></td>}</tr>)}</tbody></GridTable>{!visible.length && <p className="p-6 text-center text-sm text-muted-foreground">No tags match this view.</p>}</div>
      {manage && <SmartCreateSection title="Create tag" mobileSheet={phone||undefined} closeOnRecordSaved={!phone} savedRevision={phone?savedRevision:0} inline={!!editing}><CompactForm className="pms-tag-editor space-y-3 rounded-lg border p-4" onSubmit={event => {
        event.preventDefault();if(phone){void mutatePhone('save');return;} if (busy||!sourceReady) return; setBusy(true); setError(""); setNotice("");
        void (editing ? api.put(`/project-management/tag-manager/${editing}`, { name, color }) : api.post("/project-management/tags", { name, color })).then(async () => { setName(""); setEditing(null); setNotice("Tag saved"); await load(); if(phone)setSavedRevision(value=>value+1); }).catch(error => setError(workspaceError(error))).finally(() => setBusy(false));
      }}>{phone&&recovery==='save'&&recoveryPanel}{error && <p role="alert" className="text-sm text-destructive">{error}</p>}<h2 className="font-semibold">{editing ? "Edit tag" : "Create tag"}</h2><fieldset disabled={busy||!sourceReady} className="flex flex-wrap items-end gap-3"><label className="min-w-0 flex-1 text-sm">Name<Input required maxLength={100} value={name} onChange={event => setName(event.target.value)} /></label><label className="text-sm">Color<input aria-label="Tag color" type="color" value={color} onChange={event => setColor(event.target.value)} className="mt-1 block h-10 w-14" /></label><Button disabled={busy||!sourceReady}>{busy ? "Saving…" : "Save tag"}</Button>{editing && <Button type="button" variant="outline" onClick={() => { setEditing(null); setName(""); }}>Cancel edit</Button>}</fieldset><p className="text-xs text-muted-foreground">Renaming or recoloring a tag updates it wherever it is used in this organization.</p></CompactForm></SmartCreateSection>}
    </>}
    <AlertDialog.Root open={confirm} onOpenChange={open => { if (!busy) setConfirm(open); }}><AlertDialog.Portal><AlertDialog.Overlay className="fixed inset-0 z-50 bg-black/40" /><AlertDialog.Content className="pms-tag-delete fixed left-1/2 top-1/2 z-50 w-[calc(100%_-_2rem)] max-w-lg -translate-x-1/2 -translate-y-1/2 space-y-4 rounded-lg border bg-background p-6"><AlertDialog.Title className="font-semibold">Delete {selected.length} tags?</AlertDialog.Title><AlertDialog.Description className="text-sm text-muted-foreground">This permanently deletes the selected organization tags and removes their labels from all tasks, including tasks outside the current view. Tasks themselves are kept.</AlertDialog.Description><p className="max-h-36 overflow-y-auto text-sm">{tags.filter(tag => selected.includes(tag.id)).map(tag => tag.name).join(", ")}</p><div className="flex justify-end gap-2"><AlertDialog.Cancel asChild><Button variant="outline" disabled={busy||!sourceReady}>Cancel</Button></AlertDialog.Cancel><Button variant="destructive" disabled={busy||!sourceReady} onClick={() => {
      if(phone){void mutatePhone('delete');return;}setBusy(true); setError(""); void api.post("/project-management/tag-manager/delete", { tag_ids: selected }).then(async () => { setConfirm(false); setSelected([]); setEditing(null); setName(""); setNotice("Selected tags deleted"); await load(); }).catch(error => { setConfirm(false); setError(workspaceError(error)); }).finally(() => setBusy(false));
    }}>{busy ? "Deleting…" : "Delete permanently"}</Button></div></AlertDialog.Content></AlertDialog.Portal></AlertDialog.Root>
  </main>;
}
