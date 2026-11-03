import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/services/api";
import { Button } from "@/components/ui/button";

type Branch = { id: number; name: string };
type Inventory = { tables: { table: string; category: string }[] };
type Review = { total: number; items: { resource_key: string; name?: string; title?: string; order_number?: string; invoice_number?: string; branch_id?: number }[] };

export default function BranchOwnershipReview({ branches }: { branches: Branch[] }) {
  const [table, setTable] = useState("crm_companies");
  const [branch, setBranch] = useState("");
  const [keys, setKeys] = useState<string[]>([]);
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const inventory = useQuery<Inventory>({ queryKey: ["branch-ownership-inventory"], queryFn: async () => (await api.get("/branches/ownership/inventory")).data });
  const review = useQuery<Review>({ queryKey: ["branch-ownership-review", table], enabled: false, retry: false, queryFn: async () => (await api.get("/branches/ownership/unassigned", { params: { table_name: table } })).data });
  async function action(path: string, payload: object) {
    setBusy(true); setMessage("");
    try {
      const response = await api.post(path, { reason, ...payload });
      setMessage(`Assigned ${response.data.total ?? response.data.assigned} records. Unresolved records remain hidden from branch-restricted users.`);
      setKeys([]); await review.refetch();
    } catch (error: any) { setMessage(error?.response?.data?.detail || "Unable to update ownership."); }
    finally { setBusy(false); }
  }
  return <details className="mt-5 border-t pt-4"><summary className="cursor-pointer font-medium">Review historical data ownership</summary><div className="mt-3 grid gap-3 text-sm">
    <p className="text-muted-foreground">Assign existing records using trusted evidence. A creator's current branch is not historical evidence. Child records inherit from their parents when the evidence agrees.</p>
    <label className="grid gap-1">Business table<select aria-label="Ownership business table" className="rounded border bg-background p-2" value={table} onChange={e => { setTable(e.target.value); setKeys([]); }}><option value="crm_companies">crm_companies</option>{inventory.data?.tables.filter(t => t.category !== "shared" && t.table !== "crm_companies").map(t => <option key={t.table} value={t.table}>{t.table} · {t.category}</option>)}</select></label>
    <Button variant="outline" disabled={busy || review.isFetching} onClick={() => void review.refetch()}>Load unassigned records</Button>
    {review.isError && <p role="alert">{(review.error as any)?.response?.data?.detail || "Unable to load records."}</p>}
    {review.data && <><p>{review.data.total} unassigned records · showing up to 100</p><div className="max-h-48 overflow-auto rounded border p-2">{review.data.items.map(row => <label key={row.resource_key} className="flex gap-2 py-1"><input type="checkbox" checked={keys.includes(row.resource_key)} onChange={e => setKeys(e.target.checked ? [...keys, row.resource_key] : keys.filter(k => k !== row.resource_key))} />{row.name || row.title || row.order_number || row.invoice_number || `Record ${row.resource_key}`} <span className="text-muted-foreground">#{row.resource_key}</span></label>)}{!review.data.items.length && <p>No unassigned records in this table.</p>}</div></>}
    <label className="grid gap-1">Destination branch<select aria-label="Ownership destination branch" className="rounded border bg-background p-2" value={branch} onChange={e => setBranch(e.target.value)}><option value="">Choose branch</option>{branches.map(b => <option key={b.id} value={b.id}>{b.name}</option>)}</select></label>
    <label className="grid gap-1">Evidence / reason<input className="rounded border bg-background p-2" value={reason} onChange={e => setReason(e.target.value)} minLength={5} maxLength={1000} /></label>
    <Button disabled={busy || !keys.length || !branch || reason.trim().length < 5} onClick={() => void action("/branches/ownership/assign", { table_name: table, resource_keys: keys, branch_id: Number(branch) })}>Assign {keys.length || "selected"} records</Button>
    <Button variant="outline" disabled={busy || reason.trim().length < 5} onClick={() => void action("/branches/ownership/backfill", {})}>Infer ownership from verified branches and parents</Button>
    {message && <p role="status">{message}</p>}
  </div></details>;
}
