import {useRef,useState,type ReactNode} from 'react';
import {useInfiniteQuery,useMutation,useQuery,useQueryClient} from '@tanstack/react-query';
import {api} from '@/services/api';
import {useAuthStore} from '@/store/authStore';
import {useRecordScope,recordScope} from '@/lib/record-scope';
import {selectedPackContext} from '@/lib/pack-context';
import {selectedBranch} from '@/lib/branch-context';
import {effectiveOperationalSelection} from '@/lib/effective-operational-selection';
import {securityAuthStamp} from '@/lib/security-auth-stamp';
import {Card,CardHeader,CardTitle,CardContent} from '@/components/ui/card';
import {Input} from '@/components/ui/input';
import {Button} from '@/components/ui/button';
import {NativeSelect} from '@/components/ui/native-select';
import CompactForm from '@/components/forms/CompactForm';
import {SmartCreateSection} from '@/shared/creation/SmartCreateSection';
import {defaultToday} from '@/lib/form-defaults';
import {catalogError} from '@/shared/catalog/api';
import {useFinanceWrite} from './useFinanceWrite';
import type {FAMRecord} from './types';
import PharmaRecallControls from './PharmaRecallControls';

type Page={items:FAMRecord[];next:number|null;has_more:boolean};
type Options={products:{id:number;item_name:string;sku:string}[];warehouses:{id:number;warehouse_name:string}[];next:number|null;has_more:boolean;can_receive:boolean;can_recall:boolean};

/** Fresh server identity, including sole implicit context; no selector writes. */
export default function PharmaInventory({fallback,renderTable}:{fallback:ReactNode;renderTable:(rows:FAMRecord[])=>ReactNode}) {
 const scope=useRecordScope();
 const [mount]=useState(()=>crypto.randomUUID());
 const query=useQuery({queryKey:['srm','inventory-operational-selection',scope,mount],retry:false,staleTime:0,gcTime:0,refetchOnWindowFocus:false,
  queryFn:async()=>{
   const user=useAuthStore.getState().user,owner=recordScope(user),selector=selectedPackContext();
   const config={recordCache:false as const,headers:{'X-Suite-Pack-Context':selector}};
   const [identity,access,result]=await Promise.all([api.get('/auth/me',config),api.get('/access/me',config),api.get('/srm/industry/capabilities',config)]);
   if(owner!==recordScope(useAuthStore.getState().user))throw new Error('Inventory context changed. Reload before continuing.');
   const role=typeof identity.data.role==='string'?identity.data.role:identity.data.role?.name||null;
   const fresh={...user,...identity.data,role,primary_role:role,access:access.data};
   if(securityAuthStamp(fresh)!==securityAuthStamp(user))throw new Error('Your access changed. Reload the page before continuing.');
   return {selection:effectiveOperationalSelection(result.data?.operational_scope,fresh,selectedBranch(),selector),owner};
  }});
 if(!query.data||query.isError)return <Card><CardContent className="space-y-3 pt-4"><p role={query.isError?'alert':'status'}>{query.isError?catalogError(query.error):'Verifying inventory access…'}</p>{query.isError&&<Button onClick={()=>window.location.reload()}>Reload inventory access</Button>}</CardContent></Card>;
 if(query.data.selection.pack_key!=='pharma')return fallback;
 return <PharmaStock key={`${scope}:${mount}`} context={query.data.selection.context_id!} owner={query.data.owner} renderTable={renderTable}/>;
}

