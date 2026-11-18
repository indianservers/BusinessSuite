import {schedulingPhone} from './scheduling-format';
import {ChevronDown} from 'lucide-react';
import SchedulingAvatar from './SchedulingAvatar';
import { useEffect, useRef, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { CompanyQuickCreate, masterScope, useDebounced, type Company } from '@/shared/master-data/CompanySelect';
import SmartRecordPicker from '@/shared/records/SmartRecordPicker';
import { api } from '@/services/api';
import { Button } from '@/components/ui/button';
import { useBusinessTerms } from '@/hooks/use-business-terms';

export default function PrebookingCustomer({ reference = false, value, onChange, onSelected }: { reference?: boolean; value: string; onChange: (value: string) => void; onSelected: (customer: Company) => void }) {
  const { term } = useBusinessTerms();
  const [changing, setChanging] = useState(false), [chosen, setChosen] = useState<Company>();
  const [search,setSearch]=useState(''),[page,setPage]=useState(1),[creating,setCreating]=useState(false);
  const needle=useDebounced(search);
  const list=useQuery({queryKey:['prebooking-customer-search',masterScope(),needle,page],enabled:!value||changing,retry:false,
    queryFn:({signal})=>api.get<{items:Company[];total:number;canCreate:boolean}>('/master-data/companies',{signal,params:{source:'srm',entity_kind:'all',search:needle,page,per_page:50}}).then(r=>r.data)});
  const query = useQuery({ queryKey: ['master-company', masterScope(), 'srm', value], enabled: !!value, retry: false,
    queryFn: ({ signal }) => api.get<Company>(`/master-data/companies/${value}`, { signal, params: { source: 'srm' }, recordCache: false }).then(r => r.data) });
  const customer = query.data || (String(chosen?.id) === value ? chosen : undefined);
  const selectedCallback=useRef(onSelected);selectedCallback.current=onSelected;
  useEffect(()=>{if(customer)selectedCallback.current(customer);},[customer]);
  if (!value || changing) return <div className="prebooking-customer-picker">{reference&&list.data?.canCreate&&<button type="button" className="reference-new-customer" onClick={()=>setCreating(true)}>+ New customer</button>}<SmartRecordPicker name={term('customer')} value={value} search={search} onSearch={v=>{setSearch(v);setPage(1);}}
    items={(list.data?.items || []).map(row=>({id:String(row.id),label:row.name,details:[{label:"Mobile",value:row.phone?schedulingPhone(row.phone,row.phone_country_code):"Not recorded"},{label:"Email",value:row.email||"Not recorded"},{label:"ID",value:String(row.id)}],description:[`${term('customer')} #${row.id}`,row.phone?`•••• ${row.phone.slice(-4)}`:row.email?`${row.email.slice(0,2)}•••@${row.email.split('@')[1] || ''}`:'No contact recorded'].join(' · '),searchText:[row.phone,row.email].join(' '),record:row}))}
    selected={customer?{id:String(customer.id),label:customer.name,record:customer}:undefined}
    onSelect={row=>{setChosen(row);onChange(String(row.id));onSelected(row);setChanging(false);setSearch('');}} onClear={()=>{onChange('');setChosen(undefined);}}
    loading={list.isFetching} error={list.isError?'Customer search could not load.':undefined} retry={()=>void list.refetch()} hasMore={!!list.data && page*50<list.data.total} loadMore={()=>setPage(p=>p+1)} onCreate={list.data?.canCreate?()=>setCreating(true):undefined}/>
    {creating && <CompanyQuickCreate source="srm" roles={['Customer']} recordLabel={term('customer')} seedName={search} onClose={()=>setCreating(false)} onSaved={row=>{setChosen(row);onChange(String(row.id));onSelected(row);setChanging(false);setCreating(false);setSearch('');}}/>}
    {changing && <Button type="button" variant="ghost" onClick={() => setChanging(false)}>Keep selected {term('customer').toLowerCase()}</Button>}</div>;
  return <section className="prebooking-person-card" aria-label={`Selected ${term('customer').toLowerCase()}`}>
    {reference&&list.data?.canCreate&&<button type="button" className="reference-new-customer" onClick={()=>{setChanging(true);setCreating(true);}}>+ New customer</button>}<SchedulingAvatar className="prebooking-initials" name={customer?.name || '?'} src={customer?.avatar_url}/>
    <div><strong>{customer?.name || (query.isPending ? 'Loading customer…' : 'Customer details unavailable')}</strong><small>Customer #{value}</small><small>{customer?.phone ? schedulingPhone(customer.phone,customer.phone_country_code) : customer?.email || 'No contact details recorded'}</small></div>
    <Button type="button" variant="outline" aria-label={`Change ${term('customer').toLowerCase()}`} onClick={() => { setChanging(true); requestAnimationFrame(() => document.querySelector<HTMLInputElement>('.prebooking-customer-picker [role=combobox]')?.focus()); }}>{reference?<ChevronDown size={18}/>:<>Change {term('customer').toLowerCase()}</>}</Button>
    {query.isError && <p role="alert">Customer details could not load. <Button type="button" variant="ghost" onClick={() => void query.refetch()}>Retry customer</Button></p>}
  </section>;
}
