import { useModuleAction } from "@/hooks/use-module-action";
import GroupedRecords from "@/shared/data-grid/GroupedRecords";
import { useParams } from "react-router-dom";
import { SuiteFileIcon } from "@/components/visuals/SuiteVisuals";
import { NativeSelect } from "@/components/ui/native-select";
import { usePageRefresh } from "@/lib/page-refresh";
import { useEffect, useRef, useState } from "react";
import { Upload, FolderPlus, Download, Search, LayoutGrid, Folder, Files, HardDrive, Trash2 } from "lucide-react";
import { api } from "@/services/api";
import MoveBoard from "@/components/interaction/MoveBoard";
import { Button } from "@/components/ui/button";
import { filesAPI, projectsAPI } from "../services/api";
import type { PMSFileAsset, PMSProject } from "../types";

type Folder = { id: number; name: string };
export default function FilesPage() {
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
  useEffect(() => {
    let active = true;
    setProjectId(routeProjectId || ""); setFolder(""); setFileQuery(""); setFolderFilter("all");
    void projectsAPI.list().then(async items => {
      const selected = routeProjectId && !items.some(project => String(project.id) === routeProjectId) ? await projectsAPI.get(Number(routeProjectId)) : null;
      if (!active) return;
      setProjects(selected ? [selected, ...items] : items);
      setProjectId(routeProjectId || String(items[0]?.id || ""));
    }).catch(() => { if (active) setError("Unable to load projects."); });
    return () => { active = false; };
  }, [routeProjectId]);

  async function load(id = projectId) {
    if (!id) return;
    const [assets, directories] = await Promise.all([
      filesAPI.list({ project_id: Number(id) }),
      api.get<Folder[]>("/project-management/file-folders", {
        params: { project_id: Number(id) },
      }),
    ]);
    if (id === projectRef.current) {
      setFiles(assets);
      setFolders(directories.data);
    }
  }
  useEffect(() => {
    setFiles([]);
    setFolders([]);
    setTarget("");
    void load().catch(() => setError("Unable to load files."));
  }, [projectId]);
  usePageRefresh(() => load());
  const allowCreate=useModuleAction("create"),allowEdit=useModuleAction("edit"),allowDelete=useModuleAction("delete");
  const canManage = !!projects.find((p) => String(p.id) === projectId)
    ?.can_upload_files && (!routeProjectId || projectId === routeProjectId);
  const canCreate=canManage&&allowCreate,canEdit=canManage&&allowEdit,canDelete=canManage&&allowDelete;
  async function upload(selected: File[]) {
    if (!selected.length || !projectId || busy || !canCreate) return;
    setBusy(true);
    setError("");
    let completed = 0;
    try {
      for (const file of selected) {
        const data = new FormData();
        data.append("file", file);
        if (target) data.append("folder_id", target);
        await api.post(
          `/project-management/projects/${projectId}/files/upload`,
          data,
          { headers: { "Content-Type": "multipart/form-data" } },
        );
        completed++;
      }
    } catch (e) {
      setError(
        (e as { response?: { data?: { detail?: string } } })?.response?.data
          ?.detail || "Upload failed. Completed files have been retained.",
      );
    } finally {
      setNotice(`${completed} file${completed === 1 ? "" : "s"} uploaded`);
      try {
        await load();
      } catch {
        setError(
          "Files were uploaded, but the list could not refresh. Reload to see them.",
        );
      }
      setBusy(false);
    }
  }
  async function download(file: PMSFileAsset) {
    try {
      const blob = await filesAPI.downloadBlob(file.id);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = file.original_name;
      a.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch {
      setError("Unable to download this file.");
    }
  }
  async function removeFile(file:PMSFileAsset){if(!canDelete||busy||String(file.visibility)==="Work Evidence")return;if(!window.confirm(`Move ${file.original_name} to deleted files? Its history will be retained.`))return;setBusy(true);setError("");try{await filesAPI.deleteAttachment(file.id);await load();setNotice("File deleted; history retained.");}catch(error){const detail=(error as {response?:{data?:{detail?:unknown}}}).response?.data?.detail;setError(typeof detail==="string"?detail:"Could not delete this file. It is retained for retry.");}finally{setBusy(false);}}
  function fileActions(file:PMSFileAsset){return <><button type="button" aria-label={`Download ${file.original_name}`} disabled={busy} onClick={()=>void download(file)}><Download size={15}/></button>{canDelete&&String(file.visibility)!=="Work Evidence"&&<button type="button" aria-label={`Delete ${file.original_name}`} disabled={busy} onClick={()=>void removeFile(file)}><Trash2 size={15}/></button>}</>;}
  async function moveFile(file: PMSFileAsset, folderId: string) {
    if (!canEdit || busy || String(file.visibility) === "Work Evidence") return;
    setBusy(true); setError("");
    try {
      await api.patch(`/project-management/files/${file.id}`, { folder_id: folderId === "root" ? null : Number(folderId), previous_folder_id: file.folder_id || null });
      await load(); setNotice("File moved to folder");
    } catch { setError("Unable to move this file. Please try again."); }
    finally { setBusy(false); }
  }
  async function createFolder() {
    if (!folder.trim() || !canCreate || busy) return;
    setBusy(true); setError("");
    try { await api.post("/project-management/file-folders", { project_id: Number(projectId), name: folder.trim() }); setFolder(""); await load(); setNotice("Folder created"); }
    catch { setError("Unable to create the folder."); }
    finally { setBusy(false); }
  }
  const visibleFiles = files.filter(file => file.original_name.toLowerCase().includes(fileQuery.toLowerCase()) && (folderFilter === "all" || String(file.folder_id || "root") === folderFilter));
  const totalBytes = files.reduce((sum, file) => sum + file.size_bytes, 0);
  if (routeProjectId) return <div className="pd-files space-y-4">
    <div className="pd-file-stats"><div><Files /><span><strong>{files.length}</strong><small>Loaded files</small></span></div><div><Folder /><span><strong>{folders.length}</strong><small>Project folders</small></span></div><div><HardDrive /><span><strong>{totalBytes >= 1048576 ? `${(totalBytes / 1048576).toFixed(1)} MB` : `${Math.ceil(totalBytes / 1024)} KB`}</strong><small>Loaded file size</small></span></div></div>
    {error && <p role="alert" className="move-error">{error}</p>}{notice && <p role="status" className="text-sm text-emerald-700">{notice}</p>}
    <div className={`pd-file-drop ${over ? "is-over" : ""}`} onDragOver={e => { if (canCreate && e.dataTransfer.types.includes("Files")) { e.preventDefault(); setOver(true); } }} onDragLeave={() => setOver(false)} onDrop={e => { e.preventDefault(); setOver(false); void upload(Array.from(e.dataTransfer.files)); }}><Upload /><div><p>{busy ? "Saving your files…" : "Drop project files here"}</p><small>{canCreate ? "Designs, documents, and deliverables — organized in one place." : "You have read-only access to this project’s files."}</small></div><input ref={fileInput} className="sr-only" type="file" multiple aria-label="Upload project files" disabled={busy || !canCreate} onChange={e => { void upload(Array.from(e.target.files || [])); e.target.value = ""; }} /><Button disabled={busy || !canCreate} onClick={() => fileInput.current?.click()}><Upload size={15} />Upload files</Button></div>
    <div className="pd-file-toolbar"><label className="pd-file-search"><Search size={17} /><input aria-label="Search project files" value={fileQuery} onChange={e => setFileQuery(e.target.value)} placeholder="Search files by name…" /></label><NativeSelect aria-label="Filter files by folder" value={folderFilter} onChange={e => setFolderFilter(e.target.value)}><option value="all">All folders</option><option value="root">Unfiled</option>{folders.map(f => <option key={f.id} value={f.id}>{f.name}</option>)}</NativeSelect><NativeSelect aria-label="Upload folder" disabled={busy || !canCreate} value={target} onChange={e => setTarget(e.target.value)}><option value="">Upload to: Unfiled</option>{folders.map(f => <option key={f.id} value={f.id}>Upload to: {f.name}</option>)}</NativeSelect><div className="pd-file-views" aria-label="File layout"><button aria-pressed={fileView === "library"} onClick={() => setFileView("library")}><LayoutGrid size={15} />Library</button><button aria-pressed={fileView === "folders"} onClick={() => setFileView("folders")}><Folder size={15} />Folders</button></div></div>
    {fileView === "library" ? <GroupedRecords scope="pms-file-library" items={(visibleFiles) || []} fields={[{id:"visibility",label:"Visibility",value:file=>file.visibility},{id:"folder",label:"Folder",value:file=>folders.find(folder=>folder.id===file.folder_id)?.name || "Unfiled"}]} gridClassName="pd-file-grid" renderItem={file => <article className="pd-file-card" key={file.id}><div className="pd-file-preview"><SuiteFileIcon name={file.original_name} /></div><h3>{file.original_name}</h3><small>{Math.max(1, Math.ceil(file.size_bytes / 1024))} KB · {file.visibility} · v{file.version_number}</small><div className="pd-file-card-footer"><NativeSelect aria-label={`Move ${file.original_name} to folder`} disabled={busy || !canEdit || String(file.visibility) === "Work Evidence"} value={file.folder_id || "root"} onChange={e => void moveFile(file, e.target.value)}><option value="root">Unfiled</option>{folders.map(f => <option key={f.id} value={f.id}>{f.name}</option>)}</NativeSelect>{fileActions(file)}</div></article>}/> : <MoveBoard label="Project file folders" reorder={false} disabled={busy || !canEdit} groups={[{ id: "root", label: "Unfiled" }, ...folders.map(f => ({ id: String(f.id), label: f.name }))]} items={visibleFiles.map(file => ({ id: file.id, label: file.original_name, group: file.folder_id ? String(file.folder_id) : "root", disabled: String(file.visibility) === "Work Evidence", content: <div className="flex justify-between text-xs"><span>{Math.ceil(file.size_bytes / 1024)} KB · {file.visibility}</span>{fileActions(file)}</div> }))} onMove={async ({ item, group }) => { const file = files.find(f => f.id === item.id); if (file) await moveFile(file, group); }} />}
    {!visibleFiles.length && <p className="pd-files-empty">{files.length ? "No files match your search. Try another name or folder." : "No files yet. Upload the first project document to get started."}</p>}
    {canCreate && <form className="pd-folder-create" onSubmit={e => { e.preventDefault(); void createFolder(); }}><FolderPlus size={17} /><input aria-label="Folder name" placeholder="New folder name" value={folder} onChange={e => setFolder(e.target.value)} maxLength={120} /><Button variant="outline" disabled={!folder.trim() || busy}>Create folder</Button></form>}
    <p className="text-xs text-muted-foreground">Showing up to 100 files available to you in this project.</p>
  </div>;
  return (
    <div className="space-y-5">
      <div>
        <h1 className="page-title">Files</h1>
        <p className="page-description">
          Drop files to upload, then move them into project folders.
        </p>
      </div>
      <div className="flex flex-wrap items-center gap-3">
        <label>
          Project{" "}
          <NativeSelect
            className="input"
            aria-label="File project"
            value={projectId}
            onChange={(e) => setProjectId(e.target.value)}
            disabled={busy || !!routeProjectId}
          >
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
            disabled={busy}
          >
            <option value="">Unfiled</option>
            {folders.map((f) => (
              <option key={f.id} value={f.id}>
                {f.name}
              </option>
            ))}
          </NativeSelect>
        </label>
      </div>
      {error && (
        <p role="alert" className="move-error">
          {error}
        </p>
      )}
      {notice && <p role="status">{notice}</p>}
      <div
        className={`rounded-xl border-2 border-dashed p-8 text-center ${over ? "border-primary bg-primary/5" : "border-border"}`}
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
          disabled={busy || !canCreate}
          onChange={(e) => {
            void upload(Array.from(e.target.files || []));
            e.target.value = "";
          }}
        />
      </div>
      <div className="flex gap-2">
        <input
          className="input max-w-xs"
          aria-label="Folder name"
          placeholder="New folder"
          value={folder}
          onChange={(e) => setFolder(e.target.value)}
        />
        <Button available={!!(canCreate)}
          disabled={!folder.trim() || busy || !canCreate}
          onClick={async () => {
            setBusy(true);
            setError("");
            try {
              await api.post("/project-management/file-folders", {
                project_id: Number(projectId),
                name: folder,
              });
              setFolder("");
              await load();
            } catch {
              setError("Could not create folder.");
            } finally {
              setBusy(false);
            }
          }}
        >
          <FolderPlus size={16} />
          Create folder
        </Button>
      </div>
      <MoveBoard
        label="Project file folders"
        reorder={false}
        disabled={busy || !canEdit}
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
          await api.patch(`/project-management/files/${item.id}`, {
            folder_id: group === "root" ? null : Number(group),
            previous_folder_id:
              item.group === "root" ? null : Number(item.group),
          });
          await load();
        }}
      />
      <p className="text-xs text-muted-foreground">
        Showing the latest 100 files in this project.
      </p>
    </div>
  );
}
