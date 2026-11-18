import {useEffect,useRef,useState,type ReactNode} from 'react';
import {useInfiniteQuery,useMutation,useQuery,useQueryClient} from '@tanstack/react-query';
import {api} from '@/services/api';
import {useAuthStore} from '@/store/authStore';
import {recordScope,useRecordScope} from '@/lib/record-scope';
import {selectedPackContext} from '@/lib/pack-context';
import {selectedBranch} from '@/lib/branch-context';
import {effectiveOperationalSelection} from '@/lib/effective-operational-selection';
import {securityAuthStamp} from '@/lib/security-auth-stamp';
import type {BusinessPackDiscovery} from '@/lib/business-pack-types';
import {csvText,downloadBlob} from '@/shared/data-transfer';
import {logicalIntentScope} from '@/lib/logical-intent-scope';
import {readFinancialIntent,saveFinancialIntent,clearFinancialIntent} from '@/lib/financial-intent';
import {Card,CardHeader,CardTitle,CardContent} from '@/components/ui/card';
import {Button} from '@/components/ui/button';
import {Input} from '@/components/ui/input';
import {NativeSelect} from '@/components/ui/native-select';
import CompactForm from '@/components/forms/CompactForm';
import GridTable from '@/shared/data-grid/GridTable';
import {catalogError} from '@/shared/catalog/api';
import {useFinanceWrite} from '@/apps/fam/useFinanceWrite';
import type {FAMRecord} from '@/apps/fam/types';

type Mode='receipt'|'stock'|'warehouse'|'daily';
type Table=(rows:FAMRecord[],columns:string[])=>ReactNode;
type Product={product_id:number;sku:string;name:string;currency:string;tracked:boolean;branch_quantity:string;warehouses:{warehouse_id:number;available_quantity:string}[]};
type Stock={items:Product[];warehouses:{id:number;warehouse_name:string}[];receipt_date:string;can_receive:boolean;next_after:number|null};
type Page={items:FAMRecord[];next_after:number|null};
type Receipt={request_key:string;product_id:number;warehouse_id:number;quantity:string;unit_cost:string;currency:string;received_date:string;reference_number?:string;notes?:string};
type Intent={payload:Receipt};

function TableView({rows,columns}:{rows:FAMRecord[];columns:string[]}) {
 return <div className="overflow-x-auto"><GridTable gridId={`business-packs/retail:transactions:${columns.join("-")}`} className="w-full text-left text-sm"><thead><tr>{columns.map(key=><th key={key} className="px-3 py-2">{key.replace(/_/g,' ')}</th>)}</tr></thead><tbody>{rows.map((row,index)=><tr key={String(row.id??index)}>{columns.map(key=><td key={key} className="px-3 py-2">{row[key]==null?'—':String(row[key])}</td>)}</tr>)}</tbody></GridTable></div>;
}

