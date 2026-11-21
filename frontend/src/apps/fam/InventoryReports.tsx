import {useMemo,useState} from 'react';
import {Link,useLocation,useSearchParams,useParams} from 'react-router-dom';
import {useQuery} from '@tanstack/react-query';
import {api} from '@/services/api';
import {useRecordScope} from '@/lib/record-scope';
import {useMobile} from '@/components/mobile/useMobile';
import {MobileSheet} from '@/components/mobile/MobilePrimitives';
import './inventory-master.css';
import {Button} from '@/components/ui/button';
import {Input} from '@/components/ui/input';
import {NativeSelect} from '@/components/ui/native-select';
import {Card,CardHeader,CardTitle,CardContent} from '@/components/ui/card';
import GridTable from '@/shared/data-grid/GridTable';
import {ResponsiveContainer,BarChart,Bar,XAxis,YAxis,Tooltip,Legend} from 'recharts';

const reports=[['overview','Overview'],['summary','Stock summary'],['ledger','Stock ledger'],['valuation','Valuation'],['purchases','Purchases'],['sales','Sales movement'],['reorder','Low stock'],['aging','Stock ageing'],['expiry','Expiry & batches'],['adjustments','Adjustments'],['transfers','Transfers'],['dead-stock','Dead stock'],['reconciliation','Reconciliation']] as const;
type Row=Record<string,string|number|boolean|null>;
type Result={items:Row[];total:number;page:number;per_page:number;as_of:string;source:string;warnings:string[];limitations?:string;total_products?:number;totals_by_currency?:Row[];trends?:Row[];supported?:boolean};
const labels=(key:string)=>key.replace(/_/g,' ').replace(/^./,letter=>letter.toUpperCase());
const columnsFor=(report:string)=>['ledger','purchases','sales','adjustments','transfers'].includes(report)?['movement_date','movement_number','movement_type','reference_number','sku','warehouse_name','opening_quantity','quantity_in','quantity_out','closing_quantity','rate','value','created_by','posted_by','notes','status']
:report==='reconciliation'?['issue_type','sku','item_name','expected_quantity','actual_quantity','quantity_difference','expected_value','actual_value','value_difference','investigation']
:report==='aging'?['sku','item_name','warehouse_name','receipt_date','remaining_quantity','age_days','age_bucket']
:report==='expiry'?['sku','item_name','batch_number','warehouse_id','manufacture_date','expiry_date','quantity','stock_value','days_until_expiry','status']
:report==='valuation'?['sku','item_name','warehouse_name','quantity','average_cost','stock_value','currency','valuation_method']
:report==='summary'?['sku','item_name','warehouse_name','unit','opening_quantity','purchases','purchase_returns','sales','sales_returns','transfers_in','transfers_out','adjustments_and_other','reserved_quantity','available_quantity','quantity','stock_value','currency']
:['sku','item_name','warehouse_name','quantity','reserved_quantity','available_quantity','stock_value','currency','reorder_level','last_sale_date'];
function errorMessage(error:unknown){return (error as {response?:{data?:{detail?:unknown}}})?.response?.data?.detail?.toString()||'Inventory report could not load.';}

