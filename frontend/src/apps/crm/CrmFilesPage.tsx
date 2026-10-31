import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/services/api";
import MoveBoard from "@/components/interaction/MoveBoard";
type Cabinet = {
  folders: { id: number; name: string }[];
  files: { id: number; name: string; folder_id: number | null; size: number }[];
};
export default function CrmFilesPage() {
  const query = useQuery({
    queryKey: ["crm-file-workspace"],
    queryFn: () => api.get<Cabinet>("/crm/file-workspace").then((r) => r.data),
  });
  const [name, setName] = useState("");
  const [target, setTarget] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [over, setOver] = useState(false);
  async function upload(files: File[]) {
    if (busy || !files.length) return;
    setBusy(true);
    setError("");
    let count = 0;
    try {
      for (const file of files) {
        const form = new FormData();
        form.append("file", file);
        if (target) form.append("folder_id", target);
        await api.post("/crm/file-workspace/upload", form, {
          headers: { "Content-Type": "multipart/form-data" },
        });
        count++;
      }
    } catch (e) {
      setError(
        (e as { response?: { data?: { detail?: string } } })?.response?.data
          ?.detail || "Upload failed.",
      );
    } finally {
      setNotice(`${count} files uploaded`);
      await query.refetch();
      setBusy(false);
    }
  }
  async function download(file: Cabinet["files"][number]) {
    try {
      const response = await api.get(
        `/crm/file-workspace/files/${file.id}/download`,
        { responseType: "blob" },
      );
      const url = URL.createObjectURL(response.data);
      const a = document.createElement("a");
      a.href = url;
      a.download = file.name;
      a.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch {
      setError("Unable to download file.");
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
        </p>
      )}
      {notice && <p role="status">{notice}</p>}
      <label>
        Upload folder{" "}
        <select
          className="input max-w-xs"
          value={target}
          onChange={(e) => setTarget(e.target.value)}
        >
          <option value="">Unfiled</option>
          {query.data?.folders.map((f) => (
            <option key={f.id} value={f.id}>
              {f.name}
            </option>
          ))}
        </select>
      </label>
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
        <p>{busy ? "Uploading…" : "Drop files here or choose files"}</p>
        <input
          type="file"
          aria-label="Upload CRM files"
          multiple
          disabled={busy}
          onChange={(e) => {
            void upload(Array.from(e.target.files || []));
            e.target.value = "";
          }}
        />
      </div>
      <div className="flex gap-2">
        <input
          className="input max-w-xs"
          aria-label="CRM folder name"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Folder name"
        />
        <button
          disabled={busy || !name.trim()}
          onClick={async () => {
            setBusy(true);
            setError("");
            try {
              await api.post("/crm/file-workspace/folders", { name });
              setName("");
              await query.refetch();
            } catch {
              setError("Unable to create folder.");
            } finally {
              setBusy(false);
            }
          }}
        >
          Create folder
        </button>
      </div>
      <MoveBoard
        label="CRM file folders"
        reorder={false}
        disabled={busy}
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
              <span>{Math.ceil(f.size / 1024)} KB</span>
              <button onClick={() => void download(f)}>Download</button>
            </div>
          ),
        }))}
        onMove={async ({ item, group }) => {
          try {
            await api.put(`/crm/file-workspace/files/${item.id}/folder`, {
              folder_id: group === "root" ? null : Number(group),
              previous_folder_id:
                item.group === "root" ? null : Number(item.group),
            });
          } finally {
            await query.refetch();
          }
        }}
      />
      <p className="text-xs text-muted-foreground">
        Showing up to 200 accessible files.
      </p>
    </div>
  );
}
