import { usePageRefresh } from "@/lib/page-refresh";
import { useRecordDraft } from "@/hooks/use-record-autosave";
import { announceCreated } from "@/shared/creation/CreationOutcome";
import { contentToHtml, RICH_TEXT_PREFIX } from "@/components/rich-text/content";
import { useMobile } from "@/components/mobile/useMobile";
import { MobileDisclosure } from "@/components/mobile/MobilePrimitives";
import "./docs-mobile.css";
import { CreationEditorSurface } from "@/shared/creation/CreationEditorSurface";
import CompactActions from "@/components/actions/CompactActions";
import { NativeSelect } from "@/components/ui/native-select";
import { downloadRichDocument } from "@/components/rich-text/content";
import RichTextEditor, { RichTextContent, richTextPlainText } from "@/components/rich-text/LazyRichText";
import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "@/services/api";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { projectsAPI, tasksAPI } from "../services/api";
import type { PMSProject, PMSTask } from "../types";
import { workspaceError } from "./workspaceTypes";
type Doc = { id: number; title: string; content: string; task_id: number | null; project_id: number; project_name: string; version: number; updated_at: string; updated_by: string; can_edit: boolean };
type Summary = Pick<Doc, "id" | "title" | "project_id" | "project_name" | "version" | "updated_at">;
type Revision = { version: number; title: string; created_at: string; author: string };
const blank = { title: "", content: "", task_id: "" };
function PhoneDocsRefresh({reload}:{reload:()=>Promise<unknown>}){usePageRefresh(reload);return null;}
export default function DocsPage() {
  const phone=useMobile(480),editorRef=useRef<HTMLElement>(null),mobileOrigin=useRef(phone);
  if(phone)mobileOrigin.current=true;
  const protectedSources=mobileOrigin.current;
  const [creatingDocument,setCreatingDocument] = useState(false);
  const [library, setLibrary] = useState<Summary[]>([]);
  const [projects, setProjects] = useState<PMSProject[]>([]);
  const [project, setProject] = useState("");
  const [tasks, setTasks] = useState<PMSTask[]>([]);
  const [doc, setDoc] = useState<Doc | null>(null);
  const [draft, setDraft] = useState(blank);
  const [search, setSearch] = useState("");
  const [revisions, setRevisions] = useState<Revision[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const createDraft = useRecordDraft("pms:document:new", { draft, project }, saved => { setDraft(saved.draft); setProject(saved.project); }, !doc);
  const [loading, setLoading] = useState(true);
  const lock = useRef(false);
  const dirty = doc ? draft.title !== doc.title || draft.content !== doc.content || draft.task_id !== String(doc.task_id || "") : !!(draft.title || draft.content || draft.task_id);
  type SourcePhase="loading"|"ready"|"error";
  const [sourcePhase,setSourcePhase]=useState<SourcePhase>("loading"),[sourceError,setSourceError]=useState("");
  const phaseRef=useRef<SourcePhase>("loading"),hasSources=useRef(false),sourceJob=useRef<Promise<void>|null>(null),mounted=useRef(true),projectSource=useRef<PMSProject[]>([]),projectsComplete=useRef(false),phoneSeen=useRef(phone);
  function source(phase:SourcePhase,message=""){phaseRef.current=phase;setSourcePhase(phase);setSourceError(message);}
  async function readProjects(fresh:boolean){
    if(!mobileOrigin.current)return projectsAPI.list();
    const items:PMSProject[]=[];
    for(let offset=0;;offset+=100){const batch=await projectsAPI.list(offset,100,undefined,fresh);if(!mounted.current)return [];items.push(...batch);if(batch.length<100){projectsComplete.current=true;return items;}}
  }
  function loadSources(fresh=false):Promise<void>{
    if(sourceJob.current)return sourceJob.current;
    if(mobileOrigin.current&&(lock.current||busy))return Promise.resolve();
    source("loading");setLoading(true);
    const job=Promise.all([api.get<Summary[]>("/project-management/docs",fresh?{recordCache:false,headers:{"Cache-Control":"no-cache"}}:undefined),readProjects(fresh)]).then(([docs,available])=>{
      if(!mounted.current)return;
      setLibrary(docs.data);setProjects(available);projectSource.current=available;hasSources.current=true;source("ready");
    }).catch(failure=>{
      if(mounted.current){
        const status=(failure as {response?:{status?:number}}).response?.status;
        if(mobileOrigin.current&&status&&status>=400&&status<500){hasSources.current=false;setLibrary([]);setProjects([]);projectSource.current=[];projectsComplete.current=false;}
        source("error",workspaceError(failure));if(!mobileOrigin.current)setError(workspaceError(failure));
      }
      throw failure;
    }).finally(()=>{if(sourceJob.current===job)sourceJob.current=null;if(mounted.current)setLoading(false);});
    sourceJob.current=job;return job;
  }
  const sourceReady=!protectedSources||(sourcePhase==="ready"&&projectsComplete.current);
  const canSaveSource=sourceReady&&(!protectedSources||!!doc||projects.some(item=>String(item.id)===project));
  useEffect(()=>{mounted.current=true;void loadSources().catch(()=>{});return()=>{mounted.current=false;};},[]);
  useEffect(()=>{
    if(!phone||phoneSeen.current||busy)return;
    phoneSeen.current=true;let active=true;
    void (async()=>{if(sourceJob.current)await sourceJob.current.catch(()=>{});if(active&&mounted.current&&!projectsComplete.current)await loadSources(true).catch(()=>{});})();
    return()=>{active=false;if(!projectsComplete.current)phoneSeen.current=false;};
  },[phone,busy]);
  const projectRef=useRef(project);projectRef.current=project;
  const taskEpoch=useRef(0),taskJob=useRef<{project:string;epoch:number;promise:Promise<void>}|null>(null),lastTaskProtected=useRef(protectedSources);
  const [taskSource,setTaskSource]=useState<{project:string;phase:SourcePhase;error:string}>({project:"",phase:"ready",error:""});
  function loadLinkedTasks(fresh=false):Promise<void>{
    const id=project,epoch=taskEpoch.current;
    if(!id)return Promise.resolve();
    if(taskJob.current?.project===id&&taskJob.current.epoch===epoch)return taskJob.current.promise;
    const owns=()=>mounted.current&&projectRef.current===id&&taskEpoch.current===epoch;
    setTaskSource({project:id,phase:"loading",error:""});
    const job={project:id,epoch,promise:Promise.resolve() as Promise<void>};
    job.promise=(async()=>{
      if(!mobileOrigin.current)return tasksAPI.list(Number(id));
      const rows:PMSTask[]=[];
      for(let skip=0;;skip+=100){
        const batch=fresh?(await api.get<PMSTask[]>(`/project-management/projects/${id}/tasks`,{params:{skip,limit:100},recordCache:false,headers:{"Cache-Control":"no-cache"}})).data:await tasksAPI.list(Number(id),skip,100);
        if(!owns())return null;
        rows.push(...batch);if(batch.length<100)return rows;
      }
    })().then(rows=>{if(rows&&owns()){setTasks(rows);setTaskSource({project:id,phase:"ready",error:""});}}).catch(failure=>{
      if(!owns())return;
      if(mobileOrigin.current){setTasks([]);setTaskSource({project:id,phase:"error",error:workspaceError(failure)});}else setError(workspaceError(failure));
      throw failure;
    }).finally(()=>{if(taskJob.current===job)taskJob.current=null;});
    taskJob.current=job;return job.promise;
  }
  useEffect(()=>{
    taskEpoch.current++;taskJob.current=null;setTasks([]);
    const fresh=protectedSources&&!lastTaskProtected.current;lastTaskProtected.current=protectedSources;
    if(!project){setTaskSource({project:"",phase:"ready",error:""});return;}
    void loadLinkedTasks(fresh).catch(()=>{});
    return()=>{taskEpoch.current++;taskJob.current=null;};
  },[project,protectedSources]);
  const taskPhase=taskSource.project===project?taskSource.phase:"loading";
  const taskRows=protectedSources&&(taskSource.project!==project||taskPhase!=="ready")?[]:tasks;
  function taskNotice(){
    if(!protectedSources||!project)return null;
    if(taskPhase==="loading")return <p role="status">Loading linked tasks...</p>;
    if(taskPhase==="error")return <div className="pms-docs-source" role="alert"><p>Linked tasks could not be verified. {taskSource.error}</p><p>{draft.task_id?"Keep or clear the current link, or retry to choose another task.":"You can save without a linked task, or retry to choose one."}</p><Button type="button" disabled={busy} onClick={()=>void loadLinkedTasks(true).catch(()=>{})}>Retry linked tasks</Button></div>;
    if(!taskRows.length)return <p role="status">No tasks available to select.</p>;
    return null;
  }
  const historyEpoch=useRef(0),historyDoc=useRef(doc),historySection=useRef<HTMLElement>(null);
  historyDoc.current=doc;
  const historyJob=useRef<{id:number;epoch:number;promise:Promise<void>}|null>(null);
  const [historyState,setHistoryState]=useState<{id:number|null;phase:"idle"|SourcePhase;error:string}>({id:null,phase:"idle",error:""});
  const ownsHistory=(id:number,epoch:number)=>mounted.current&&historyDoc.current?.id===id&&historyEpoch.current===epoch;
  function resetHistory(next:Doc|null){historyEpoch.current++;historyJob.current=null;historyDoc.current=next;setHistoryState({id:next?.id??null,phase:"idle",error:""});}
  function loadHistory():Promise<void>{
    if(!doc)return Promise.resolve();
    const id=doc.id,epoch=historyEpoch.current;
    if(!mobileOrigin.current){setBusy(true);setError("");return api.get<Revision[]>(`/project-management/docs/${id}/revisions`).then(({data})=>setRevisions(data)).catch(failure=>setError(workspaceError(failure))).finally(()=>setBusy(false));}
    if(historyJob.current?.id===id&&historyJob.current.epoch===epoch)return historyJob.current.promise;
    setHistoryState({id,phase:"loading",error:""});
    const job={id,epoch,promise:Promise.resolve() as Promise<void>};
    job.promise=api.get<Revision[]>(`/project-management/docs/${id}/revisions`,{recordCache:false,headers:{"Cache-Control":"no-cache"}}).then(({data})=>{
      if(ownsHistory(id,epoch)){setRevisions(data);setHistoryState({id,phase:"ready",error:""});}
    }).catch(failure=>{
      if(!ownsHistory(id,epoch))return;
      const status=(failure as {response?:{status?:number}}).response?.status;
      if(status&&status>=400&&status<500)setRevisions([]);
      setHistoryState({id,phase:"error",error:workspaceError(failure)});throw failure;
    }).finally(()=>{if(historyJob.current===job)historyJob.current=null;});
    historyJob.current=job;return job.promise;
  }
  function showHistory(){
    if(!doc)return;const id=doc.id,epoch=historyEpoch.current;
    void loadHistory().catch(()=>{});
    if(mobileOrigin.current)requestAnimationFrame(()=>{if(ownsHistory(id,epoch)){historySection.current?.focus({preventScroll:true});historySection.current?.scrollIntoView({block:"start"});}});
  }
  function historyNotice(){
    if(!protectedSources||historyState.id!==doc?.id)return null;
    if(historyState.phase==="loading")return <p role="status">Loading version history...</p>;
    if(historyState.phase==="error")return <div className="pms-docs-source" role="alert"><p>{revisions.length?"Previously loaded revisions are shown. ":"Version history could not be verified. "}{historyState.error}</p><Button type="button" disabled={busy} onClick={()=>void loadHistory().catch(()=>{})}>Retry version history</Button></div>;
    if(historyState.phase==="ready"&&!revisions.length)return <p role="status">No revisions available.</p>;
    return null;
  }
  useEffect(() => { const warn = (event: BeforeUnloadEvent) => { if (dirty) { event.preventDefault(); event.returnValue = ""; } }; window.addEventListener("beforeunload", warn); return () => window.removeEventListener("beforeunload", warn); }, [dirty]);
  const apply = (data: Doc) => { resetHistory(data); setDoc(data); setProject(String(data.project_id)); setDraft({ title: data.title, content: data.content, task_id: String(data.task_id || "") }); setRevisions([]); };
  async function open(id: number) {
    if (busy || (dirty && !window.confirm("Discard your unsaved changes and open this document?"))) return;
    setBusy(true); setError(""); setNotice("");
    try { const { data } = await api.get<Doc>(`/project-management/docs/${id}`); apply(data); if(phone)requestAnimationFrame(()=>editorRef.current?.focus({preventScroll:true})); }
    catch (error) { setError(workspaceError(error)); } finally { setBusy(false); }
  }
  async function save() {
    if (lock.current || !project || !draft.title.trim() || (doc && !doc.can_edit) || (mobileOrigin.current&&(phaseRef.current!=="ready"||!projectsComplete.current||(!doc&&!projectSource.current.some(item=>String(item.id)===project))))) return;
    lock.current = true; setBusy(true); setError(""); setNotice("");
    const payload = { title: draft.title, content: draft.content, task_id: draft.task_id ? Number(draft.task_id) : null };
    try {
      const { data } = doc ? await api.put<Doc>(`/project-management/docs/${doc.id}`, { ...payload, version: doc.version }) : await api.post<Doc>(`/project-management/projects/${project}/docs`, payload);
      if (!doc) { createDraft(); announceCreated({ title: `Document ${data.title} created`, href: "/pms/docs" }); }
      apply(data); setLibrary(current => [data, ...current.filter(item => item.id !== data.id)]); setNotice(`Saved version ${data.version}`);
    } catch (error) { setError(workspaceError(error)); } finally { lock.current = false; setBusy(false); }
  }
  function download() { downloadRichDocument(draft.content, draft.title); }
  function sourceNotice(){
    if(!protectedSources)return null;
    if(sourcePhase==="loading"||(sourcePhase==="ready"&&!projectsComplete.current))return <p role="status">Loading documents and projects...</p>;
    if(sourcePhase==="ready"&&!projects.length)return <p role="status">No accessible projects available.</p>;
    if(sourcePhase!=="error")return null;
    return <div className="pms-docs-source" role="alert"><p>{hasSources.current?"Previously loaded records are shown. ":"Documents and projects could not be verified. "}{sourceError}</p><Button disabled={busy} onClick={()=>void loadSources(true).catch(()=>{})}>Retry documents and projects</Button></div>;
  }
  const editable = !doc || doc.can_edit;
  return <main className="pms-docs space-y-4" onKeyDown={event => { if ((event.ctrlKey || event.metaKey) && event.key === "s") { event.preventDefault(); void save(); } }}>
    <header className="flex flex-wrap items-center justify-between gap-3"><div><h1 className="page-title">Docs</h1><p className="page-description">Project documents with visual editing, task links and version history.</p></div><Link className="text-sm text-primary underline" to="/pms/workspaces">Workspace</Link></header>
    {protectedSources&&<PhoneDocsRefresh reload={()=>Promise.all([loadSources(true),loadLinkedTasks(true),...(doc&&historyState.phase!=="idle"?[loadHistory()]:[])])}/>}
    {(!creatingDocument||!!doc)&&sourceNotice()}

    {error && <p role="alert" className="rounded border border-destructive p-3 text-destructive">{error}</p>}{notice && <p role="status">{notice}</p>}
    <div className="grid gap-4 lg:grid-cols-[240px_minmax(0,1fr)]"><MobileDisclosure key={phone?String(doc?.id||"new"):"desktop"} maxWidth={480} initiallyOpen={!doc} title={`Document library · ${protectedSources&&(sourcePhase!=="ready"||!projectsComplete.current)?(sourcePhase==="loading"?"Loading":"Unverified"):library.length}`}><aside className="pms-docs-library space-y-3 rounded-lg border p-4"><Button disabled={busy||!sourceReady} onClick={() => { if (!dirty || window.confirm("Discard unsaved changes and create a document?")) { resetHistory(null); setDoc(null); setDraft(blank); setRevisions([]); setError(""); setNotice(""); setCreatingDocument(true); } }}>New document</Button><Input aria-label="Search documents" placeholder="Search title or project…" value={search} onChange={event => setSearch(event.target.value)} />{loading && !protectedSources && <p role="status">Loading documents…</p>}{protectedSources&&sourceReady&&!library.length&&<p role="status">No accessible documents yet.</p>}{protectedSources&&sourceReady&&!!library.length&&!library.some(item=>`${item.title} ${item.project_name}`.toLowerCase().includes(search.toLowerCase()))&&<p role="status">No documents match this search.</p>}{library.filter(item => `${item.title} ${item.project_name}`.toLowerCase().includes(search.toLowerCase())).map(item => <button key={item.id} disabled={busy||!sourceReady} className={`w-full break-words rounded-md border p-3 text-left text-sm ${doc?.id === item.id ? "bg-muted" : ""}`} onClick={() => void open(item.id)}><strong>{item.title}</strong><span className="mt-1 block text-xs text-muted-foreground">{item.project_name} · v{item.version}</span></button>)}</aside></MobileDisclosure>
      <CreationEditorSurface creating={creatingDocument && !doc} title="Create document" onClose={() => {setCreatingDocument(false);}} onCloseAutoFocus={phone?event=>{event.preventDefault();editorRef.current?.focus({preventScroll:true});}:undefined}><section ref={editorRef} tabIndex={phone?-1:undefined} className="pms-docs-editor min-w-0 space-y-4 rounded-xl border bg-card p-5" aria-label="Document editor" data-doc-creating={creatingDocument&&!doc||undefined}>{creatingDocument&&!doc&&sourceNotice()}
        <CompactActions className="flex flex-wrap items-center gap-2"><Button data-doc-save disabled={busy || !editable || !project || !draft.title.trim() || !canSaveSource} onClick={() => void save()}>{busy ? "Working…" : "Save document"}</Button><Button variant="outline" onClick={download}>Download formatted document</Button>{doc && <Button variant="ghost" disabled={busy||(protectedSources&&historyState.phase==="loading")} onClick={showHistory}>Version history</Button>}{doc && <Button variant="ghost" disabled={busy} onClick={() => void open(doc.id)}>Load latest</Button>}</CompactActions>
        <div className="grid gap-3 sm:grid-cols-2"><label className="text-sm">Project<NativeSelect aria-label="Document project" required disabled={busy || !!doc || !sourceReady} value={project} onChange={event => { setProject(event.target.value); setDraft(current => ({ ...current, task_id: "" })); }} className="mt-1 h-10 w-full rounded-md border bg-background px-3"><option value="" disabled>Choose project</option>{protectedSources&&project&&!projects.some(item=>String(item.id)===project)&&<option value={project}>{doc?.project_name||`Project #${project}`} ({sourcePhase==="ready"?"unavailable":"unverified"})</option>}{projects.map(project => <option key={project.id} value={project.id}>{project.name}</option>)}</NativeSelect></label><label className="text-sm">Linked task<NativeSelect aria-label="Document linked task" disabled={busy || !editable || (protectedSources&&(!project||!sourceReady||taskPhase==="loading"))} value={draft.task_id} onChange={event => setDraft({ ...draft, task_id: event.target.value })} className="mt-1 h-10 w-full rounded-md border bg-background px-3"><option value="">No linked task</option>{draft.task_id && !taskRows.some(task => String(task.id) === draft.task_id) && <option value={draft.task_id}>Linked task #{draft.task_id} ({protectedSources&&taskPhase!=="ready"?"unverified":"unavailable"})</option>}{taskRows.map(task => <option key={task.id} value={task.id}>{task.task_key} · {task.title}</option>)}</NativeSelect></label></div>
        {taskNotice()}
        <Input aria-label="Document title" placeholder="Document title" maxLength={180} disabled={busy || !editable} value={draft.title} className="h-12 text-xl font-semibold" onChange={event => setDraft({ ...draft, title: event.target.value })} />
          {!doc && <><label className="text-sm">Document template<NativeSelect aria-label="Document template" disabled={busy} defaultValue="" onChange={event => { const template = event.target.value; if (!template) return; if (richTextPlainText(draft.content).trim()) { setError("Clear the content before applying a template."); event.target.value = ""; return; } const content = ({ meeting: "# Meeting notes\n\n## Attendees\n\n## Discussion\n\n## Decisions\n\n## Action items\n", brief: "# Project brief\n\n## Objective\n\n## Scope\n\n## Deliverables\n\n## Acceptance criteria\n", decision: "# Decision record\n\n## Context\n\n## Options considered\n\n## Decision\n\n## Consequences\n" } as Record<string,string>)[template]; setDraft(current => ({ ...current, content: RICH_TEXT_PREFIX + contentToHtml(content) })); }}><option value="">Blank document</option><option value="meeting">Meeting notes</option><option value="brief">Project brief</option><option value="decision">Decision record</option></NativeSelect></label><p role="status" className="text-xs text-muted-foreground">{createDraft.status === "restored" ? "Restored your unfinished document." : createDraft.status === "unavailable" ? "Draft storage unavailable; keep the editor open." : "Document draft saved in this browser session."}</p></>}
        <p className="text-xs text-muted-foreground">{doc ? `Version ${doc.version} · Updated by ${doc.updated_by}` : "New document"} · {dirty ? "Unsaved changes" : "No unsaved changes"} · {richTextPlainText(draft.content) ? richTextPlainText(draft.content).split(/\s+/).length : 0} words{!editable && " · View only"}</p>
        <RichTextEditor value={draft.content} onChange={content => setDraft({ ...draft, content })} label="Document content" variant="document" maxLength={200000} readOnly={!editable} disabled={busy}/>

        {(!!revisions.length||(protectedSources&&historyState.id===doc?.id&&historyState.phase!=="idle")) && <section ref={historySection} tabIndex={protectedSources?-1:undefined} aria-label={protectedSources?"Document version history":undefined} className="pms-docs-history space-y-2 border-t pt-4"><h2 className="font-semibold">Version history</h2><p className="text-xs text-muted-foreground">Loading an older version puts it in your draft. Save to create a new revision; history is retained.</p>{historyNotice()}{revisions.map(revision => <div key={revision.version} className="flex flex-wrap items-center justify-between gap-2 rounded border p-3 text-sm"><span>v{revision.version} · {revision.author} · {revision.title}</span><Button size="sm" variant="outline" disabled={busy} onClick={() => {
          if (dirty && !window.confirm("Replace your unsaved draft with this revision?")) return;
          setBusy(true); setError(""); void api.get(`/project-management/docs/${doc!.id}/revisions/${revision.version}`).then(({ data }) => { setDraft({ title: data.title, content: data.content, task_id: String(data.task_id || "") }); setNotice(`Revision ${revision.version} loaded as a draft`); }).catch(error => setError(workspaceError(error))).finally(() => setBusy(false));
        }}>Load revision {revision.version}</Button></div>)}</section>}
      </section>{error && <p role="alert">{error}</p>}</CreationEditorSurface>
    </div>
  </main>;
}
