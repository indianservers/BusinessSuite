import {useMobileContext} from "@/components/mobile/useMobileContext";
import {useMobileDraftGuard} from "@/components/mobile/useMobileDraftGuard";
import {syncScope} from "@/shared/record-sync/store";
import {workspaceError} from "./workspaceTypes";
import {useMobile} from "@/components/mobile/useMobile";
import "./files-mobile.css";
import { SmartCreateSection } from "@/shared/creation/SmartCreateSection";
import { useModuleAction } from "@/hooks/use-module-action";
import GroupedRecords from "@/shared/data-grid/GroupedRecords";
import { useParams } from "react-router-dom";
import { SuiteFileIcon } from "@/components/visuals/SuiteVisuals";
import { NativeSelect } from "@/components/ui/native-select";
import { usePageRefresh } from "@/lib/page-refresh";
import { type ReactNode, useEffect, useRef, useState } from "react";
import { Upload, FolderPlus, Download, Search, LayoutGrid, Folder, Files, HardDrive, Trash2 } from "lucide-react";
import { api } from "@/services/api";
import MoveBoard from "@/components/interaction/MoveBoard";
import { Button } from "@/components/ui/button";
import { filesAPI, projectsAPI, listAllProjects } from "../services/api";
import type { PMSFileAsset, PMSProject } from "../types";

type Folder = { id: number; name: string };
type SavedChange={projectId:string;kind:"folder"|"move"|"delete"|"upload";message:string};
export default function FilesPage() {
  const phone=useMobile(480),mobileOrigin=useRef(phone);
  if(phone)mobileOrigin.current=true;
  const scope=useMobileContext(mobileOrigin.current),{projectId}=useParams<{projectId:string}>();
  const route=useRef(projectId),epoch=useRef(0);
  if(mobileOrigin.current&&route.current!==projectId)epoch.current++;
  route.current=projectId;
  if(mobileOrigin.current&&scope!==syncScope())return <p role="status">Updating file context…</p>;
  return <FilesContent key={scope+":"+epoch.current} protectedContext={mobileOrigin.current}/>;
}