function PharmaStock({context,owner,renderTable}:{context:number;owner:string;renderTable:(rows:FAMRecord[])=>ReactNode}) {
 const qc=useQueryClient(),scope=useRecordScope(),key=['srm','pharma-batches',scope,context];
 const config={recordCache:false as const,headers:{'X-Suite-Pack-Context':String(context)}};
 const assertOwner=()=>{if(owner!==recordScope(useAuthStore.getState().user))throw new Error('Inventory context changed. Reopen this form.');};
 const nativeWrite=useFinanceWrite(['srm_manage','srm_admin'],'create');
 const nativeEdit=useFinanceWrite(['srm_manage','srm_admin'],'edit');
 const [search,setSearch]=useState(''),[productSearch,setProductSearch]=useState('');
 const initial=()=>({product:'',warehouse:'',number:'',received:defaultToday('srm'),manufacture:'',expiry:'',quantity:'',cost:'0',sellingPrice:''});
 const [draft,setDraft]=useState(initial),requestKey=useRef(crypto.randomUUID());
 const [receiptCompleted,setReceiptCompleted]=useState(0);
 const batches=useInfiniteQuery({queryKey:[...key,search],initialPageParam:0,retry:false,
  queryFn:async({pageParam,signal})=>{assertOwner();return (await api.get<Page>('/srm/pharma/batches',{...config,signal,params:{search,after:pageParam,limit:30}})).data;},
  getNextPageParam:page=>page.has_more?page.next??undefined:undefined});
 const options=useInfiniteQuery({queryKey:['srm','pharma-options',scope,context,productSearch],initialPageParam:0,retry:false,
  queryFn:async({pageParam,signal})=>{assertOwner();return (await api.get<Options>('/srm/pharma/options',{...config,signal,params:{search:productSearch,after:pageParam,limit:30}})).data;},
  getNextPageParam:page=>page.has_more?page.next??undefined:undefined});
 const products=options.data?.pages.flatMap(page=>page.products)||[],warehouses=options.data?.pages[0]?.warehouses||[];
 const canReceive=nativeWrite&&options.data?.pages[0]?.can_receive===true;
 const update=(field:keyof typeof draft,value:string)=>{setDraft(current=>({...current,[field]:value}));requestKey.current=crypto.randomUUID();};
 const save=useMutation({mutationFn:async()=>{
  assertOwner();
  if(!canReceive)throw new Error('Receiving permission is required.');
  return api.post('/srm/pharma/batch-receipts',{request_key:requestKey.current,product_id:Number(draft.product),warehouse_id:Number(draft.warehouse),
   batch_number:draft.number,received_date:draft.received,manufacture_date:draft.manufacture||null,expiry_date:draft.expiry,quantity:draft.quantity,unit_cost:draft.cost,selling_price:draft.sellingPrice},config);
 },onSuccess:()=>{assertOwner();setDraft(initial());setReceiptCompleted(value=>value+1);requestKey.current=crypto.randomUUID();void qc.invalidateQueries({queryKey:key});void qc.invalidateQueries({queryKey:['srm','inventoryItems','pos']});}});
 const field=(name:keyof typeof draft,label:string,type='text')=><label className="grid min-w-0 gap-1 text-sm">{label}<Input aria-label={label} required={name!=='manufacture'} type={type} value={draft[name]} onChange={e=>update(name,e.target.value)} /></label>;
 return <div className="grid min-w-0 gap-4 lg:grid-cols-2">
  <div className="min-w-0 space-y-4">
  <SmartCreateSection title="Receive medicine batch" size="compact" completionRevision={receiptCompleted}><Card><CardHeader><CardTitle className="text-base">Receive medicine batch</CardTitle></CardHeader><CardContent>
   <CompactForm compactTabs={false} aria-label="Receive medicine batch" className="grid min-w-0 gap-3 md:grid-cols-2" onSubmit={e=>{e.preventDefault();if(!save.isPending)save.mutate();}}>
    <fieldset disabled={!canReceive||save.isPending} className="contents">
     <label className="grid min-w-0 gap-1 text-sm md:col-span-2">Find medicine<Input aria-label="Find medicine" value={productSearch} onChange={e=>setProductSearch(e.target.value)} /></label>
     <label className="grid min-w-0 gap-1 text-sm">Medicine<NativeSelect className="min-w-0 w-full max-w-full" aria-label="Medicine" required value={draft.product} onChange={e=>update('product',e.target.value)}><option value="">Choose medicine</option>{products.map(row=><option key={row.id} value={row.id}>{row.item_name} · {row.sku}</option>)}</NativeSelect></label>
     <label className="grid min-w-0 gap-1 text-sm">Warehouse<NativeSelect className="min-w-0 w-full max-w-full" aria-label="Warehouse" required value={draft.warehouse} onChange={e=>update('warehouse',e.target.value)}><option value="">Choose warehouse</option>{warehouses.map(row=><option key={row.id} value={row.id}>{row.warehouse_name}</option>)}</NativeSelect></label>
     {field('number','Batch number')}{field('received','Received date','date')}{field('manufacture','Manufacture date','date')}{field('expiry','Expiry date','date')}{field('quantity','Quantity')}{field('cost','Unit cost')}{field('sellingPrice','Batch selling price')}
    </fieldset>
    {options.hasNextPage&&<Button type="button" variant="outline" onClick={()=>void options.fetchNextPage()}>More medicines</Button>}
    <p className="text-sm text-muted-foreground md:col-span-2">Enable batch and expiry tracking in Products & Services first. Existing stock is not assigned to a lot automatically. Each receipt creates a new batch and updates warehouse stock together.</p>
    {(save.isError||options.isError)&&<p role="alert" className="text-sm text-destructive md:col-span-2">{catalogError(save.error||options.error)}</p>}
    <Button data-save-action type="submit" disabled={!canReceive||save.isPending||options.isPending}>{save.isPending?'Receiving…':'Receive batch'}</Button>
   </CompactForm>
  </CardContent></Card></SmartCreateSection>
  <PharmaRecallControls context={context} scope={scope} canWrite={nativeWrite&&nativeEdit&&options.data?.pages[0]?.can_recall===true} batches={batches.data?.pages.flatMap(page=>page.items)||[]} assertOwner={assertOwner} refreshBatches={()=>qc.invalidateQueries({queryKey:key})}/>
  </div>
  <Card className="min-w-0"><CardHeader><CardTitle className="text-base">Batches</CardTitle></CardHeader><CardContent className="min-w-0 space-y-3 overflow-x-auto">
   <Input aria-label="Find batches" placeholder="Find batch or medicine…" value={search} onChange={e=>setSearch(e.target.value)}/>
   {batches.isPending&&<p role="status">Loading batches…</p>}{batches.isError&&<p role="alert">{catalogError(batches.error)}</p>}
   {renderTable(batches.data?.pages.flatMap(page=>page.items)||[])}
   {batches.hasNextPage&&<Button variant="outline" disabled={batches.isFetchingNextPage} onClick={()=>void batches.fetchNextPage()}>More batches</Button>}
  </CardContent></Card>
 </div>;
}
