import { usePageRefresh } from "@/lib/page-refresh";
import { useEffect, useRef, useState } from "react";
import { Upload, FolderPlus, Download } from "lucide-react";
import { api } from "@/services/api";
import MoveBoard from "@/components/interaction/MoveBoard";
import { Button } from "@/components/ui/button";
import { filesAPI, projectsAPI } from "../services/api";
import type { PMSFileAsset, PMSProject } from "../types";

type Folder = { id: number; name: string };
export default function FilesPage() {
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
  const projectRef = useRef(projectId);
  projectRef.current = projectId;
  useEffect(() => {
    projectsAPI
      .list()
      .then((items) => {
        setProjects(items);
        setProjectId(String(items[0]?.id || ""));
      })
      .catch(() => setError("Unable to load projects."));
  }, []);
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
  const canEdit = !!projects.find((p) => String(p.id) === projectId)
    ?.can_upload_files;
  async function upload(selected: File[]) {
    if (!selected.length || !projectId || busy || !canEdit) return;
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
          <select
            className="input"
            value={projectId}
            onChange={(e) => setProjectId(e.target.value)}
            disabled={busy}
          >
            {projects.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name}
              </option>
            ))}
          </select>
        </label>
        <label>
          Upload folder{" "}
          <select
            className="input"
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
          </select>
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
          disabled={busy || !canEdit}
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
        <Button
          disabled={!folder.trim() || busy || !canEdit}
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
              <span>
                {Math.ceil(f.size_bytes / 1024)} KB · {f.visibility}
              </span>
              <button
                type="button"
                aria-label={`Download ${f.original_name}`}
                onClick={() => void download(f)}
              >
                <Download size={14} />
              </button>
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
