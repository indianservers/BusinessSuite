import {useRef,useState} from 'react';
import {useInfiniteQuery,useMutation,useQueryClient} from '@tanstack/react-query';
import {api} from '@/services/api';
import {Card,CardHeader,CardTitle,CardContent} from '@/components/ui/card';
import {Input} from '@/components/ui/input';
import {NativeSelect} from '@/components/ui/native-select';
import {Button} from '@/components/ui/button';
import CompactForm from '@/components/forms/CompactForm';
import {SmartCreateSection} from '@/shared/creation/SmartCreateSection';
import {catalogError} from '@/shared/catalog/api';
import type {FAMRecord} from './types';

type Case={id:number;revision:number;state:'open'|'closed';action:string;batch_id:number;batch_number:string;batch_status:string;batch_revision:number;reason:string};
type Page={items:Case[];has_more:boolean;next:number|null};
type Batch={id:number;batch_number:string;item_name:string;status:string;state_revision:number};

export default function PharmaRecallControls({context,scope,canWrite,batches,assertOwner,refreshBatches}:{context:number;scope:string;canWrite:boolean;batches:FAMRecord[];assertOwner:()=>void;refreshBatches:()=>Promise<unknown>}) {
 const qc=useQueryClient(),key=['srm','pharma-recalls',scope,context];
 const config={recordCache:false as const,headers:{'X-Suite-Pack-Context':String(context)}};
 const [selected,setSelected]=useState<Batch|null>(null),[review,setReview]=useState<Case|null>(null),[action,setAction]=useState('quarantine'),[reason,setReason]=useState('');
 const [completed,setCompleted]=useState(0);
 const request=useRef(crypto.randomUUID());
 const cases=useInfiniteQuery({queryKey:key,initialPageParam:0,retry:false,enabled:canWrite,
  queryFn:async({pageParam,signal})=>{assertOwner();return (await api.get<Page>('/srm/pharma/recalls',{...config,signal,params:{after:pageParam,limit:30}})).data;},
  getNextPageParam:page=>page.has_more?page.next??undefined:undefined});
 const pick=(row:FAMRecord|undefined)=>{setSelected(row?{id:Number(row.id),batch_number:String(row.batch_number),item_name:String(row.item_name),status:String(row.status),state_revision:Number(row.state_revision)}:null);request.current=crypto.randomUUID();};
 const save=useMutation({mutationFn:async()=>{
  assertOwner();if(!canWrite||!selected)throw new Error('Select an available batch and receiving authority.');
  const common={request_key:request.current,expected_batch_revision:selected.state_revision,expected_batch_status:selected.status,action,reason};
  return review?api.post<Case>(`/srm/pharma/recalls/${review.id}/commands`,{...common,expected_revision:review.revision},config):api.post<Case>('/srm/pharma/recalls',{...common,batch_id:selected.id},config);
 },onSuccess:async()=>{assertOwner();await Promise.all([refreshBatches(),qc.invalidateQueries({queryKey:key})]);assertOwner();setSelected(null);setReview(null);setAction('quarantine');setReason('');setCompleted(value=>value+1);request.current=crypto.randomUUID();}});
 if(!canWrite)return null;
 const rows=cases.data?.pages.flatMap(page=>page.items)||[];
 return <div className="space-y-4">
  <SmartCreateSection title="Quarantine or recall batch" size="compact" autoOpen={review!==null} completionRevision={completed} onClose={()=>setReview(null)}><Card><CardHeader><CardTitle className="text-base">{review?'Review recall case':'Quarantine or recall batch'}</CardTitle></CardHeader><CardContent>
   <CompactForm compactTabs={false} aria-label="Batch quality action" className="grid min-w-0 gap-3" onSubmit={event=>{event.preventDefault();if(!save.isPending)save.mutate();}}>
    <fieldset className="contents" disabled={save.isPending}>
     <label className="grid min-w-0 gap-1 text-sm">Batch<NativeSelect className="min-w-0 w-full max-w-full" aria-label="Quality action batch" required disabled={review!==null} value={selected?.id??''} onChange={event=>{pick(batches.find(row=>Number(row.id)===Number(event.target.value)));setReview(null);}}><option value="">Choose a loaded batch</option>{batches.map(row=><option key={String(row.id)} value={String(row.id)}>{String(row.batch_number)} · {String(row.item_name)}</option>)}</NativeSelect></label>
     {selected&&<p className="text-sm text-muted-foreground">Current batch state: {selected.status}. Stock remains in the warehouse.</p>}
     <label className="grid min-w-0 gap-1 text-sm">Action<NativeSelect className="min-w-0 w-full max-w-full" aria-label="Batch quality action" value={action} onChange={event=>{setAction(event.target.value);request.current=crypto.randomUUID();}}>{review?<><option value="recall">Confirm recall</option><option value="close">Close case, keep stock blocked</option></>:<><option value="quarantine">Quarantine for review</option><option value="recall">Recall batch</option></>}</NativeSelect></label>
     <label className="grid min-w-0 gap-1 text-sm">Reason<Input aria-label="Batch quality reason" required minLength={3} maxLength={2000} value={reason} onChange={event=>{setReason(event.target.value);request.current=crypto.randomUUID();}}/></label>
    </fieldset>
    <p className="text-sm text-muted-foreground">Quarantine and recall block this batch from sale. Closing a case keeps the stock blocked and preserves its history.</p>
    {save.isError&&<p role="alert" className="text-sm text-destructive">{catalogError(save.error)}</p>}
    <Button data-save-action type="submit" disabled={!selected||save.isPending}>{save.isPending?'Recording…':'Record batch action'}</Button>
   </CompactForm>
  </CardContent></Card></SmartCreateSection>
  <Card className="min-w-0"><CardHeader><CardTitle className="text-base">Recall cases</CardTitle></CardHeader><CardContent className="space-y-3">
   {cases.isPending&&<p role="status">Loading recall cases…</p>}{cases.isError&&<p role="alert">{catalogError(cases.error)}</p>}
   {!cases.isPending&&!rows.length&&!cases.isError&&<p className="text-sm text-muted-foreground">No recall cases in this business context.</p>}
   {rows.map(row=>{const batch=batches.find(item=>Number(item.id)===row.batch_id);return <div key={row.id} className="space-y-2 rounded-lg border p-3 text-sm"><p className="font-medium">{row.batch_number} · {row.state}</p><p>{row.reason}</p><p className="text-muted-foreground">{row.batch_status}</p>{row.state==='open'&&<Button type="button" variant="outline" disabled={!batch||cases.isFetching||cases.isError||save.isPending} onClick={()=>{pick(batch);setReview(row);setAction(row.batch_status==='recalled'?'close':'recall');setReason('');request.current=crypto.randomUUID();}}>Review case</Button>}{!batch&&row.state==='open'&&<p className="text-muted-foreground">Load this batch in the batch list to review its current state.</p>}</div>;})}
   {cases.hasNextPage&&<Button variant="outline" onClick={()=>void cases.fetchNextPage()}>More recall cases</Button>}
  </CardContent></Card>
 </div>;
}
