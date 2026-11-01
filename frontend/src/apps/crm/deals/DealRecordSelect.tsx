import {useEffect, useState} from "react";
import {crmApi, type CRMApiRecord} from "../api";
import {Input} from "@/components/ui/input";
import {Button} from "@/components/ui/button";
import {dealError} from "./deal-utils";

export default function DealRecordSelect({resource, value, onChange, initial, name}: {resource: string; value: string; onChange: (value: string) => void; initial: CRMApiRecord[]; name: string}) {
  const [search, setSearch] = useState("");
  const [items, setItems] = useState(initial);
  const [page, setPage] = useState(1), [pages, setPages] = useState(1), [busy, setBusy] = useState(false), [error, setError] = useState("");
  const [retry, setRetry] = useState(0);
  useEffect(() => {setPage(1);}, [search]);
  useEffect(() => {
    let active = true;
    const timer = setTimeout(() => {
      setBusy(true);
      void crmApi.list(resource, {search: search || undefined, page, per_page: 100}).then(response => {
        if (!active) return;
        setItems(current => page === 1 ? response.data.items : [...current, ...response.data.items]);
        setPages(response.data.pages || Math.ceil((response.data.total || 0) / 100) || 1);setError("");
      }).catch(e => {if (active) setError(dealError(e));}).finally(() => {if (active) setBusy(false);});
    }, 250);
    return () => {active = false;clearTimeout(timer);};
  }, [resource, search, page, retry]);
  const combined = [...new Map([...initial.filter(item => String(item.id) === value), ...items].map(item => [String(item.id), item])).values()];
  return <div className="grid gap-1"><Input aria-label={`Search ${name}`} placeholder={`Search ${name.toLowerCase()}...`} value={search} onChange={e => setSearch(e.target.value)}/><select aria-label={name} className="h-10 w-full rounded-md border bg-background px-3 text-sm" value={value} onChange={e => onChange(e.target.value)}><option value="">Select {name.toLowerCase()}</option>{combined.map(item => <option key={String(item.id)} value={String(item.id)}>{String(item.name || item.full_name || item.email || item.id)}</option>)}</select>{busy && <small role="status">Loading choices...</small>}{error && <div role="alert" className="text-xs text-destructive">{error}<Button type="button" variant="ghost" size="sm" onClick={() => setRetry(v => v + 1)}>Retry</Button></div>}{page < pages && <Button type="button" variant="ghost" size="sm" disabled={busy} onClick={() => setPage(v => v + 1)}>Load more choices</Button>}</div>;
}
