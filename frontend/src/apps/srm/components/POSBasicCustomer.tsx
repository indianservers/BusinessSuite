import { isAxiosError } from 'axios';
import POSCustomerCustomFields, { type POSCustomerSchema, type POSCustomValue } from './POSCustomerCustomFields';
import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Dialog,DialogContent,DialogHeader,DialogTitle } from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { NativeSelect } from '@/components/ui/native-select';
import { api } from '@/services/api';
import { dealError } from '@/apps/crm/deals/deal-utils';
import { useRecordScope } from '@/lib/record-scope';
import { useRecordScopeOwner } from '@/hooks/use-record-scope-owner';
import type { PosCustomerRecord } from './QuickAddCustomer';
export type POSFeatures={appointments_schedule:boolean;customers_register:boolean;registration_unavailable_reason?:string|null;held_bills:boolean;follow_ups:boolean;advanced_customer:boolean;countries:{code:string;name:string}[]};
export function POSQuickAddCustomer({features,patient=false,onClose,onCreated}:{features:POSFeatures;patient?:boolean;onClose:()=>void;onCreated:(record:PosCustomerRecord)=>void}) {
  const owns=useRecordScopeOwner(),scope=useRecordScope();
  const schema=useQuery({queryKey:['srm','pos-customer-schema',scope],queryFn:()=>api.get<POSCustomerSchema>('/srm/pos/customer-schema',{recordCache:false}).then(response=>response.data),retry:false,refetchOnWindowFocus:false});
  const [customValues,setCustomValues]=useState<Record<string,POSCustomValue>>({}),[needsReview,setNeedsReview]=useState(false);
  const [form,setForm]=useState({name:'',email:'',phone:'',phone_country_code:'',address:'',city:'',state:'',country:''});
  const [busy,setBusy]=useState(false),[error,setError]=useState('');
  return <Dialog open onOpenChange={open=>{if(!open&&!busy)onClose();}}><DialogContent className="max-h-[90dvh] overflow-y-auto"><DialogHeader><DialogTitle>{patient?'Register patient':'Quick add customer'}</DialogTitle></DialogHeader><form className="space-y-3" onSubmit={async event=>{event.preventDefault();event.stopPropagation();if(busy||!features.customers_register||!schema.data?.registration_available||schema.isFetching||needsReview)return;setBusy(true);setError('');try{const {data}=await api.post<PosCustomerRecord>('/srm/pos/customers',{...form,email:form.email||null,phone:form.phone||null,phone_country_code:form.phone_country_code||null,schema_fingerprint:schema.data.schema_fingerprint,custom_fields:schema.data.fields.filter(field=>Object.prototype.hasOwnProperty.call(customValues,String(field.id))).map(field=>({field_id:field.id,value:customValues[String(field.id)]}))});if(owns())onCreated(data);}catch(caught){if(owns()){setError(dealError(caught));if(isAxiosError(caught)&&caught.response?.status===409)setNeedsReview(true);}}finally{if(owns())setBusy(false);}}}>
    <p className="text-sm text-muted-foreground">Use the customer's actual billing details. These are saved to the shared customer account.</p>
    {(['name','address','city','state','email','phone_country_code','phone'] as const).map(key=><label className="block space-y-1 text-sm" key={key}>{({name:patient?'Patient name':'Customer name',address:'Billing address',city:'City',state:'State / region',email:'Email',phone_country_code:'Phone calling code',phone:'Phone number'})[key]}<Input aria-label={`POS customer ${key}`} required={['name','address','state'].includes(key)} type={key==='email'?'email':'text'} maxLength={key==='address'?2000:key==='name'?180:key==='phone'?15:150} value={form[key]} disabled={busy} onChange={event=>setForm(current=>({...current,[key]:event.target.value}))}/></label>)}
    <label className="block space-y-1 text-sm">Billing country<NativeSelect aria-label="POS customer country" required value={form.country} disabled={busy} onChange={event=>setForm(current=>({...current,country:event.target.value}))}><option value="">Select billing country</option>{features.countries.map(country=><option key={country.code} value={country.code}>{country.name}</option>)}</NativeSelect></label>
    {schema.isPending&&<p role="status">Loading customer field requirements…</p>}
    {schema.isError&&<p role="alert">{dealError(schema.error)}</p>}
    {schema.data&&!schema.data.registration_available&&<p role="alert">{schema.data.unavailable_reason}</p>}
    {schema.data&&<POSCustomerCustomFields fields={schema.data.fields} values={customValues} disabled={busy||schema.isFetching||needsReview} onChange={(key,value)=>setCustomValues(current=>({...current,[key]:value}))}/>}
    {(schema.isError||needsReview)&&<Button type="button" variant="outline" disabled={busy||schema.isFetching} onClick={async()=>{const refreshed=await schema.refetch();if(owns()&&refreshed.isSuccess){setNeedsReview(false);setError('Review the refreshed customer fields before saving.');}}}>Reload and review customer fields</Button>}
    {error&&<p role="alert" className="text-destructive">{error}</p>}<div className="flex justify-end gap-2"><Button type="button" variant="outline" disabled={busy} onClick={onClose}>Cancel</Button><Button disabled={busy||!features.customers_register||schema.isFetching||!schema.data?.registration_available||needsReview}>{busy?'Saving…':patient?'Save patient':'Save customer'}</Button></div>
  </form></DialogContent></Dialog>;
}
export function POSCustomerProfile({id,onClose}:{id:number;onClose:()=>void}) {
  const scope=useRecordScope();
  const query=useQuery({queryKey:['srm','pos-basic-customer',scope,id],queryFn:()=>api.get<PosCustomerRecord&{city:string;state:string;country:string}>(`/srm/pos/customers/${id}`).then(response=>response.data),retry:false});
  return <Dialog open onOpenChange={open=>{if(!open)onClose();}}><DialogContent><DialogHeader><DialogTitle>Customer profile</DialogTitle></DialogHeader>{query.isPending?<p>Loading customer…</p>:query.isError?<p role="alert">{dealError(query.error)}</p>:<dl className="space-y-2">{(['name','phone','email','address','city','state','country'] as const).map(key=><div key={key}><dt className="text-sm text-muted-foreground">{key}</dt><dd>{query.data[key]||'—'}</dd></div>)}</dl>}<Button variant="outline" onClick={onClose}>Close</Button></DialogContent></Dialog>;
}
