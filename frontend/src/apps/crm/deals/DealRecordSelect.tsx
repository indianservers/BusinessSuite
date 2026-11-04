import SharedCompanySelect from "@/shared/master-data/CompanySelect";
import SmartRecordPicker from "@/shared/records/SmartRecordPicker";
import { NativeSelect } from "@/components/ui/native-select";
import {useEffect, useState} from "react";
import {crmApi, type CRMApiRecord} from "../api";
import {Input} from "@/components/ui/input";
import {Button} from "@/components/ui/button";
import {dealError} from "./deal-utils";

type Props = {resource: string; value: string; onChange: (value: string) => void; initial: CRMApiRecord[]; name: string; onSelected?: (record: CRMApiRecord) => void; companyId?: string; onCreate?: (seedName: string) => void};
function RecordSelect({resource, value, onChange, initial, name, onSelected, companyId, onCreate}: Props) {
  const [search, setSearch] = useState("");
  const [items, setItems] = useState(initial);
  const [selected, setSelected] = useState<CRMApiRecord>();
  const [page, setPage] = useState(1), [pages, setPages] = useState(1), [busy, setBusy] = useState(false), [error, setError] = useState("");
  const [retry, setRetry] = useState(0);
  useEffect(() => {setPage(1);}, [search]);
  useEffect(() => {
    let active = true;
    setBusy(true);
    const timer = setTimeout(() => {
      setBusy(true);
      void crmApi.list(resource, {search: search || undefined, ...(companyId ? {company_id: Number(companyId)} : {}), page, per_page: 100}).then(response => {
        if (!active) return;
        setItems(current => page === 1 ? response.data.items : [...current, ...response.data.items]);
        setPages(response.data.pages || Math.ceil((response.data.total || 0) / 100) || 1);setError("");
      }).catch(e => {if (active) setError(dealError(e));}).finally(() => {if (active) setBusy(false);});
    }, 250);
    return () => {active = false;clearTimeout(timer);};
  }, [resource, search, page, retry, companyId]);
  const combined = [...new Map([...initial, ...items, ...(selected ? [selected] : [])].map(item => [String(item.id), item])).values()]
    .filter(item => resource !== "contacts" || !companyId || String(item.company_id || item.companyId || "") === companyId);
  const suggest = (item: CRMApiRecord) => ({id: String(item.id), label: String(item.full_name || item.fullName || item.name || item.email || `Record #${item.id}`), description: [item.company_name || item.companyName || item.company, item.email, item.phone, item.status].filter(Boolean).map(String).join(" · "), record: item});
  const current = combined.find(item => String(item.id) === value);
  return <SmartRecordPicker name={name} value={value} search={search} onSearch={value => {setSearch(value);setPage(1);}}
    items={combined.map(suggest)} selected={current ? suggest(current) : undefined}
    onSelect={record => {setSelected(record);onChange(String(record.id));onSelected?.(record);setSearch("");}}
    onClear={() => {onChange("");setSelected(undefined);}} loading={busy} error={error || undefined} retry={() => setRetry(v => v + 1)}
    onCreate={onCreate} hasMore={page < pages} loadMore={() => setPage(v => v + 1)}/>;
}

export default function DealRecordSelect(props: Props) {
  return props.resource === "companies" ? <SharedCompanySelect value={props.value} onChange={props.onChange} label={props.name} entityKind="all" onCreate={props.onCreate}
    onSelected={company=>props.onSelected?.(company as unknown as CRMApiRecord)} initial={props.initial.map(row=>({...row,id:Number(row.id),name:String(row.name||row.full_name||row.id)}))}/> : <RecordSelect {...props}/>;
}