/** Generic children remain unmounted until fresh native and pack identity is proved. */
export default function RetailWorkspace({fallback,mode,renderTable,receiptTitle='Stock in',header}:{fallback:ReactNode;mode:Mode;renderTable?:Table;receiptTitle?:string;header?:ReactNode}) {
 const scope=useRecordScope(),[mount]=useState(()=>crypto.randomUUID());
 const selection=useQuery({queryKey:['srm','retail-selection',scope,mount],retry:false,staleTime:0,gcTime:0,refetchOnWindowFocus:false,queryFn:async()=>{
  const user=useAuthStore.getState().user,owner=recordScope(user),selector=selectedPackContext();
  const config={recordCache:false as const,headers:{'X-Suite-Pack-Context':selector}};
  const [identity,access]=await Promise.all([api.get('/auth/me',config),api.get('/access/me',config)]);
  if(owner!==recordScope(useAuthStore.getState().user)||selector!==selectedPackContext())throw Error('Inventory context changed. Reload before continuing.');
  const role=typeof identity.data.role==='string'?identity.data.role:identity.data.role?.name||null;
  const fresh={...user,...identity.data,role,primary_role:role,access:access.data};
  if(securityAuthStamp(fresh)!==securityAuthStamp(user))throw Error('Your access changed. Reload before continuing.');
  const discovery=(fresh.access as {businessPacks?:BusinessPackDiscovery}).businessPacks;
  if(selector!==null){
   const choice=discovery?.contexts?.find(item=>String(item.contextId)===selector&&String(item.branchId)===selectedBranch());
   if(!/^[1-9][0-9]*$/.test(selector)||discovery?.state!=='ready'||discovery.hasMore!==false||discovery.selectionState!=='verified'||String(discovery.selectedContextId)!==selector||!choice)throw Error('Inventory context verification is unavailable. Reload before continuing.');
   if(choice.packKey!=='retail')return {selection:null,owner};
  }else{
   if(discovery?.state==='unavailable'&&discovery.reason==='not_installed')return {selection:null,owner};
   if(discovery?.state!=='ready'||discovery.hasMore!==false)throw Error('Inventory context verification is unavailable. Reload before continuing.');
   const retail=discovery.contexts.some(item=>item.packKey==='retail'&&(selectedBranch()==='all'||String(item.branchId)===selectedBranch()));
   if(!retail)return {selection:null,owner};
  }
  const result=await api.get('/srm/industry/capabilities',config);
  if(owner!==recordScope(useAuthStore.getState().user)||selector!==selectedPackContext())throw Error('Inventory context changed. Reload before continuing.');
  return {selection:effectiveOperationalSelection(result.data?.operational_scope,fresh,selectedBranch(),selector),owner};
 }});
 if(!selection.data||selection.isError)return <Card><CardContent className="space-y-3 pt-4"><p role={selection.isError?'alert':'status'}>{selection.isError?catalogError(selection.error):'Verifying inventory access…'}</p>{selection.isError&&<Button onClick={()=>window.location.reload()}>Reload inventory access</Button>}</CardContent></Card>;
 if(!selection.data.selection||selection.data.selection.pack_key!=='retail')return fallback;
 return <RetailContent key={`${scope}:${mount}:${mode}`} context={selection.data.selection.context_id!} owner={selection.data.owner} mode={mode} title={receiptTitle} header={header} renderTable={renderTable??((rows,columns)=><TableView rows={rows} columns={columns}/>)}/>;
}