function FilesContent({protectedContext}:{protectedContext:boolean}) {
  const phone=useMobile(480),mutationLock=useRef(false);
  const ownerScope=useRef(syncScope()),projectEpoch=useRef(0),folderBaseline=useRef("");
  const [savedRevision,setSavedRevision]=useState(0),[completedRevision,setCompletedRevision]=useState(0);
  const confirmed=useRef<SavedChange|null>(null),verification=useRef<Promise<void>|null>(null);
  const [recovery,setRecovery]=useState<SavedChange|null>(null),[checking,setChecking]=useState(false),[recoveryError,setRecoveryError]=useState("");
  const { projectId: routeProjectId } = useParams<{ projectId: string }>();
  const [projects, setProjects] = useState<PMSProject[]>([]);
  const [projectId, setProjectId] = useState("");
  const [files, setFiles] = useState<PMSFileAsset[]>([]);
  const [folders, setFolders] = useState<Folder[]>([]);
  const [folder, setFolder] = useState("");
  const [target, setTarget] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const [over, setOver] = useState(false);
  const [fileQuery, setFileQuery] = useState("");
  const [folderFilter, setFolderFilter] = useState("all");
  const [fileView, setFileView] = useState<"library" | "folders">("library");
  const fileInput = useRef<HTMLInputElement>(null);
  const projectRef = useRef(projectId);
  projectRef.current = projectId;
  type Phase="loading"|"ready"|"error";
  const [sources,setSources]=useState<Record<"projects"|"files",Phase>>({projects:"loading",files:"loading"});
  const [sourceErrors,setSourceErrors]=useState({projects:"",files:""});
  const phases=useRef(sources),hasProjects=useRef(false),hasFiles=useRef(false),fileOwner=useRef("");
  const mounted=useRef(true),readVersion=useRef(0),routeRef=useRef(routeProjectId);
  routeRef.current=routeProjectId;
  const ownsContext=()=>!protectedContext||(mounted.current&&ownerScope.current===syncScope());
  const ownsProject=(id:string,epoch:number)=>ownsContext()&&mounted.current&&projectRef.current===id&&projectEpoch.current===epoch&&(!routeRef.current||routeRef.current===id);
  const requestLeave=useMobileDraftGuard({enabled:protectedContext,dirty:folder!==folderBaseline.current,draftKey:ownerScope.current+":"+projectId+":"+folder,pending:()=>mutationLock.current||!!verification.current,onDiscard:()=>{folderBaseline.current=folder;},message:"Discard this folder draft and leave?"});
  function changeProject(next:string){
    if(protectedContext){
      if(next===projectId||!ownsContext()||!requestLeave())return;
      projectEpoch.current++;projectRef.current=next;folderBaseline.current="";setFolder("");setError("");setNotice("");setFileQuery("");setFolderFilter("all");
    }
    setProjectId(next);
  }
  function closeFolderDraft(){
    if(!protectedContext||!ownsContext()||mutationLock.current||confirmed.current)return;
    folderBaseline.current="";
    setFolder("");
  }
  const initialized=useRef(false);
  const fileRead=useRef<{id:string;promise:Promise<boolean>}|null>(null),retryProjects=useRef<()=>Promise<void>>(async()=>{});
  useEffect(()=>{mounted.current=true;return()=>{mounted.current=false;readVersion.current++;};},[]);
  function source(kind:"projects"|"files",phase:Phase,message=""){
    phases.current={...phases.current,[kind]:phase};
    setSources(phases.current);setSourceErrors(values=>({...values,[kind]:message}));
  }
  const isSourceReady=()=>ownsContext()&&!confirmed.current&&(!phone||(phases.current.projects==="ready"&&phases.current.files==="ready"&&fileOwner.current===projectId&&!!projectId&&(!routeProjectId||projectId===routeProjectId)));
  const sourceReady=isSourceReady();
  const recordsVisible=ownsContext()&&(!phone||(hasProjects.current&&hasFiles.current&&fileOwner.current===projectId&&(!routeProjectId||routeProjectId===projectId)));
  useEffect(() => {
    let active = true;
    if((!protectedContext||!initialized.current)&&!confirmed.current){initialized.current=true;setProjectId(routeProjectId || ""); setFolder(""); setFileQuery(""); setFolderFilter("all");}
    let reading=false;
    async function readProjects(){
      if(!active||!ownsContext()||reading)return;
      reading=true;if(phone||confirmed.current||protectedContext)source("projects","loading");
      try{
        const items=await listAllProjects();
        const selected=routeProjectId&&!items.some(project=>String(project.id)===routeProjectId)?await projectsAPI.get(Number(routeProjectId)):null;
        if(!active||!mounted.current||!ownsContext())return;
        setProjects(selected?[selected,...items]:items);
        setProjectId(current=>routeProjectId||(items.some(project=>String(project.id)===current)?current:String(items[0]?.id||"")));
        if(phone||confirmed.current||protectedContext){hasProjects.current=true;source("projects","ready");}
      }catch(error:any){
        if(!active||!mounted.current||!ownsContext())return;
        if(!phone&&!confirmed.current&&!protectedContext)setError("Unable to load projects.");
        else{
          if(error?.response?.status>=400&&error?.response?.status<500){hasProjects.current=false;hasFiles.current=false;readVersion.current++;fileRead.current=null;setProjects([]);setFiles([]);setFolders([]);source("files","loading");}
          source("projects","error",workspaceError(error));
        }
      }finally{reading=false;}
    }
    let projectJob:Promise<void>|null=null;
    function loadProjects(){
      if(projectJob)return projectJob;
      projectJob=readProjects().finally(()=>{projectJob=null;});return projectJob;
    }
    retryProjects.current=loadProjects;void loadProjects();
    return () => { active = false; };
  }, [routeProjectId,phone,protectedContext]);

  async function load(id = projectId, fresh = false) {
    const protectedRead=phone||fresh||!!confirmed.current||protectedContext;
    const epoch=projectEpoch.current;
    if (!id || (protectedRead&&phases.current.projects!=="ready")) return false;
    if(protectedRead&&fresh){readVersion.current++;fileRead.current=null;}
    if(protectedRead&&fileRead.current?.id===id)return fileRead.current.promise;
    const version=++readVersion.current;
    const owns=()=>ownsProject(id,epoch)&&version===readVersion.current;
    async function read(){
      if(protectedRead)source("files","loading");
      try{
        const [assets,directories]=await Promise.all([
          fresh?api.get<PMSFileAsset[]>("/project-management/files",{params:{project_id:Number(id)},recordCache:false,headers:{"Cache-Control":"no-cache"}}).then(response=>response.data):filesAPI.list({project_id:Number(id)}),
          api.get<Folder[]>("/project-management/file-folders",{params:{project_id:Number(id)},...(fresh?{recordCache:false,headers:{"Cache-Control":"no-cache"}}:{})})
        ]);
        if(protectedRead?!owns():id!==projectRef.current)return false;
        setFiles(assets);setFolders(directories.data);
        if(protectedRead){hasFiles.current=true;fileOwner.current=id;source("files","ready");}
        return true;
      }catch(error:any){
        if(protectedRead&&owns()){
          if(error?.response?.status>=400&&error?.response?.status<500){hasFiles.current=false;setFiles([]);setFolders([]);}
          source("files","error",workspaceError(error));
        }
        throw error;
      }
    }
    const job={id,promise:Promise.resolve(false)};
    job.promise=read().finally(()=>{if(fileRead.current===job)fileRead.current=null;});
    if(protectedRead)fileRead.current=job;
    return job.promise;
  }
  useEffect(() => {
    if(phone||confirmed.current||protectedContext){
      if(fileOwner.current!==projectId){readVersion.current++;fileRead.current=null;hasFiles.current=false;fileOwner.current=projectId;setFiles([]);setFolders([]);setTarget("");}
      if(sources.projects==="ready"&&projectId)void load().catch(()=>{});
      return;
    }
    setFiles([]);setFolders([]);setTarget("");
    void load().catch(() => setError("Unable to load files."));
  }, [projectId,phone,sources.projects,protectedContext]);
  async function verifySaved(){
    if(verification.current)return verification.current;
    const intent=confirmed.current;
    if(!intent||!ownsContext()||!mounted.current||intent.projectId!==projectRef.current)return;
    const epoch=projectEpoch.current;
    setChecking(true);setRecoveryError("");
    const request=(async()=>{
      try{
        if(phases.current.projects!=="ready")await retryProjects.current();
        const verified=await load(intent.projectId,true);
        if(!verified)throw new Error("Reload again to verify the saved changes.");
        if(!ownsProject(intent.projectId,epoch)||confirmed.current!==intent)return;
        confirmed.current=null;setRecovery(null);setNotice(intent.message);
        if(intent.kind==="folder"){folderBaseline.current="";setFolder("");setCompletedRevision(value=>value+1);}
      }catch(error){if(ownsProject(intent.projectId,epoch)&&confirmed.current===intent)setRecoveryError(workspaceError(error));}
      finally{if(ownsProject(intent.projectId,epoch))setChecking(false);}
    })();
    verification.current=request;
    try{await request;}finally{if(verification.current===request)verification.current=null;}
  }
  async function saved(kind:SavedChange["kind"],message:string){
    if(!ownsContext())return;
    const intent={projectId,kind,message};confirmed.current=intent;setRecovery(intent);setRecoveryError("");
    if(kind==="folder"){folderBaseline.current=folder;setSavedRevision(value=>value+1);}
    await verifySaved();
  }
  usePageRefresh(() => confirmed.current?verifySaved():phone&&phases.current.projects!=="ready"?retryProjects.current():load());
  const allowCreate=useModuleAction("create"),allowEdit=useModuleAction("edit"),allowDelete=useModuleAction("delete");
  const canManage = !!projects.find((p) => String(p.id) === projectId)
    ?.can_upload_files && (!routeProjectId || projectId === routeProjectId);
  function sourceNotice(){
    if(recovery)return <div className="pms-files-source" role={recoveryError?"alert":"status"}>
      <p>{recovery.message}. The change was saved; reload to verify the file list.</p>
      {recoveryError&&<p>{recoveryError}</p>}
      <Button type="button" variant="outline" disabled={checking} onClick={()=>void verifySaved()}>{checking?"Checking saved changes…":"Reload saved changes"}</Button>
    </div>;
    if(!phone&&!protectedContext)return null;
    const kind=sources.projects!=="ready"?"projects":"files",phase=sources[kind];
    if(kind==="files"&&!projectId)return <p role="status">No accessible projects available.</p>;
    if(phase==="ready")return null;
    return <div className="pms-files-source" role={phase==="error"?"alert":"status"}>
      <p>{phase==="loading"?(kind==="projects"?"Loading file projects…":hasFiles.current?"Refreshing files and folders…":"Loading files and folders…"):sourceErrors[kind]}</p>
      {phase==="error"&&hasProjects.current&&hasFiles.current&&<p>Showing last loaded files and folders. Reload before making changes.</p>}
      {phase==="error"&&<Button type="button" variant="outline" onClick={()=>kind==="projects"?retryProjects.current():void load().catch(()=>{})}>{kind==="projects"?"Retry projects":"Retry files and folders"}</Button>}
    </div>;
  }
  const withSource=(children:ReactNode)=>phone||recovery||protectedContext?<div>{sourceNotice()}{error&&<p role="alert" className="move-error">{error}</p>}{children}</div>:children;
  const canCreate=canManage&&allowCreate,canEdit=canManage&&allowEdit,canDelete=canManage&&allowDelete;
  async function upload(selected: File[]) {
    if (!ownsContext() || confirmed.current || !selected.length || !projectId || busy || !canCreate || (phone&&(mutationLock.current||!isSourceReady()))) return;
    if(phone)mutationLock.current=true;
    setBusy(true);
    setError("");
    let completed = 0;const epoch=projectEpoch.current,owner=projectId;
    try {
      for (const file of selected) {
        if(protectedContext&&!ownsProject(owner,epoch))return;
        const data = new FormData();
        data.append("file", file);
        if (target) data.append("folder_id", target);
        await api.post(
          `/project-management/projects/${projectId}/files/upload`,
          data,
          { headers: { "Content-Type": "multipart/form-data" } },
        );
        if(protectedContext&&!ownsProject(owner,epoch))return;
        completed++;
      }
    } catch (e) {
      if(protectedContext&&!ownsProject(owner,epoch))return;
      setError(
        (e as { response?: { data?: { detail?: string } } })?.response?.data
          ?.detail || "Upload failed. Completed files have been retained.",
      );
    } finally {
      if(protectedContext&&!ownsProject(owner,epoch))return;
      if(phone&&completed>0)await saved("upload",`${completed} file${completed===1?"":"s"} uploaded`);
      else{
      setNotice(`${completed} file${completed === 1 ? "" : "s"} uploaded`);
      try {
        await load();
      } catch {
        setError(
          "Files were uploaded, but the list could not refresh. Reload to see them.",
        );
      }
      }
      if(phone)mutationLock.current=false;
      setBusy(false);
    }
  }
  async function download(file: PMSFileAsset) {
    if(!ownsContext())return;
    const epoch=projectEpoch.current,owner=projectId;
    if(phone&&(!hasProjects.current||!hasFiles.current||fileOwner.current!==projectRef.current))return;
    try {
      const blob = await filesAPI.downloadBlob(file.id);
      if(protectedContext&&!ownsProject(owner,epoch))return;
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = file.original_name;
      a.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch {
      if(protectedContext&&!ownsProject(owner,epoch))return;
      setError("Unable to download this file.");
    }
  }
  async function removeFile(file:PMSFileAsset){if(!ownsContext()||confirmed.current||!canDelete||busy||(phone&&(mutationLock.current||!isSourceReady()))||String(file.visibility)==="Work Evidence")return;if(!window.confirm(`Move ${file.original_name} to deleted files? Its history will be retained.`))return;if(phone)mutationLock.current=true;setBusy(true);setError("");const epoch=projectEpoch.current,owner=projectId;try{await filesAPI.deleteAttachment(file.id);if(protectedContext&&!ownsProject(owner,epoch))return;if(phone)await saved("delete","File deleted; history retained");else{await load();setNotice("File deleted; history retained.");}}catch(error){if(protectedContext&&!ownsProject(owner,epoch))return;const detail=(error as {response?:{data?:{detail?:unknown}}}).response?.data?.detail;setError(typeof detail==="string"?detail:"Could not delete this file. It is retained for retry.");}finally{if(!protectedContext||ownsProject(owner,epoch)){if(phone)mutationLock.current=false;setBusy(false);}}}
  function fileActions(file:PMSFileAsset){return <><button type="button" data-file-action={phone?"download":undefined} aria-label={`Download ${file.original_name}`} disabled={busy||!recordsVisible} onClick={()=>void download(file)}><Download size={15}/>{phone&&<span>Download</span>}</button>{canDelete&&String(file.visibility)!=="Work Evidence"&&<button type="button" data-file-action={phone?"delete":undefined} aria-label={`Delete ${file.original_name}`} disabled={busy||!sourceReady} onClick={()=>void removeFile(file)}><Trash2 size={15}/>{phone&&<span>Delete</span>}</button>}</>;}
  async function moveFile(file: PMSFileAsset, folderId: string, reportFailure = false) {
    if (!ownsContext() || confirmed.current || !canEdit || busy || (phone&&(mutationLock.current||!isSourceReady())) || String(file.visibility) === "Work Evidence") return;
    if(phone)mutationLock.current=true;
    setBusy(true); setError("");const epoch=projectEpoch.current,owner=projectId;
    try {
      await api.patch(`/project-management/files/${file.id}`, { folder_id: folderId === "root" ? null : Number(folderId), previous_folder_id: file.folder_id || null });
      if(protectedContext&&!ownsProject(owner,epoch))return;
      if(phone)await saved("move","File moved to folder");else{await load(); setNotice("File moved to folder");}
    } catch (error) { if(protectedContext&&!ownsProject(owner,epoch))return;setError("Unable to move this file. Please try again.");if(reportFailure)throw error; }
    finally { if(!protectedContext||ownsProject(owner,epoch)){if(phone)mutationLock.current=false;setBusy(false);} }
  }
  async function createFolder() {
    if (!ownsContext() || confirmed.current || !folder.trim() || !canCreate || busy || (phone&&(mutationLock.current||!isSourceReady()))) return;
    if(phone)mutationLock.current=true;
    setBusy(true); setError("");const epoch=projectEpoch.current,owner=projectId;
    try { await api.post("/project-management/file-folders", { project_id: Number(projectId), name: folder.trim() }); if(protectedContext&&!ownsProject(owner,epoch))return;if(phone)await saved("folder","Folder created");else{setFolder("");await load();setNotice("Folder created");} }
    catch(error) { if(protectedContext&&!ownsProject(owner,epoch))return;setError(phone?workspaceError(error):"Unable to create the folder."); }
    finally { if(!protectedContext||ownsProject(owner,epoch)){if(phone)mutationLock.current=false;setBusy(false);} }
  }
  const missingTarget=phone&&!!target&&!folders.some(item=>String(item.id)===target);
  const missingFilter=phone&&!["all","root"].includes(folderFilter)&&!folders.some(item=>String(item.id)===folderFilter);
  const visibleFiles = files.filter(file => file.original_name.toLowerCase().includes(fileQuery.toLowerCase()) && (folderFilter === "all" || String(file.folder_id || "root") === folderFilter));
  const totalBytes = files.reduce((sum, file) => sum + file.size_bytes, 0);
  if (routeProjectId) return <div className="pms-files pd-files space-y-4">
    <div className="pd-file-stats"><div><Files /><span><strong>{phone&&!sourceReady?"—":files.length}</strong><small>Loaded files</small></span></div><div><Folder /><span><strong>{phone&&!sourceReady?"—":folders.length}</strong><small>Project folders</small></span></div><div><HardDrive /><span><strong>{phone&&!sourceReady?"—":totalBytes >= 1048576 ? `${(totalBytes / 1048576).toFixed(1)} MB` : `${Math.ceil(totalBytes / 1024)} KB`}</strong><small>Loaded file size</small></span></div></div>
    {sourceNotice()}
    {error && <p role="alert" className="move-error">{error}</p>}{notice && <p role="status" className="text-sm text-emerald-700">{notice}</p>}
    <div className={`pd-file-drop ${over ? "is-over" : ""}`} onDragOver={e => { if (canCreate && e.dataTransfer.types.includes("Files")) { e.preventDefault(); setOver(true); } }} onDragLeave={() => setOver(false)} onDrop={e => { e.preventDefault(); setOver(false); void upload(Array.from(e.dataTransfer.files)); }}><Upload /><div><p>{busy ? "Saving your files…" : "Drop project files here"}</p><small>{phone&&sources.projects!=="ready"?"Project access must be verified before making changes.":canCreate ? "Designs, documents, and deliverables — organized in one place." : "You have read-only access to this project’s files."}</small></div><input ref={fileInput} className="sr-only" type="file" multiple aria-label="Upload project files" disabled={busy || !canCreate || !sourceReady} onChange={e => { void upload(Array.from(e.target.files || [])); e.target.value = ""; }} /><Button disabled={busy || !canCreate || !sourceReady} onClick={() => fileInput.current?.click()}><Upload size={15} />Upload files</Button></div>
    <div className="pd-file-toolbar"><label className="pd-file-search"><Search size={17} /><input aria-label="Search project files" value={fileQuery} onChange={e => setFileQuery(e.target.value)} placeholder="Search files by name…" /></label><NativeSelect aria-label="Filter files by folder" value={folderFilter} onChange={e => setFolderFilter(e.target.value)}><option value="all">All folders</option><option value="root">Unfiled</option>{missingFilter&&<option value={folderFilter}>Selected folder (unverified)</option>}{folders.map(f => <option key={f.id} value={f.id}>{f.name}</option>)}</NativeSelect><NativeSelect aria-label="Upload folder" disabled={busy || !canCreate || !sourceReady} value={target} onChange={e => setTarget(e.target.value)}><option value="">Upload to: Unfiled</option>{missingTarget&&<option value={target}>Selected folder (unverified)</option>}{folders.map(f => <option key={f.id} value={f.id}>Upload to: {f.name}</option>)}</NativeSelect><div className="pd-file-views" aria-label="File layout"><button aria-pressed={fileView === "library"} onClick={() => setFileView("library")}><LayoutGrid size={15} />Library</button><button aria-pressed={fileView === "folders"} onClick={() => setFileView("folders")}><Folder size={15} />Folders</button></div></div>
    {recordsVisible&&(fileView === "library" ? <GroupedRecords scope="pms-file-library" items={(visibleFiles) || []} fields={[{id:"visibility",label:"Visibility",value:file=>file.visibility},{id:"folder",label:"Folder",value:file=>folders.find(folder=>folder.id===file.folder_id)?.name || "Unfiled"}]} gridClassName="pd-file-grid" renderItem={(file,_index,closePreview) => {const card=<article className="pd-file-card" key={file.id}><div className="pd-file-preview"><SuiteFileIcon name={file.original_name} /></div><h3>{file.original_name}</h3><small>{Math.max(1, Math.ceil(file.size_bytes / 1024))} KB · {file.visibility} · v{file.version_number}</small><div className="pd-file-card-footer"><NativeSelect aria-label={`Move ${file.original_name} to folder`} disabled={busy || !sourceReady || !canEdit || String(file.visibility) === "Work Evidence"} value={file.folder_id || "root"} onChange={e => void moveFile(file, e.target.value)}><option value="root">Unfiled</option>{folders.map(f => <option key={f.id} value={f.id}>{f.name}</option>)}</NativeSelect>{fileActions(file)}</div></article>;return phone&&closePreview?<div className="pms-files pms-files-preview">{card}</div>:card;}}/> : <MoveBoard label="Project file folders" reorder={false} disabled={busy || !sourceReady || !canEdit} groups={[{ id: "root", label: "Unfiled" }, ...folders.map(f => ({ id: String(f.id), label: f.name }))]} items={visibleFiles.map(file => ({ id: file.id, label: file.original_name, group: file.folder_id ? String(file.folder_id) : "root", disabled: String(file.visibility) === "Work Evidence", content: <div className="flex justify-between text-xs"><span>{Math.ceil(file.size_bytes / 1024)} KB · {file.visibility}</span>{fileActions(file)}</div> }))} onMove={async ({ item, group }) => { const file = files.find(f => f.id === item.id); if (file) await moveFile(file, group, phone); }} />)}
    {(!phone||sourceReady)&&!visibleFiles.length && <p className="pd-files-empty">{files.length ? "No files match your search. Try another name or folder." : "No files yet. Upload the first project document to get started."}</p>}
    {canCreate && <SmartCreateSection onClose={closeFolderDraft} title="Create folder" size="compact" mobileSheet={phone} savedRevision={phone||recovery?savedRevision:0} closeOnRecordSaved={!phone&&!recovery} completionRevision={completedRevision} trigger={phone?<Button className="pms-files-create-trigger"><FolderPlus size={16}/>Create folder</Button>:undefined}>{withSource(<form className="pd-folder-create" onSubmit={e => { e.preventDefault(); void createFolder(); }}><FolderPlus size={17} /><input disabled={!!recovery||(phone&&busy)} aria-label="Folder name" placeholder="New folder name" value={folder} onChange={e => setFolder(e.target.value)} maxLength={120} /><Button data-save-action variant="outline" disabled={!folder.trim() || busy || !sourceReady}>Create folder</Button></form>)}</SmartCreateSection>}
    <p className="text-xs text-muted-foreground">Showing up to 100 files available to you in this project.</p>
  </div>;
  return (
    <div className="pms-files pms-files-global space-y-5">
      <div>
        <h1 className="page-title">Files</h1>
        <p className="page-description">
          Drop files to upload, then move them into project folders.
        </p>
      </div>
      <div className="pms-files-selectors flex flex-wrap items-center gap-3">
        <label>
          Project{" "}
          <NativeSelect
            className="input"
            aria-label="File project"
            value={projectId}
            onChange={(e) => changeProject(e.target.value)}
            disabled={busy || !!recovery || !!routeProjectId || (phone&&sources.projects!=="ready")}
          >
            {phone&&projectId&&!projects.some(project=>String(project.id)===projectId)&&<option value={projectId}>Selected project (unverified)</option>}
            {projects.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name}
              </option>
            ))}
          </NativeSelect>
        </label>
        <label>
          Upload folder{" "}
          <NativeSelect
            className="input"
            aria-label="Upload folder"
            value={target}
            onChange={(e) => setTarget(e.target.value)}
            disabled={busy||!sourceReady}
          >
            <option value="">Unfiled</option>
            {missingTarget&&<option value={target}>Selected folder (unverified)</option>}
            {folders.map((f) => (
              <option key={f.id} value={f.id}>
                {f.name}
              </option>
            ))}
          </NativeSelect>
        </label>
      </div>
      {sourceNotice()}
      {error && (
        <p role="alert" className="move-error">
          {error}
        </p>
      )}
      {notice && <p role="status">{notice}</p>}
      <div
        className={`pms-files-upload rounded-xl border-2 border-dashed p-8 text-center ${over ? "border-primary bg-primary/5" : "border-border"}`}
        onDragOver={(e) => {
          if (e.dataTransfer.types.includes("Files")) {
            e.preventDefault();
            setOver(true);
          }
        }}
        onDragLeave={() => setOver(false)}
        onDrop={(e) => {
          e.preventDefault();
          setOver(false);
          void upload(Array.from(e.dataTransfer.files));
        }}
      >
        <Upload className="mx-auto mb-3" />
        <p>{busy ? "Uploading files…" : "Drop files here or choose files"}</p>
        <input
          className="mt-3 max-w-full"
          aria-label="Upload project files"
          type="file"
          multiple
          disabled={busy || !canCreate || !sourceReady}
          onChange={(e) => {
            void upload(Array.from(e.target.files || []));
            e.target.value = "";
          }}
        />
      </div>
      <SmartCreateSection onClose={closeFolderDraft} title="Create folder" mobileSheet={phone} savedRevision={phone||recovery?savedRevision:0} closeOnRecordSaved={!phone&&!recovery} completionRevision={completedRevision} trigger={phone?<Button className="pms-files-create-trigger"><FolderPlus size={16}/>Create folder</Button>:undefined}>{withSource(<div className="pms-files-folder-form flex gap-2">
        <input
          className="input max-w-xs"
          aria-label="Folder name"
          disabled={!!recovery||(phone&&busy)}
          placeholder="New folder"
          value={folder}
          onChange={(e) => setFolder(e.target.value)}
        />
        <Button data-save-action available={!!(canCreate)}
          disabled={!folder.trim() || busy || !canCreate || !sourceReady}
          onClick={async () => {
            if(!ownsContext()||confirmed.current||(phone&&(!canCreate||busy||mutationLock.current||!isSourceReady()||!folder.trim())))return;
            if(phone)mutationLock.current=true;
            setBusy(true);
            setError("");const epoch=projectEpoch.current,owner=projectId;
            try {
              await api.post("/project-management/file-folders", {
                project_id: Number(projectId),
                name: folder,
              });
              if(protectedContext&&!ownsProject(owner,epoch))return;
              if(phone)await saved("folder","Folder created");else{setFolder("");await load();}
            } catch(error) {
              if(protectedContext&&!ownsProject(owner,epoch))return;
              setError(phone?workspaceError(error):"Could not create folder.");
            } finally {
              if(!protectedContext||ownsProject(owner,epoch)){if(phone)mutationLock.current=false;setBusy(false);}
            }
          }}
        >
          <FolderPlus size={16} />
          Create folder
        </Button>
      </div>)}</SmartCreateSection>
      {recordsVisible&&<MoveBoard
        label="Project file folders"
        reorder={false}
        disabled={busy || !sourceReady || !canEdit}
        groups={[
          { id: "root", label: "Unfiled" },
          ...folders.map((f) => ({ id: String(f.id), label: f.name })),
        ]}
        items={files.map((f) => ({
          id: f.id,
          label: f.original_name,
          group: f.folder_id ? String(f.folder_id) : "root",
          disabled: String(f.visibility) === "Work Evidence",
          content: (
            <div className="flex items-center justify-between text-xs">
              <SuiteFileIcon name={f.original_name}/><span>
                {Math.ceil(f.size_bytes / 1024)} KB · {f.visibility}
              </span>
              {fileActions(f)}
            </div>
          ),
        }))}
        onMove={async ({ item, group }) => {
          if(!ownsContext()||confirmed.current)return;
          if(phone){const file=files.find(file=>file.id===item.id);if(file)await moveFile(file,group,true);return;}
          await api.patch(`/project-management/files/${item.id}`, {
            folder_id: group === "root" ? null : Number(group),
            previous_folder_id:
              item.group === "root" ? null : Number(item.group),
          });
          await load();
        }}
      />}
      {phone&&sourceReady&&!files.length&&<p role="status">No files yet. Upload the first project document to get started.</p>}
      <p className="text-xs text-muted-foreground">
        Showing the latest 100 files in this project.
      </p>
    </div>
  );
}
