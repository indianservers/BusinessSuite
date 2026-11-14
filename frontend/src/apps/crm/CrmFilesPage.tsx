import { useModuleAction } from "@/hooks/use-module-action";
import { Button } from "@/components/ui/button";
import { SmartCreateSection } from "@/shared/creation/SmartCreateSection";
import { SuiteFileIcon } from "@/components/visuals/SuiteVisuals";
import { NativeSelect } from "@/components/ui/native-select";
import { useEffect, useRef, useState } from "react";
import { useAuthStore } from "@/store/authStore";
import { recordScope, useRecordScope } from "@/shared/records/Record360Workspace";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/services/api";
import MoveBoard from "@/components/interaction/MoveBoard";
type Cabinet = {
  can_manage: boolean;
  folders: { id: number; name: string }[];
  files: { id: number; name: string; folder_id: number | null; size: number }[];
};
export default function CrmFilesPage() {
  const scope = useRecordScope();
  return <FilesWorkspace key={scope} scope={scope} />;
}
function FilesWorkspace({ scope }: { scope: string }) {
  const active = useRef(true), owner = useRef(recordScope(useAuthStore.getState().user));
  useEffect(() => { active.current = true; return () => { active.current = false; }; }, []);
  const owns = () => active.current && owner.current === recordScope(useAuthStore.getState().user);
  const createAction = useModuleAction("create"), editAction = useModuleAction("edit");
  const query = useQuery({
    queryKey: ["crm-file-workspace", scope],
    queryFn: ({ signal }) => api.get<Cabinet>("/crm/file-workspace", { signal }).then((r) => r.data),
  });
  const canCreate = query.isSuccess && !!query.data?.can_manage && createAction;
  const canMove = query.isSuccess && !!query.data?.can_manage && editAction;
  const [name, setName] = useState("");
  const [target, setTarget] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [over, setOver] = useState(false);
  async function upload(files: File[]) {
    if (!owns() || !canCreate || busy || !files.length) return;
    setBusy(true);
    setError("");
    let count = 0;
    try {
      for (const file of files) {
        if (!owns()) return;
        const form = new FormData();
        form.append("file", file);
        if (target) form.append("folder_id", target);
        await api.post("/crm/file-workspace/upload", form, {
          headers: { "Content-Type": "multipart/form-data" },
        });
        count++;
      }
    } catch (e) {
      if (!owns()) return;
      setError(
        (e as { response?: { data?: { detail?: string } } })?.response?.data
          ?.detail || "Upload failed.",
      );
    } finally {
      if (owns()) {
        setNotice(`${count} files uploaded`);
        setBusy(false);
        void query.refetch();
      }
    }
  }
  async function download(file: Cabinet["files"][number]) {
    if (!owns()) return;
    setError("");
    try {
      const response = await api.get(
        `/crm/file-workspace/files/${file.id}/download`,
        { responseType: "blob" },
      );
      if (!owns()) return;
      const url = URL.createObjectURL(response.data);
      const a = document.createElement("a");
      a.href = url;
      a.download = file.name;
      a.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch {
      if (owns()) setError("Unable to download file.");
    }
  }
  return (
    <div className="space-y-5">
      <div>
        <h1 className="page-title">CRM Files</h1>
        <p className="page-description">
          Upload files and organize them into shared folders.
        </p>
      </div>
      {(error || query.isError) && (
        <p role="alert" className="move-error">
          {error || "Unable to load files."}
          {query.isError && <Button type="button" variant="outline" onClick={() => void query.refetch()}>Retry files</Button>}
        </p>
      )}
      {notice && <p role="status">{notice}</p>}
      <label>
        Upload folder{" "}
        <NativeSelect loading={query.isFetching} error={query.isError}
          className="input max-w-xs"
          disabled={!canCreate || busy}
          value={target}
          onChange={(e) => setTarget(e.target.value)}
        >
          <option value="">Unfiled</option>
          {query.data?.folders.map((f) => (
            <option key={f.id} value={f.id}>
              {f.name}
            </option>
          ))}
        </NativeSelect>
      </label>
      <div
        className={`rounded-xl border-2 border-dashed p-8 text-center ${over ? "border-primary bg-primary/5" : "border-border"}`}
        onDragOver={(e) => {
          if (canCreate && e.dataTransfer.types.includes("Files")) {
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
        <p>{busy ? "Uploading…" : "Drop files here or choose files"}</p>
        <input
          type="file"
          aria-label="Upload CRM files"
          multiple
          disabled={!canCreate || busy}
          onChange={(e) => {
            void upload(Array.from(e.target.files || []));
            e.target.value = "";
          }}
        />
      </div>
      <SmartCreateSection title="Create folder"><div className="flex gap-2">
        <input
          className="input max-w-xs"
          aria-label="CRM folder name"
          disabled={!canCreate || busy}
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Folder name"
        />
        <Button type="submit" variant="default"
          disabled={!canCreate || busy || !name.trim()}
          onClick={async () => {
            if (!owns() || !canCreate) return;
            setBusy(true);
            setError("");
            try {
              await api.post("/crm/file-workspace/folders", { name });
              if (!owns()) return;
              setName("");
              void query.refetch();
            } catch {
              if (owns()) setError("Unable to create folder.");
            } finally {
              if (owns()) setBusy(false);
            }
          }}
        >
          Create folder
        </Button>
      </div></SmartCreateSection>
      <MoveBoard
        label="CRM file folders"
        reorder={false}
        disabled={!canMove || busy}
        groups={[
          { id: "root", label: "Unfiled" },
          ...(query.data?.folders || []).map((f) => ({
            id: String(f.id),
            label: f.name,
          })),
        ]}
        items={(query.data?.files || []).map((f) => ({
          id: f.id,
          label: f.name,
          group: f.folder_id ? String(f.folder_id) : "root",
          content: (
            <div className="flex justify-between text-xs">
              <SuiteFileIcon name={f.name}/><span>{Math.ceil(f.size / 1024)} KB</span>
              <Button type="submit" variant="outline" onClick={() => void download(f)}>Download</Button>
            </div>
          ),
        }))}
        onMove={async ({ item, group }) => {
          if (!owns() || !canMove) return;
          try {
            await api.put(`/crm/file-workspace/files/${item.id}/folder`, {
              folder_id: group === "root" ? null : Number(group),
              previous_folder_id:
                item.group === "root" ? null : Number(item.group),
            });
          } finally {
            if (owns()) await query.refetch();
          }
        }}
      />
      <p className="text-xs text-muted-foreground">
        Showing up to 200 accessible files.
      </p>
    </div>
  );
}