function RetailContent({context,owner,mode,title,renderTable,header}:{context:number;owner:string;mode:Mode;title:string;renderTable:Table;header?:ReactNode}) {
 const scope=useRecordScope(),qc=useQueryClient(),active=useRef(true);
 useEffect(()=>{active.current=true;return()=>{active.current=false;};},[]);
 const assertOwner=()=>{if(!active.current||owner!==recordScope(useAuthStore.getState().user))throw Error('Inventory context changed. Reopen this screen.');};
 const config={recordCache:false as const,headers:{'X-Suite-Pack-Context':String(context),'X-Suite-Expected-Pack-Realm':'pack'}};
 const prefix=['srm','retail',scope,context],nativeWrite=useFinanceWrite(['srm_manage','srm_admin'],'create');
 const stock=useInfiniteQuery({queryKey:[...prefix,'stock'],initialPageParam:0,retry:false,enabled:mode!=='daily',queryFn:async({pageParam,signal})=>{assertOwner();return (await api.get<Stock>('/srm/retail/stock',{...config,signal,params:{after:pageParam,limit:100}})).data;},getNextPageParam:page=>page.next_after??undefined});
 const history=useInfiniteQuery({queryKey:[...prefix,'receipts'],initialPageParam:0,retry:false,enabled:mode==='receipt',queryFn:async({pageParam,signal})=>{assertOwner();return (await api.get<Page>('/srm/retail/stock-receipts',{...config,signal,params:{after:pageParam,limit:100}})).data;},getNextPageParam:page=>page.next_after??undefined});
 const [day,setDay]=useState(''),[selected,setSelected]=useState('Sales'),[message,setMessage]=useState('');
 const report=useQuery({queryKey:[...prefix,'daily',day],retry:false,enabled:mode==='daily',queryFn:async({signal})=>{assertOwner();return (await api.get<FAMRecord>('/srm/retail/reports/daily',{...config,signal,params:day?{day}:undefined})).data;}});
 useEffect(()=>{if(!day&&typeof report.data?.day==='string')setDay(report.data.day);},[report.data,day]);
 const [intentKey]=useState(()=>`suite-financial-intent-v1:${JSON.stringify([logicalIntentScope(),'retail-stock-receipt',null])}`);
 const [recovery]=useState(()=>mode==='receipt'?readFinancialIntent<Intent>(intentKey):{pending:false,payload:null});
 const valid=recovery.payload?.payload&&typeof recovery.payload.payload.request_key==='string'&&Number.isSafeInteger(recovery.payload.payload.product_id)&&Number.isSafeInteger(recovery.payload.payload.warehouse_id);
 const pending=useRef<Receipt|null>(valid?recovery.payload!.payload:null),uncertain=useRef(recovery.pending);
 const initial=()=>({product:'',warehouse:'',quantity:'1',rate:'0',date:stock.data?.pages[0]?.receipt_date??'',reference:'',notes:''});
 const [draft,setDraft]=useState(()=>pending.current?{product:String(pending.current.product_id),warehouse:String(pending.current.warehouse_id),quantity:pending.current.quantity,rate:pending.current.unit_cost,date:pending.current.received_date,reference:pending.current.reference_number??'',notes:pending.current.notes??''}:initial());
 const [locked,setLocked]=useState(recovery.pending),[error,setError]=useState(''),[completed,setCompleted]=useState('');
 const products=stock.data?.pages.flatMap(page=>page.items)||[],warehouses=stock.data?.pages[0]?.warehouses||[];
 useEffect(()=>{const day=stock.data?.pages[0]?.receipt_date;if(day&&!pending.current)setDraft(old=>old.date?old:{...old,date:day});},[stock.data]);
 const canReceive=nativeWrite&&stock.data?.pages[0]?.can_receive===true;
 const save=useMutation({mutationFn:async()=>{
  assertOwner();if(!canReceive)throw Error('Receiving permission is required.');
  if(!navigator.locks)throw Error('Receipt coordination is unavailable. Use a supported secure browser.');
  return navigator.locks.request(intentKey,async()=>{
   assertOwner();
   const stored=readFinancialIntent<Intent>(intentKey),saved=stored.payload?.payload;
   if(stored.pending&&(!saved||typeof saved.request_key!=='string'||!Number.isSafeInteger(saved.product_id)||!Number.isSafeInteger(saved.warehouse_id)))throw Error('A pending receipt cannot be read. Resolve it before creating another receipt.');
   if(saved&&pending.current&&saved.request_key!==pending.current.request_key)throw Error('Another receipt is pending. Reload to recover it before continuing.');
   let command=saved||pending.current;
   if(saved)uncertain.current=true;
   if(!command){
    const product=products.find(row=>row.product_id===Number(draft.product));
    if(!product||product.tracked||!warehouses.some(row=>row.id===Number(draft.warehouse)))throw Error('Choose an available quantity-only item and warehouse.');
    if(!/^(?:\d+\.?\d{0,2}|\.\d{1,2})$/.test(draft.quantity)||Number(draft.quantity)<=0||!/^(?:\d+\.?\d{0,2}|\.\d{1,2})$/.test(draft.rate))throw Error('Enter a positive quantity and nonnegative rate with at most two decimal places.');
    command={request_key:crypto.randomUUID(),product_id:product.product_id,warehouse_id:Number(draft.warehouse),quantity:draft.quantity,unit_cost:draft.rate,currency:product.currency,received_date:draft.date,reference_number:draft.reference,notes:draft.notes};
   }
   saveFinancialIntent(intentKey,{payload:command});pending.current=command;setLocked(true);
   setDraft({product:String(command.product_id),warehouse:String(command.warehouse_id),quantity:command.quantity,rate:command.unit_cost,date:command.received_date,reference:command.reference_number??'',notes:command.notes??''});
   const clearOwn=()=>{if(readFinancialIntent<Intent>(intentKey).payload?.payload?.request_key===command.request_key)clearFinancialIntent(intentKey);};
   try{const result=(await api.post('/srm/retail/stock-receipts',command,config)).data as {number:string};clearOwn();return result;}
   catch(failure){const status=(failure as {response?:{status?:number}}).response?.status;if(status===422&&!uncertain.current){clearOwn();pending.current=null;setLocked(false);}else uncertain.current=true;throw failure;}
  });
 },onSuccess:result=>{
  if(!active.current||owner!==recordScope(useAuthStore.getState().user))return;
  pending.current=null;uncertain.current=false;setLocked(false);setDraft(initial());setError('');setCompleted(`Stock receipt posted: ${result.number}`);
  void qc.invalidateQueries({queryKey:prefix});void qc.invalidateQueries({queryKey:['srm','pos-catalog']});
 },onError:failure=>{if(active.current&&owner===recordScope(useAuthStore.getState().user))setError(catalogError(failure));}});
 const loading=mode==='daily'?report.isPending:stock.isPending;
 const failure=mode==='daily'?report.error:stock.error;
 if(loading||failure)return <Card><CardContent className="space-y-3 pt-4"><p role={failure?'alert':'status'}>{failure?catalogError(failure):'Loading inventory…'}</p>{failure&&<Button onClick={()=>void (mode==='daily'?report.refetch():stock.refetch())}>Retry</Button>}</CardContent></Card>;
 const stockRows:FAMRecord[]=products.map(row=>({id:row.product_id,sku:row.sku,item_name:row.name,current_quantity:row.branch_quantity}));
 const warehouseRows:FAMRecord[]=products.flatMap(row=>row.warehouses.map(location=>({id:`${row.product_id}:${location.warehouse_id}`,sku:row.sku,item_name:row.name,warehouse_name:warehouses.find(w=>w.id===location.warehouse_id)?.warehouse_name??String(location.warehouse_id),quantity:location.available_quantity})));
 const field=(label:string,key:'quantity'|'rate'|'date'|'reference'|'notes',type='text')=><label className="grid gap-1 text-sm">{label}<Input aria-label={label} type={type} required={key!=='reference'&&key!=='notes'} maxLength={key==='reference'?120:key==='notes'?4000:undefined} inputMode={key==='quantity'||key==='rate'?'decimal':undefined} value={draft[key]} onChange={e=>setDraft(old=>({...old,[key]:e.target.value}))}/></label>;
 if(mode==='daily'){
  const data=report.data||{},list=(key:string)=>Array.isArray(data[key])?data[key] as FAMRecord[]:[];
  const registers=list('registers').map(row=>({...row,id:row.session_id,lifetime_expected_cash:(row.lifetime_reconciliation as FAMRecord)?.expected_cash,reconciliation_required:row.currency_reconciliation_required||(row.lifetime_reconciliation as FAMRecord)?.reconciliation_required}));
  const definitions:{title:string;rows:FAMRecord[];columns:string[]}[]=[
   {title:'Sales',rows:list('sales'),columns:['currency','count','gross','tax']},{title:'Collections',rows:list('collections'),columns:['currency','method','amount']},{title:'Refunds',rows:list('refunds'),columns:['currency','amount']},{title:'Daily registers',rows:registers,columns:['session_id','status','cash_collected','cash_in','cash_out','net_cash_change','lifetime_expected_cash','reconciliation_required']},{title:'Stock movements',rows:list('stock_movements'),columns:['product_id','warehouse_id','quantity_in','quantity_out']}
  ];
  const preview=definitions.find(item=>item.title===selected)||definitions[0];
  const exportRows=(report:typeof preview)=>{assertOwner();if(!report.rows.length){setMessage(`${report.title} has no rows available to export.`);return;}downloadBlob(new Blob([csvText(report.rows,report.columns,true)],{type:'text/csv;charset=utf-8'}),`retail-${report.title}-${day}.csv`);setMessage(`${report.title} CSV exported.`);};
  return <div className="space-y-5">{header}<div className="flex flex-wrap items-end gap-3"><label className="grid gap-1 text-sm">Report date<Input aria-label="Report date" type="date" value={day} onChange={e=>setDay(e.target.value)}/></label><Button variant="outline" onClick={()=>void report.refetch()}>Refresh</Button><span className="text-sm text-muted-foreground">{String(data.timezone??'')}</span></div>{message&&<p role="status">{message}</p>}
   <div className="grid min-w-0 grid-cols-1 gap-4 xl:grid-cols-[minmax(0,1.1fr)_minmax(360px,0.9fr)]"><div className="grid min-w-0 grid-cols-1 gap-3 md:grid-cols-2">{definitions.map(item=><Card key={item.title} className={preview.title===item.title?'border-primary/60':undefined}><CardHeader><CardTitle className="text-base">{item.title}</CardTitle></CardHeader><CardContent className="space-y-3"><div className="text-sm text-muted-foreground">{item.rows.length} recorded transactions</div><div className="rounded-lg border bg-muted/30 p-3 text-xs"><span className="font-medium">Filters:</span> {day} · {String(data.timezone??'')}</div><div className="flex flex-wrap gap-2"><Button size="sm" variant="outline" onClick={()=>{setSelected(item.title);setMessage(`${item.title} preview loaded`);}}>View details</Button><Button size="sm" variant="secondary" onClick={()=>exportRows(item)}>Export</Button></div></CardContent></Card>)}</div>
   <Card className="min-w-0 xl:sticky xl:top-4 xl:self-start"><CardHeader><CardTitle className="text-base">{preview.title} Preview</CardTitle></CardHeader><CardContent className="space-y-4">{renderTable(preview.rows,preview.columns)}<div className="flex flex-wrap items-center justify-between gap-2 text-xs text-muted-foreground"><span>{preview.rows.length} rows available for CSV export.</span><Button size="sm" variant="outline" disabled={!preview.rows.length} onClick={()=>exportRows(preview)}>Export CSV</Button></div></CardContent></Card></div>
  </div>;
 }
 return <div className="space-y-4">{mode==='receipt'&&<Card><CardHeader><CardTitle className="text-base">{title}</CardTitle></CardHeader><CardContent><CompactForm compactTabs={false} aria-label="Retail stock receipt" className="grid gap-3 md:grid-cols-3" onSubmit={e=>{e.preventDefault();setError('');if(!save.isPending)save.mutate();}}>
  <fieldset className="contents" disabled={!canReceive||save.isPending||locked}>
   <label className="grid gap-1 text-sm">Item<NativeSelect required searchable aria-label="Item" value={draft.product} onChange={e=>setDraft(old=>({...old,product:e.target.value}))}><option value="">Choose item</option>{products.filter(row=>!row.tracked).map(row=><option key={row.product_id} value={row.product_id}>{row.name} · {row.sku}</option>)}{locked&&draft.product&&!products.some(row=>String(row.product_id)===draft.product)&&<option value={draft.product}>Pending item #{draft.product}</option>}</NativeSelect></label>
   <label className="grid gap-1 text-sm">Warehouse<NativeSelect required searchable aria-label="Warehouse" value={draft.warehouse} onChange={e=>setDraft(old=>({...old,warehouse:e.target.value}))}><option value="">Choose warehouse</option>{warehouses.map(row=><option key={row.id} value={row.id}>{row.warehouse_name}</option>)}</NativeSelect></label>
   {field('Date','date','date')}{field('Quantity','quantity')}{field('Rate','rate')}{field('Reference','reference')}{field('Notes','notes')}
  </fieldset>
  {locked&&<p role="status" className="text-sm md:col-span-3">A receipt is pending. Retry the same receipt to recover its result.</p>}
  {error&&<p role="alert" className="text-sm text-destructive md:col-span-3">{error}</p>}{completed&&<p role="status" className="text-sm md:col-span-3">{completed}</p>}
  <Button data-save-action type="submit" disabled={!canReceive||save.isPending||(recovery.pending&&!valid)}>{save.isPending?'Posting…':locked?'Retry same receipt':'Post movement'}</Button>
 </CompactForm></CardContent></Card>}
 <Card><CardHeader><CardTitle className="text-base">{mode==='receipt'?'Goods receipts':mode==='warehouse'?'Warehouse Stock':'Stock Summary'}</CardTitle></CardHeader><CardContent className="space-y-3">
  {mode==='receipt'?<>{history.isPending&&<p role="status">Loading goods receipts…</p>}{history.isError&&<p role="alert">{catalogError(history.error)} <Button variant="outline" onClick={()=>void history.refetch()}>Retry goods receipts</Button></p>}{renderTable(history.data?.pages.flatMap(page=>page.items)||[],['number','receipt_date','product_id','warehouse_id','quantity','unit_cost','currency','reference_number'])}{history.hasNextPage&&<Button variant="outline" onClick={()=>void history.fetchNextPage()}>More receipts</Button>}</>:renderTable(mode==='warehouse'?warehouseRows:stockRows,mode==='warehouse'?['warehouse_name','sku','item_name','quantity']:['sku','item_name','current_quantity'])}
  {stock.hasNextPage&&<Button variant="outline" onClick={()=>void stock.fetchNextPage()}>More items</Button>}
 </CardContent></Card></div>;
}
