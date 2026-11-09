import {useMobile} from "@/components/mobile/useMobile";
import "./fam-mobile-workflows.css";
import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { api } from '@/services/api';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { NativeSelect } from '@/components/ui/native-select';
import GridTable from '@/shared/data-grid/GridTable';
import { DataExportButton } from '@/shared/data-transfer';

type Row = Record<string,string|number>;
type Statement = {currency:string;from_date:string;to_date:string;basis:string;items:Row[];summary:Record<string,string>};
const reports = {trial_balance:'Trial balance',ledger_report:'General ledger',profit_and_loss:'Profit and loss',balance_sheet:'Balance sheet'};
function errorMessage(error:unknown) { const detail=(error as {response?:{data?:{detail?:unknown}}})?.response?.data?.detail;return typeof detail==='string'?detail:'The statement could not be loaded.'; }

export default function FinancialStatementsPage(){
  const phone=useMobile(480);
  const [draft,setDraft]=useState({report:'trial_balance',from_date:'',to_date:''});
  const [filters,setFilters]=useState(draft);
  const query=useQuery({queryKey:['fam','financial-statements',filters],queryFn:async()=>(await api.get<Statement>(`/fam/financial-statements/${filters.report}`,{params:{from_date:filters.from_date||undefined,to_date:filters.to_date||undefined}})).data});
  const rows=query.data?.items||[];
  const columns=filters.report==='balance_sheet'?['ledger_name','nature','amount']:filters.report==='profit_and_loss'?['ledger_name','nature','debit','credit','amount']:['ledger_code','ledger_name','opening_balance','debit','credit','closing_balance'];
  return <section className="space-y-4 fam-mobile-statements"><h1 className="text-2xl font-semibold">Financial statements</h1>
    <form className="flex flex-wrap items-end gap-3 fam-statement-filters" onSubmit={e=>{e.preventDefault();if(JSON.stringify(draft)===JSON.stringify(filters))query.refetch();else setFilters({...draft});}}>
      <label>Statement<NativeSelect className="block h-10 rounded border bg-background px-3" value={draft.report} onChange={e=>setDraft({...draft,report:e.target.value})}>{Object.entries(reports).map(([key,label])=><option key={key} value={key}>{label}</option>)}</NativeSelect></label>
      <label>From date<Input type="date" value={draft.from_date} onChange={e=>setDraft({...draft,from_date:e.target.value})}/></label>
      <label>To date<Input type="date" min={draft.from_date} value={draft.to_date} onChange={e=>setDraft({...draft,to_date:e.target.value})}/></label>
      <Button disabled={query.isFetching}>Run statement</Button>
    </form>
    {query.isLoading&&<p role="status">Loading statement...</p>}{query.isError&&<p role="alert">{errorMessage(query.error)}</p>}
    {query.data&&<><p>{query.data.from_date} to {query.data.to_date} · {query.data.currency}. {query.data.basis}</p>
      <div className="flex flex-wrap gap-4 fam-statement-summary">{Object.entries(query.data.summary).map(([key,value])=><div className="rounded border p-3" key={key}><p className="text-sm capitalize">{key.replace(/_/g,' ')}</p><strong>{value} {query.data.currency}</strong></div>)}</div>
      <div className="overflow-x-auto fam-statement-rows" role={phone ? "region" : undefined} aria-label={phone ? "Statement rows, scroll for more columns" : undefined} tabIndex={phone ? 0 : undefined}><GridTable gridId={`fam-statement-${filters.report}`} className="w-full text-sm"><thead><tr>{columns.map(key=><th className="p-2 text-left capitalize" key={key}>{key.replace(/_/g,' ')}</th>)}</tr></thead><tbody>{rows.map((row,index)=><tr key={String(row.ledger_id||`summary-${index}`)}>{columns.map(key=><td className="border-t p-2" key={key}>{String(row[key]??'')}</td>)}</tr>)}{!rows.length&&<tr><td colSpan={columns.length} className="p-4">No posted balances for this period.</td></tr>}</tbody></GridTable></div>
      <DataExportButton label="Export statement CSV" filename={filters.report} load={async()=>{
        const job=(await api.post<{id:number}>('/fam/exports',{export_type:filters.report,export_format:'csv',filters_json:{from_date:query.data?.from_date,to_date:query.data?.to_date}})).data;
        const file=(await api.get<{file_content:string}>(`/fam/exports/${job.id}/download`)).data;
        return new Blob([file.file_content],{type:'text/csv'});
      }}/></>}
  </section>;
}
