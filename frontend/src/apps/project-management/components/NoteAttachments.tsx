import { lazy, Suspense, useEffect, useRef, useState } from "react";
import * as Dialog from "@radix-ui/react-dialog";
import { Download, Paperclip, Trash2, X } from "lucide-react";
import { api } from "@/services/api";
import { Button } from "@/components/ui/button";
import { workspaceError } from "../pages/workspaceTypes";
type Attachment = { id: number; filename: string; media_type: string; size: number };
type Listing = { items: Attachment[]; removed_items: Attachment[]; max_file_bytes: number; max_files: number; max_note_bytes: number };
const NotePdfPreview = lazy(() => import("./NotePdfPreview"));
export default function NoteAttachments({ noteId, readOnly }: { noteId: number; readOnly: boolean }) {
  const [data, setData] = useState<Listing | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [removed, setRemoved] = useState<Attachment | null>(null);
  const [preview, setPreview] = useState<{ item: Attachment; url: string; file: Blob; text?: string } | null>(null);
  const fileInput = useRef<HTMLInputElement>(null);
  const controller = useRef(new AbortController());
  const previewUrl = useRef<string | null>(null);
  const base = `/project-management/notes/${noteId}/attachments`;
  useEffect(() => {
    const abort = new AbortController(); controller.current = abort;
    void api.get<Listing>(base, { signal: abort.signal }).then(({ data }) => setData(data)).catch(e => { if (!abort.signal.aborted) setError(workspaceError(e)); });
    return () => { abort.abort(); if (previewUrl.current) URL.revokeObjectURL(previewUrl.current); };
  }, [base]);
  function closePreview() { setPreview(null); if (previewUrl.current) URL.revokeObjectURL(previewUrl.current); previewUrl.current = null; }
  async function upload(files: FileList | null) {
    if (!files || busy || !data) return;
    setBusy(true); setError("");
    try {
      for (const file of Array.from(files)) {
        if (file.size > data.max_file_bytes || !file.size) throw new Error(`Choose a non-empty file up to ${data.max_file_bytes / 1024 / 1024} MB.`);
        const form = new FormData(); form.append("file", file);
        const { data: item } = await api.post<Attachment>(base, form, { signal: controller.current.signal, uploadLimitBytes: data.max_file_bytes });
        setData(current => current ? { ...current, items: [...current.items, item] } : current);
      }
    } catch (e) { if (!controller.current.signal.aborted) setError(e instanceof Error && !('response' in e) ? e.message : workspaceError(e)); }
    finally { setBusy(false); if (fileInput.current) fileInput.current.value = ""; }
  }
  async function fetchFile(item: Attachment, download: boolean) {
    if (busy) return;
    setBusy(true); setError("");
    try {
      const { data: blob } = await api.get<Blob>(`${base}/${item.id}/download`, { responseType: "blob", signal: controller.current.signal });
      const url = URL.createObjectURL(new Blob([blob], { type: item.media_type }));
      if (download) {
        const link = document.createElement("a"); link.href = url; link.download = item.filename; link.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
      } else {
        closePreview(); previewUrl.current = url;
        setPreview({ item, url, file: blob, text: item.media_type.startsWith("text/") ? await blob.text() : undefined });
      }
    } catch (e) { if (!controller.current.signal.aborted) setError(workspaceError(e)); }
    finally { setBusy(false); }
  }
  async function remove(item: Attachment) {
    if (busy) return; setBusy(true); setError("");
    try { await api.delete(`${base}/${item.id}`, { signal: controller.current.signal }); setData(current => current ? { ...current, items: current.items.filter(i => i.id !== item.id), removed_items: [...current.removed_items, item] } : current); setRemoved(item); }
    catch (e) { if (!controller.current.signal.aborted) setError(workspaceError(e)); } finally { setBusy(false); }
  }
  async function undoRemove(target = removed) {
    if (!target || busy) return; setBusy(true); setError("");
    try { const { data: item } = await api.post<Attachment>(`${base}/${target.id}/restore`, {}, { signal: controller.current.signal }); setData(current => current ? { ...current, items: [...current.items, item], removed_items: current.removed_items.filter(i => i.id !== item.id) } : current); setRemoved(null); }
    catch (e) { if (!controller.current.signal.aborted) setError(workspaceError(e)); } finally { setBusy(false); }
  }
  return <section className="note-attachments" aria-label="Private attachments"><header><h2><Paperclip size={15} />Attachments <span>{data?.items.length ?? ""}</span></h2>{!readOnly && <Button size="sm" variant="outline" disabled={busy || !data} onClick={() => fileInput.current?.click()}>{busy ? "Working…" : "Attach files"}</Button>}</header>
    <input ref={fileInput} type="file" hidden aria-label="Attach private files" multiple accept=".png,.jpg,.jpeg,.gif,.webp,.pdf,.txt,.md,.csv,.docx,.xlsx,.pptx,.zip" onChange={e => void upload(e.target.files)} />
    <p className="notes-attachment-help">Only you can access these files. {data ? `Up to ${data.max_file_bytes / 1024 / 1024} MB per file; ${data.max_files} files / 50 MB per note (including removed files).` : "Loading attachments…"}</p>
    {error && <p role="alert" className="text-destructive text-sm">{error}</p>}
    {data?.items.map(item => <div key={item.id} className="note-attachment-row"><div><strong>{item.filename}</strong><small>{(item.size / 1024).toFixed(1)} KB · Private</small></div>{(item.media_type.startsWith("image/") || item.media_type.startsWith("text/") || item.media_type === "application/pdf") && <Button size="sm" variant="ghost" disabled={busy} aria-label={`Preview ${item.filename}`} onClick={() => void fetchFile(item, false)}>Preview</Button>}<Button size="sm" variant="ghost" disabled={busy} aria-label={`Download ${item.filename}`} onClick={() => void fetchFile(item, true)}><Download size={15} /></Button>{!readOnly && <Button size="sm" variant="ghost" disabled={busy} aria-label={`Remove ${item.filename}`} onClick={() => void remove(item)}><Trash2 size={15} /></Button>}</div>)}
    {removed && <p role="status" className="note-attachment-undo">Removed {removed.filename}.<Button size="sm" variant="ghost" disabled={busy || readOnly} onClick={() => void undoRemove()}>Undo removal</Button></p>}
    {!!data?.removed_items?.length && <details className="notes-note-details"><summary>Removed files ({data.removed_items.length})</summary>{data.removed_items.map(item => <div key={item.id} className="note-attachment-row"><div><strong>{item.filename}</strong><small>Removed · Private</small></div><Button size="sm" variant="outline" disabled={busy || readOnly} aria-label={`Restore ${item.filename}`} onClick={() => void undoRemove(item)}>Restore</Button></div>)}</details>}
    <Dialog.Root open={!!preview} onOpenChange={open => { if (!open) closePreview(); }}><Dialog.Portal><Dialog.Overlay className="notes-modal-overlay" /><Dialog.Content className="notes-modal note-attachment-preview"><Dialog.Title>{preview?.item.filename}</Dialog.Title><Dialog.Description>Private attachment preview. Only your authenticated session can retrieve this file.</Dialog.Description><Dialog.Close asChild><Button className="notes-modal-close" variant="ghost" aria-label="Close attachment preview"><X size={18} /></Button></Dialog.Close>{preview?.item.media_type.startsWith("image/") ? <img src={preview.url} alt={preview.item.filename} /> : preview?.text !== undefined ? <pre>{preview.text}</pre> : preview && <Suspense fallback={<p role="status">Loading PDF viewer…</p>}><NotePdfPreview file={preview.file} /></Suspense>}</Dialog.Content></Dialog.Portal></Dialog.Root>
  </section>;
}

