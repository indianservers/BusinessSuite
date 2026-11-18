import { NativeSelect } from "@/components/ui/native-select";
import { useEffect, useRef, useState } from "react";
import * as Dialog from "@radix-ui/react-dialog";
import { Button } from "@/components/ui/button";
import { api } from "@/services/api";
import { catalogChanged, catalogError, type CatalogItem, type CatalogSource } from "./api";

export default function CatalogBranchReuse({ items, source, close, saved }: { items: CatalogItem[]; source: CatalogSource; close: () => void; saved: (message: string) => void }) {
  const [branches, setBranches] = useState<{ id: number; name: string; can_write: boolean; is_active: boolean }[]>([]);
  const [origin, setOrigin] = useState<number>();
  const [destinations, setDestinations] = useState<number[]>([]);
  const [operation, setOperation] = useState<"share" | "copy" | "move">("share");
  const [ready, setReady] = useState(false), [busy, setBusy] = useState(false), [error, setError] = useState("");
  const submitting = useRef(false);
  useEffect(() => {
    let active = true;
    api.get("/branches/context", { progress: false }).then(({ data }) => {
      if (!active) return;
      setOrigin(data.selected); setBranches(data.branches); setReady(true);
    }).catch(error => { if (active) setError(catalogError(error)); });
    return () => { active = false; };
  }, []);
  const targets = branches.filter(branch => branch.id !== origin && branch.can_write && branch.is_active);
  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (submitting.current || !destinations.length) return;
    submitting.current = true; setBusy(true); setError("");
    try {
      await api.post("/catalog/branches/reuse", { operation, items: items.map(({ kind, id, version }) => ({ kind, id, version })), branch_ids: destinations }, { params: { source }, headers: { "X-Suite-Branch": String(origin) } });
      catalogChanged();
      saved(`${items.length} offering${items.length === 1 ? "" : "s"} ${operation === "share" ? "shared with" : operation === "copy" ? "copied to" : "moved to"} ${destinations.length} branch${destinations.length === 1 ? "" : "es"}.`);
    } catch (error) { setError(catalogError(error)); }
    finally { submitting.current = false; setBusy(false); }
  }
  return <Dialog.Root open onOpenChange={open => { if (!open && !busy) close(); }}><Dialog.Portal><Dialog.Overlay className="sc-overlay"/><Dialog.Content className="sc-preview">
    <Dialog.Title>Reuse in other branches</Dialog.Title>
    <Dialog.Description>{items.length} selected offering{items.length === 1 ? "" : "s"} from {branches.find(branch => branch.id === origin)?.name || "the current branch"}.</Dialog.Description>
    <form onSubmit={submit} className="sc-form"><fieldset disabled={busy} className="grid gap-4 border-0 p-0">
      <label>Action<NativeSelect className="mt-1 w-full rounded border p-2" aria-label="Branch reuse action" value={operation} onChange={event => { const value = event.target.value as typeof operation; setOperation(value); if (value === "move") setDestinations(current => current.slice(0, 1)); }}><option value="share">Share the same offering</option><option value="copy">Create an independent copy</option><option value="move">Move to another branch</option></NativeSelect></label>
      <p className="sc-muted">{operation === "share" ? "Use the same product or service in the selected branches. Future edits update the shared offering." : operation === "copy" ? "Copy the details, images and pricing into each selected branch with a new code. Copies can be edited independently and use the organization catalog. Barcodes are cleared on copies." : "Make this offering available in the destination and remove it from this branch’s catalog. Other branches keep their existing availability."}</p>
      <fieldset className="grid gap-2 rounded border p-3"><legend>Destination {operation === "move" ? "branch" : "branches"}</legend>{!ready ? <p>Loading branches…</p> : targets.length ? targets.map(branch => <label key={branch.id} className="sc-branch-choice"><input type={operation === "move" ? "radio" : "checkbox"} name="destination" checked={destinations.includes(branch.id)} onChange={event => setDestinations(current => operation === "move" ? [branch.id] : event.target.checked ? [...current, branch.id] : current.filter(id => id !== branch.id))}/>{branch.name}</label>) : <p>No other writable branches are available.</p>}</fieldset>
      <p className="sc-muted">Stock quantities, customer activity and historical transactions stay in their original branches.</p>
    </fieldset>{error && <p className="sc-error" role="alert">{error}</p>}<footer className="sc-form-footer"><Button type="button" variant="outline" disabled={busy} onClick={close}>Cancel</Button><Button type="submit" disabled={busy || !ready || !destinations.length}>{busy ? "Applying…" : operation === "share" ? "Share offerings" : operation === "copy" ? "Copy offerings" : "Move offerings"}</Button></footer></form>
  </Dialog.Content></Dialog.Portal></Dialog.Root>;
}