/** The existing report route, using shared controls and tables with server pages. */
export default function InventoryReports({initialReport="overview",singleReport=false}:{initialReport?:string;singleReport?:boolean}){
 const mobile=useMobile();
 const location=useLocation(),scope=useRecordScope(),[params,setParams]=useSearchParams();
 const route=useParams();
 const fixedProduct=location.pathname.includes('/item-ledger/')?route.id:undefined;
 const source=location.pathname.startsWith('/srm')?'srm':'fam',report=singleReport?initialReport:params.get('report')||initialReport;
 const [hidden,setHidden]=useState<Record<string,boolean>>({}),[exporting,setExporting]=useState(false),[exportError,setExportError]=useState('');
 const [filtersOpen,setFiltersOpen]=useState(false);
 const useFilterSheet=mobile&&source==='fam';
 const endpoint=`/${source}/inventory/reports`;
 const request=useMemo(()=>Object.fromEntries([...params.entries(),['report',report],...(fixedProduct?[['product_id',fixedProduct]]:[]),...(source==='fam'?[['analysis','true']]:[])]),[params,report,source,fixedProduct]);
 const query=useQuery<Result>({queryKey:['inventory-analysis',scope,source,request],queryFn:({signal})=>api.get(endpoint,{params:request,signal,recordCache:false}).then(response=>response.data),retry:false});
 const data=query.data,columns=columnsFor(report).filter(column=>!hidden[report+':'+column]);
 const page=Number(params.get('page')||1),size=Number(params.get('per_page')||25);
 function change(values:Record<string,string>){const next=new URLSearchParams(params);Object.entries(values).forEach(([key,value])=>value?next.set(key,value):next.delete(key));if(!('page' in values))next.delete('page');if(values.report&&values.report!=='ledger')next.delete('movement_id');setParams(next);}
 async function download(format:'xlsx'|'pdf'){
  setExporting(true);setExportError('');try{const response=await api.get(endpoint,{params:{...request,export_format:format},responseType:'blob',recordCache:false});const url=URL.createObjectURL(response.data);const anchor=document.createElement('a');anchor.href=url;anchor.download=`inventory-${source}-${report}.${format}`;anchor.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}catch(error){const blob=(error as {response?:{data?:Blob}}).response?.data;try{setExportError(JSON.parse(await blob!.text()).detail);}catch{setExportError(errorMessage(error));}}finally{setExporting(false);}
 }
 function drill(row:Row){const next=new URLSearchParams(params);next.set('report','ledger');next.delete('page');next.delete('transaction_type');if(row.product_id)next.set('product_id',String(row.product_id));if(row.warehouse_id)next.set('warehouse_id',String(row.warehouse_id));return `/${source}/inventory/reports?${next}`;}
 function sourceDrill(row:Row){const next=new URLSearchParams(params);next.set('report','ledger');next.set('movement_id',String(row.movement_id));next.delete('page');return `/${source}/inventory/reports?${next}`;}
 const filterFields=[['start_date','From','date'],['end_date','To','date'],['search','Search','search'],['product_id','Product ID','number'],['warehouse_id','Warehouse ID','number'],['category','Category ID','text'],['transaction_type','Transaction type','text']].map(([key,label,type])=><label className="text-sm" key={key}>{label}<Input name={key} aria-label={label} type={type} min={type==='number'?1:undefined} readOnly={key==='product_id'&&!!fixedProduct} defaultValue={key==='product_id'&&fixedProduct?fixedProduct:params.get(key)||''} className="max-w-44"/></label>);
 const filterActions=<>
   <Button type="submit" size="sm">Apply filters</Button>
   <Button type="button" variant="outline" size="sm" onClick={()=>{setParams({report});setFiltersOpen(false);}}>Clear filters</Button>
 </>;
 const filterForm=<form className={useFilterSheet?"fam-report-filter-sheet":"flex flex-wrap items-end gap-3 mt-3 fam-inventory-report-filters"} aria-label="Inventory report filters" onSubmit={event=>{
   event.preventDefault();
   const fields=new FormData(event.currentTarget);
   change(Object.fromEntries([...fields.entries()].map(([key,value])=>[key,String(value)])));
   setFiltersOpen(false);
 }} key={params.toString()}>
   {useFilterSheet?<><div className="fam-report-filter-fields">{filterFields}</div><div className="fam-report-filter-actions">{filterActions}</div></>:<>{filterFields}{filterActions}</>}
 </form>;
 return <section className={source === "fam" ? "space-y-4 min-w-0 fam-inventory-report" : "space-y-4 min-w-0"} aria-label="Inventory report workspace">
  {mobile?<div className={useFilterSheet?"fam-report-mobile-controls":undefined}>
    {!singleReport&&<label className="block text-sm">Report<NativeSelect aria-label="Inventory report" value={report} onChange={event=>change({report:event.target.value,transaction_type:'',search:'',category:''})}>{reports.map(([key,label])=><option key={key} value={key}>{label}</option>)}</NativeSelect></label>}
    {useFilterSheet&&<><Button type="button" variant="outline" aria-haspopup="dialog" onClick={()=>setFiltersOpen(true)}>Report filters</Button><MobileSheet open={filtersOpen} onClose={()=>setFiltersOpen(false)} title="Report filters">{filterForm}</MobileSheet></>}
  </div>:!singleReport&&<nav className="flex flex-wrap gap-2" aria-label="Inventory reports">{reports.map(([key,label])=><Button key={key} size="sm" variant={report===key?'default':'outline'} aria-pressed={report===key} onClick={()=>change({report:key,transaction_type:'',search:key==='reconciliation'?'':params.get('search')||'',category:key==='reconciliation'?'':params.get('category')||''})}>{label}</Button>)}</nav>}
  <Card><CardHeader><CardTitle className="text-base">{reports.find(([key])=>key===report)?.[1]||'Inventory report'}</CardTitle></CardHeader><CardContent className="space-y-4">
   {!useFilterSheet&&<details open={!mobile}><summary className="text-sm font-medium">Report filters</summary>{filterForm}</details>}
   <div className="flex flex-wrap items-center gap-3 fam-inventory-report-tools"><label className="text-sm">Sort<NativeSelect aria-label="Sort inventory report" value={params.get('sort')||'item_name'} onChange={event=>change({sort:event.target.value})}>{['item_name','sku','quantity','stock_value'].map(key=><option key={key} value={key}>{labels(key)}</option>)}</NativeSelect></label><Button variant="outline" size="sm" onClick={()=>change({descending:params.get('descending')==='true'?'false':'true'})}>Reverse sort</Button><Button variant="outline" size="sm" disabled={query.isFetching} onClick={()=>void query.refetch()}>Refresh</Button><Button variant="outline" size="sm" disabled={exporting||!data||query.isError} onClick={()=>void download('xlsx')}>Export Excel</Button><Button variant="outline" size="sm" disabled={exporting||!data||query.isError} onClick={()=>void download('pdf')}>Export PDF</Button><Button variant="outline" size="sm" onClick={()=>window.print()}>Print</Button><details><summary>Columns</summary><div className="flex flex-wrap gap-3">{columnsFor(report).map(column=><label key={column}><input type="checkbox" checked={!hidden[report+':'+column]} onChange={event=>setHidden(current=>({...current,[report+':'+column]:!event.target.checked}))}/>{labels(column)}</label>)}</div></details></div>
   {query.isFetching&&<p role="status">Loading inventory report…</p>}{query.isError&&<p role="alert">{errorMessage(query.error)}</p>}{exportError&&<p role="alert">{exportError}</p>}
   {!query.isError&&data&&<><p className="text-sm text-muted-foreground">{source==='srm'?'Sales':'Finance'} stock ledger · As of {data.as_of} · Posted movements only · Costs exclude sales tax</p>{report==='sales'&&<p className="text-sm">These are stock costs and quantities. <Link className="underline" to={source==='srm'?'/srm/inventory/reports/gross-margin':'/fam/inventory/gross-margin'}>Gross margin from linked invoices (all dates)</Link>.</p>}
    {data.total_products!==undefined&&<p className="text-sm font-medium">Products with recorded movements: {data.total_products}</p>}
    {!!data.totals_by_currency?.length&&<div className="flex flex-wrap gap-6" aria-label="Inventory totals">{data.totals_by_currency.map((row,index)=><div key={index}><strong className="text-base">{row.currency||'Unknown currency'} {row.stock_value===null?'Value not available':Number(row.stock_value).toLocaleString(undefined,{minimumFractionDigits:2,maximumFractionDigits:2})}</strong><p className="text-sm">{row.quantity} base units · {row.positions} warehouse positions · {row.negative_positions} negative</p><Button size="sm" variant="link" onClick={()=>change({report:'valuation'})}>Inspect valuation</Button></div>)}</div>}
    {!!data.trends?.length&&<p className="text-sm text-muted-foreground">Latest 90 daily movement points. Quantities use each item's base unit; totals can combine different units.</p>}{!!data.trends?.length&&<div style={{height:240}} aria-label="Stock movement trend"><ResponsiveContainer width="100%" height="100%"><BarChart data={data.trends}><XAxis dataKey="movement_date"/><YAxis/><Tooltip/><Legend/><Bar dataKey="quantity_in" name="Quantity in" fill="hsl(var(--primary))" isAnimationActive={false} onClick={entry=>{const day=String(entry.payload?.movement_date||'');if(day)change({report:'ledger',start_date:day,end_date:day});}}/><Bar dataKey="quantity_out" name="Quantity out" fill="hsl(var(--muted-foreground))" isAnimationActive={false} onClick={entry=>{const day=String(entry.payload?.movement_date||'');if(day)change({report:'ledger',start_date:day,end_date:day});}}/></BarChart></ResponsiveContainer></div>}
    {data.supported===false&&<p role="status">This source does not support this report.</p>}{data.limitations&&<p className="text-sm">{data.limitations}</p>}
    <div className="overflow-x-auto fam-inventory-report-records" role={source === "fam" && mobile ? "region" : undefined} tabIndex={source === "fam" && mobile ? 0 : undefined} aria-label="Inventory report records"><GridTable gridId={`inventory-analysis-${source}-${report}`} variant="matrix" staticLayout><thead><tr>{columns.map(column=><th key={column} className="p-2 text-left text-xs whitespace-nowrap">{labels(column)}</th>)}<th className="p-2 text-left text-xs">Inspect</th></tr></thead><tbody>{data.items.map((row,index)=><tr key={String(row.id??index)}>{columns.map(column=><td key={column} className="p-2 text-sm whitespace-nowrap">{row[column]===null||row[column]===undefined?'Not available':String(row[column])}</td>)}<td className="p-2 text-sm">{row.product_id&&<Link className="underline" to={drill(row)}>Ledger</Link>}{row.source_url&&['ledger','purchases','sales','transfers','adjustments'].includes(report)&&<> · <Link className="underline" to={sourceDrill(row)}>Source record</Link></>}</td></tr>)}</tbody></GridTable></div>
    {!data.items.length&&<p>No matching records.</p>}<nav className="flex flex-wrap items-center gap-3" aria-label="Inventory report pagination"><Button variant="outline" size="sm" disabled={page<=1||query.isFetching} onClick={()=>change({page:String(page-1)})}>Previous page</Button><span className="text-sm">Page {page} · {data.total} records</span><Button variant="outline" size="sm" disabled={page*size>=data.total||query.isFetching} onClick={()=>change({page:String(page+1)})}>Next page</Button><NativeSelect aria-label="Report rows per page" value={String(size)} onChange={event=>change({per_page:event.target.value})}>{[25,50,100].map(value=><option key={value}>{value}</option>)}</NativeSelect></nav>
    <details><summary>Calculation basis and limitations</summary><ul className="list-disc pl-5 text-sm">{data.warnings.map((warning,index)=><li key={index}>{warning}</li>)}</ul></details>
   </>}
  </CardContent></Card>
 </section>;
}
