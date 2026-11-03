import { ChoiceStatus } from "@/components/ui/choice-status";
import { NativeSelect } from "@/components/ui/native-select";
import {useEffect, useState} from "react";
import {Button} from "@/components/ui/button";
import {Input} from "@/components/ui/input";
import {crmApi, type CRMApiRecord} from "../api";
import {dealError} from "./deal-utils";

export default function DealCatalogSelect({initial, value, savedName, onSelect}: {initial: CRMApiRecord[]; value: string; savedName?: string; onSelect: (value: string, item: CRMApiRecord) => void}) {
  const [search, setSearch] = useState(""), [page, setPage] = useState(1), [pages, setPages] = useState(1);
  const [items, setItems] = useState(initial), [busy, setBusy] = useState(false), [error, setError] = useState(""), [retry, setRetry] = useState(0);
  useEffect(() => {setPage(1);}, [search]);
  useEffect(() => {
    let active = true;
    setBusy(true);
    const timer = setTimeout(() => {
      setBusy(true);
      void Promise.all(["products", "services"].map(async resource => {
        const response = await crmApi.list(resource, {search: search || undefined, page, per_page: 100});
        return {items: response.data.items.map(item => ({...item, catalogKind: resource === "services" ? "service" : "product"})), pages: response.data.pages || Math.ceil((response.data.total || 0) / 100) || 1};
      })).then(responses => {if (active) {setItems(current => page === 1 ? responses.flatMap(item => item.items) : [...current, ...responses.flatMap(item => item.items)]);setPages(Math.max(...responses.map(item => item.pages)));setError("");}}).catch(e => {if (active) setError(dealError(e));}).finally(() => {if (active) setBusy(false);});
    }, 250);
    return () => {active = false;clearTimeout(timer);};
  }, [search, page, retry]);
  const merged = [...new Map([...initial.filter(item => `${item.catalogKind || "product"}:${item.id}` === value), ...items].map(item => [`${item.catalogKind || "product"}:${item.id}`, item])).values()];
  const selectedExists = merged.some(item => `${item.catalogKind || "product"}:${item.id}` === value);
  return <div className="grid min-w-52 gap-1"><Input type="search" aria-label="Search products or services" className="h-8" placeholder="Search catalog..." value={search} onChange={e => setSearch(e.target.value)}/><NativeSelect loading={busy} error={!!error} aria-label="Catalog item" className="h-9 w-full rounded-md border bg-background px-2" value={value} onChange={e => {const item = merged.find(row => `${row.catalogKind || "product"}:${row.id}` === e.target.value);onSelect(e.target.value, item || {});}}><option value="">Select product or service...</option>{value && !selectedExists && <option value={value}>{savedName || `Saved item #${value.split(":")[1]}`}</option>}{merged.map(item => <option key={`${item.catalogKind || "product"}:${item.id}`} value={`${item.catalogKind || "product"}:${item.id}`}>{String(item.name || item.sku || item.id)} ({item.catalogKind === "service" ? "Service" : "Product"}, {String(item.currency || "INR")})</option>)}</NativeSelect><ChoiceStatus loading={busy} empty={!merged.length} error={!!error} loadingText="Loading catalog…" />{page < pages && <Button variant="ghost" size="sm" type="button" disabled={busy} onClick={() => setPage(v => v + 1)}>Load more items</Button>}{error && <p role="alert" className="text-xs text-destructive">{error}<button type="button" className="ml-2 underline" onClick={() => setRetry(v => v + 1)}>Retry</button></p>}</div>;
}
