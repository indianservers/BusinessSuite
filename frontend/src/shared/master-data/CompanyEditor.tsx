import BranchAvailability, { type BranchAvailabilityValue } from "@/shared/BranchAvailability";
import {useEffect,useRef,useState} from 'react';
import {useQuery,useQueryClient} from '@tanstack/react-query';
import {Building2,Plus,Trash2} from 'lucide-react';
import {api} from '@/services/api';
import {Button} from '@/components/ui/button';
import {Input} from '@/components/ui/input';
import {NativeSelect} from '@/components/ui/native-select';
import {Dialog,DialogContent,DialogHeader,DialogTitle} from '@/components/ui/dialog';
import {PhoneInput} from '@/lib/validation/PhoneInput';
import {contract} from '@/lib/validation';
import {BusinessTypeSelect,CountrySelect,businessDefinitions,canonicalBusinessType,companyBasicsSchema,countryIso,normalizedWebsite,registrationError,bankCodeError} from '@/lib/validation/business';
import FinancialDataTab,{type FinancialData} from '@/apps/crm/FinancialDataTab';
import {dealError} from '@/apps/crm/deals/deal-utils';
import {masterScope,SharedNumberConfirmation,useDebounced,type Company,type MasterSource} from './CompanySelect';
import {CommunicationDraftEditor,primaryEntries,transportEntries,type CommunicationEntry} from './CommunicationEditor';

const tabs=['Basic details','Legal & tax','Contacts & addresses','Banking & other'];
type Props={source?:MasterSource;initial?:Company;seedName?:string;roles?:string[];recordLabel?:string;defaultEntityKind?:'Individual'|'Company';onClose:()=>void;onSaved:(company:Company,keepOpen?:boolean)=>void};
type Row=Record<string,string>;
const values=(record?:Company,seedName='')=>({name:record?.name||seedName,email:record?.email||'',phone:record?.phone||'',phone_country_code:record?.phone_country_code||'+91',website:record?.website||'',industry:record?.industry||'',country:countryIso(record?.country),legalName:record?.legalName||record?.name||seedName,tradeName:record?.tradeName||'',businessType:canonicalBusinessType(record?.businessType),notes:record?.notes||'',status:record?.status||'Active',vendorClassification:record?.vendorClassification||'',paymentTerms:record?.paymentTerms||'Due on receipt'});

export function CompanyQuickCreate({source='crm',initial,seedName='',roles=['Prospect'],recordLabel='company',defaultEntityKind='Company',onClose,onSaved}:Props){
  const qc=useQueryClient(),formRef=useRef<HTMLFormElement>(null),nameRef=useRef<HTMLInputElement>(null);
  const [record,setRecord]=useState(initial),[form,setForm]=useState(()=>values(initial,seedName));
  const [availability,setAvailability]=useState<BranchAvailabilityValue>();
  const [entityKind,setEntityKind]=useState(initial?.entityKind||defaultEntityKind);
  const [tab,setTab]=useState(0),[busy,setBusy]=useState(false),[error,setError]=useState(''),[notice,setNotice]=useState('');
  const [businessRoles,setBusinessRoles]=useState(()=>[...new Set(initial?.roles||roles)]);
  const [addresses,setAddresses]=useState<Row[]>(initial?.addresses||[]),[tax,setTax]=useState<Row[]>(initial?.taxRegistrations||[]);
  const [channels,setChannels]=useState<CommunicationEntry[]>(),[financial,setFinancial]=useState<FinancialData>();
  const [primaryId,setPrimaryId]=useState(String(initial?.primaryContactId||'')),[newContact,setNewContact]=useState(false);
  const [person,setPerson]=useState({name:'',email:''}),[contactSearch,setContactSearch]=useState('');
  const [confirmed,setConfirmed]=useState(false),[reason,setReason]=useState(''),[matches,setMatches]=useState<{id:number;kind:string;name?:string}[]>([]);
  const defaultsApplied=useRef(!!initial),legalEdited=useRef(!!initial?.legalName),countryEdited=useRef(!!initial),phoneCodeEdited=useRef(!!initial);
  const search=useDebounced(form.name),contactTerm=useDebounced(contactSearch);
  const defaults=useQuery<{country:string;currency:string}>({queryKey:['master-form-options',masterScope(),source],queryFn:async()=>(await api.get('/master-data/form-options',{params:{source},progress:false})).data,staleTime:60000});
  useEffect(()=>{if(defaults.data&&!defaultsApplied.current){defaultsApplied.current=true;const country=countryIso(defaults.data.country);setForm(f=>({...f,country:countryEdited.current?f.country:country,phone_country_code:phoneCodeEdited.current?f.phone_country_code:contract.countries.find(c=>c.iso===country)?.code||'+91'}));}},[defaults.data]);
  const suggestions=useQuery<{items:Company[]}>({queryKey:['master-company-suggestions',masterScope(),source,search],enabled:search.length>1&&!record,queryFn:async()=>(await api.get('/master-data/companies',{params:{source,search,per_page:5},progress:false})).data,staleTime:15000});
  const people=useQuery<{items:{id:number;name:string;email?:string}[]}>({queryKey:['master-contact-picker',masterScope(),source,contactTerm],enabled:tab===2,queryFn:async()=>(await api.get('/master-data/contacts',{params:{source,search:contactTerm,per_page:30},progress:false})).data,retry:false,staleTime:30000});
  const patch=(key:keyof typeof form,value:string)=>setForm(f=>({...f,[key]:value,...(key==='name'&&!legalEdited.current?{legalName:value}:{})}));
  async function selectExisting(id:number){setBusy(true);setError('');try{const {data}=await api.get<Company>(`/master-data/companies/${id}`,{params:{source}});setRecord(data);setAvailability(undefined);setForm(values(data));setEntityKind(data.entityKind||'Company');setBusinessRoles([...new Set([...(data.roles||[]),...(recordLabel==='company'?[]:roles)])]);setAddresses(data.addresses||[]);setTax(data.taxRegistrations||[]);setPrimaryId(String(data.primaryContactId||''));setChannels(undefined);setFinancial(undefined);setConfirmed(false);setNotice(`Using existing ${data.name}. Saving adds this relationship to the same company.`);}catch(e){setError(dealError(e));}finally{setBusy(false);}}
  async function save(keepOpen=false){
    setError('');const valid=companyBasicsSchema.safeParse(form);
    if(!valid.success){setTab(0);setError(valid.error.issues[0].message);return;}
    for(const item of tax){const message=registrationError(item.type||'Other',item.number||'',countryIso(item.country||form.country));if(message){setTab(1);setError(message);return;}}
    const financialValues=financial?{...financial,bankAccounts:financial.bankAccounts.filter(b=>[b.holderName,b.bankName,b.accountNumber,b.ifsc,b.micr,b.branch,b.iban,b.bic].some(v=>v?.trim())),upiIds:financial.upiIds.filter(u=>[u.upiId,u.mobile,u.label].some(v=>v?.trim()))}:undefined;
    for(const bank of financialValues?.bankAccounts||[]){for(const [kind,value] of [['IFSC',bank.ifsc],['IBAN',bank.iban||''],['BIC',bank.bic||'']]){const message=bankCodeError(kind,value,bank.country);if(message){setTab(3);setError(message);return;}}if(!bank.accountNumber){setTab(3);setError('Bank account number is required when adding a bank account');return;}}
    setBusy(true);
    try{
      const channelValues=channels?.map(c=>c.primary&&c.kind==='phone'?{...c,value:form.phone,countryCode:form.phone_country_code}:c.primary&&c.kind==='email'?{...c,value:form.email}:c);
      const body={...form,branch_availability:availability,name:form.name.trim(),website:normalizedWebsite(form.website)||null,entityKind,version:record?.version,roles:businessRoles,tags:record?.tags||[],addresses,taxRegistrations:tax,primaryContactId:primaryId?Number(primaryId):null,newPrimaryContact:newContact?{...person,email:person.email||null}:undefined,confirmShared:confirmed,sharedReason:reason||undefined,financialData:financialValues,communicationChannels:channelValues?transportEntries(channelValues):undefined};
      const {data}=record?await api.patch<Company>(`/master-data/companies/${record.id}`,body,{params:{source}}):await api.post<Company>('/master-data/companies',body,{params:{source}});
      await Promise.all(['master-companies','master-company','master-channels','universal-contacts','contact-financial','crm','srm','master-company-suggestions'].map(key=>qc.invalidateQueries({queryKey:[key]})));
      onSaved(data,keepOpen);
      if(keepOpen){setAvailability(undefined);setRecord(undefined);setForm({...values(),country:countryIso(defaults.data?.country),phone_country_code:contract.countries.find(c=>c.iso===countryIso(defaults.data?.country))?.code||'+91'});countryEdited.current=false;phoneCodeEdited.current=false;setEntityKind(defaultEntityKind);setBusinessRoles(roles);setTax([]);setAddresses([]);setChannels(undefined);setFinancial(undefined);setPrimaryId('');setNewContact(false);setPerson({name:'',email:''});setConfirmed(false);setMatches([]);setTab(0);legalEdited.current=false;defaultsApplied.current=false;setNotice(`${recordLabel} saved. Add another.`);setTimeout(()=>nameRef.current?.focus(),0);}
    }catch(e){setError(dealError(e));const detail=(e as {response?:{data?:{detail?:{matches?:typeof matches}}}}).response?.data?.detail;setMatches(detail?.matches||[]);}finally{setBusy(false);}
  }
  const vendor=businessRoles.some(r=>r==='Vendor'||r==='Supplier');
  return <Dialog open onOpenChange={open=>{if(!open&&!busy)onClose();}}><DialogContent className="md-quick-dialog md-company-editor" overlayClassName="md-suboverlay"><DialogHeader className="md-editor-header"><DialogTitle><Building2 size={18}/>{initial?'Edit':'Create'} {recordLabel}</DialogTitle><p>Basic details are enough to save. Add optional information when available.</p></DialogHeader>
    <nav className="md-editor-tabs" role="tablist" aria-label="Company form sections">{tabs.map((title,i)=><button key={title} type="button" role="tab" id={`company-tab-${i}`} aria-controls={`company-panel-${i}`} aria-selected={tab===i} tabIndex={tab===i?0:-1} onClick={()=>setTab(i)} onKeyDown={e=>{if(e.key==='ArrowRight'||e.key==='ArrowLeft'){e.preventDefault();const next=(i+(e.key==='ArrowRight'?1:3))%4;setTab(next);document.getElementById(`company-tab-${next}`)?.focus();}}}>{title}</button>)}</nav>
    <form ref={formRef} onSubmit={e=>{e.preventDefault();void save();}} onKeyDown={e=>{if((e.ctrlKey||e.metaKey)&&e.key==='Enter'){e.preventDefault();void save();}}} onInvalidCapture={e=>{e.preventDefault();const input=e.target as HTMLInputElement;const index=Number(input.closest<HTMLElement>('[data-company-section]')?.dataset.companySection||0);setTab(index);setError(input.validationMessage);setTimeout(()=>input.focus(),0);}}>
      <fieldset disabled={busy} className="md-editor-body">
        <section role="tabpanel" id="company-panel-0" aria-labelledby="company-tab-0" data-company-section="0" hidden={tab!==0}>
          <div className="md-form-grid">
            <div className="md-span"></div>
            {recordLabel!=='company'&&<label className="md-span">Customer / vendor type<NativeSelect aria-label="Customer / vendor type" value={entityKind} onChange={e=>setEntityKind(e.target.value as typeof entityKind)}><option value="Company">Business / company</option><option value="Individual">Individual</option></NativeSelect></label>}
            <label className="md-span">{entityKind==='Individual'?'Full name':'Company name'} *<Input ref={nameRef} autoFocus required maxLength={180} value={form.name} onChange={e=>patch('name',e.target.value)}/></label>
            {!record&&!!suggestions.data?.items.length&&<div className="md-span md-suggestions" role="region" aria-label="Existing company matches"><strong>Possible matches — reuse an existing company</strong>{suggestions.data.items.map(item=><button type="button" key={item.id} onClick={()=>void selectExisting(item.id)}><span>{item.name}<small>{[item.phone,item.email,item.gstNumber,item.country].filter(Boolean).join(' · ')}</small></span><span>{vendor?'Use existing & add Vendor':'Use existing'}</span></button>)}<button type="button" onClick={()=>{setConfirmed(true);setNotice('Creating a separate record. Existing matches are retained.');}}><Plus size={13}/> Create new company with these details</button></div>}
            <label>Phone<PhoneInput label="Company phone" value={form.phone} countryCode={form.phone_country_code} onChange={v=>patch('phone',v)} onCountryCodeChange={v=>{phoneCodeEdited.current=true;patch('phone_country_code',v);}}/></label>
            <label>Email<Input type="email" maxLength={150} value={form.email} onChange={e=>patch('email',e.target.value)}/></label>
            <label>Country<CountrySelect value={form.country} onChange={v=>{countryEdited.current=true;patch('country',v);}}/></label>
            <label>Business type<BusinessTypeSelect country={form.country} value={form.businessType} onChange={v=>patch('businessType',v)}/></label>
            <label>Website<Input placeholder="example.com" value={form.website} maxLength={200} onChange={e=>patch('website',e.target.value)}/></label>
            <label>Industry<Input value={form.industry} maxLength={120} onChange={e=>patch('industry',e.target.value)}/></label>
            {vendor&&<label>Vendor classification<NativeSelect searchable aria-label="Vendor classification" value={form.vendorClassification} onChange={e=>patch('vendorClassification',e.target.value)}><option value="">Not specified</option>{form.vendorClassification&&!businessDefinitions.vendorClassifications.includes(form.vendorClassification)&&<option value={form.vendorClassification}>{form.vendorClassification} (saved)</option>}{businessDefinitions.vendorClassifications.map(c=><option key={c}>{c}</option>)}</NativeSelect></label>}
          </div>
        </section>
        <section role="tabpanel" id="company-panel-1" aria-labelledby="company-tab-1" data-company-section="1" hidden={tab!==1}><div className="md-form-grid">
          <label>Legal name<Input value={form.legalName} maxLength={180} onChange={e=>{legalEdited.current=true;patch('legalName',e.target.value);}}/></label><label>Trade name<Input value={form.tradeName} maxLength={180} onChange={e=>patch('tradeName',e.target.value)}/></label>
          <div className="md-span"><StructuredRows kind="tax" value={tax} onChange={setTax} country={form.country}/><p className="md-muted">Format and checksum checks do not verify government registration.</p></div>
        </div></section>
        <section role="tabpanel" id="company-panel-2" aria-labelledby="company-tab-2" data-company-section="2" hidden={tab!==2}>
          <CommunicationDraftEditor ownerId={record?.id} kind="company" source={source} draft={channels!==undefined} value={channels||primaryEntries(form.email,form.phone,form.phone_country_code)} onChange={entries=>{setChannels(entries);const phone=entries.find(x=>x.kind==='phone'&&x.primary),email=entries.find(x=>x.kind==='email'&&x.primary);setForm(f=>({...f,phone:phone?.value||'',phone_country_code:phone?.countryCode||f.phone_country_code,email:email?.value||''}));}}/>
          <div className="md-form-grid"><label className="md-span">Primary contact (optional)<Input aria-label="Search contact persons" placeholder="Search contact persons" value={contactSearch} onChange={e=>setContactSearch(e.target.value)}/><NativeSelect aria-label="Primary contact" value={primaryId} onChange={e=>setPrimaryId(e.target.value)}><option value="">No primary contact</option>{primaryId&&!people.data?.items.some(c=>String(c.id)===primaryId)&&<option value={primaryId}>Saved contact #{primaryId}</option>}{people.data?.items.map(c=><option key={c.id} value={c.id}>{c.name}{c.email?` · ${c.email}`:''}</option>)}</NativeSelect></label>
          <label className="md-check md-span"><input type="checkbox" checked={newContact} onChange={e=>setNewContact(e.target.checked)}/> Create a contact person here</label>{newContact&&<><label>Contact name *<Input required value={person.name} onChange={e=>setPerson(p=>({...p,name:e.target.value}))}/></label><label>Contact email<Input type="email" value={person.email} onChange={e=>setPerson(p=>({...p,email:e.target.value}))}/></label></>}
          <div className="md-span"><StructuredRows kind="address" value={addresses} onChange={setAddresses} country={form.country}/></div></div>
        </section>
        <section role="tabpanel" id="company-panel-3" aria-labelledby="company-tab-3" data-company-section="3" hidden={tab!==3}>
          <details className="mb-4"><summary>Branch availability</summary><BranchAvailability key={record?.id ?? "new"} value={availability} editing={!!record} resource={record ? {table:"crm_companies",id:record.id,source} : undefined} onChange={setAvailability}/></details>
          <FinancialDataTab contactId={record?.financialContactId} value={financial} onChange={setFinancial} defaultCountry={form.country} defaultCurrency={defaults.data?.currency||'INR'}/>
          <div className="md-form-grid"><label>Payment terms<NativeSelect aria-label="Payment terms" value={/^Net (?!7$|15$|30$|45$|60$|90$)\d+$/.test(form.paymentTerms)?'custom':form.paymentTerms} onChange={e=>patch('paymentTerms',e.target.value==='custom'?'Net 1':e.target.value)}>{['Due on receipt','Advance','Net 7','Net 15','Net 30','Net 45','Net 60','Net 90'].map(t=><option key={t}>{t}</option>)}<option value="custom">Custom days</option></NativeSelect></label>{/^Net (?!7$|15$|30$|45$|60$|90$)\d+$/.test(form.paymentTerms)&&<label>Payment days<Input type="number" min={1} max={999} value={form.paymentTerms.slice(4)} onChange={e=>patch('paymentTerms',`Net ${e.target.value}`)}/></label>}
          <label>Status<NativeSelect value={form.status} onChange={e=>patch('status',e.target.value)}>{['Active','Inactive','Blocked'].map(s=><option key={s}>{s}</option>)}</NativeSelect></label>
          <fieldset className="md-span"><legend>Business relationships</legend><div className="md-role-options">{['Prospect','Customer','Vendor','Supplier','Partner','Other'].map(role=><label className="md-check" key={role}><input type="checkbox" checked={businessRoles.includes(role)} onChange={e=>setBusinessRoles(r=>e.target.checked?[...new Set([...r,role])]:r.filter(x=>x!==role))}/>{role}</label>)}</div><p className="md-muted">Existing relationships are retained. Use relationship management for removal.</p></fieldset>
          <label className="md-span">Internal notes<textarea maxLength={10000} rows={3} value={form.notes} onChange={e=>patch('notes',e.target.value)}/></label></div>
        </section>
        {(!record||form.phone!==(record.phone||'')||form.email!==(record.email||'')||form.phone_country_code!==(record.phone_country_code||'+91'))&&<SharedNumberConfirmation source={source} phone={form.phone} countryCode={form.phone_country_code} email={form.email} confirmed={confirmed} reason={reason} onChange={(checked,next)=>{setConfirmed(checked);setReason(next);}} onSelect={match=>{if(match.kind==='company')void selectExisting(match.id);else{setPrimaryId(String(match.id));setTab(2);}}}/>}
        {!!matches.length&&<div className="md-warning">{matches.filter(m=>m.kind==='company').map(m=><button type="button" key={m.id} onClick={()=>void selectExisting(m.id)}>Use existing {m.name||'company'}</button>)}</div>}
        {error&&<p className="md-error" role="alert">{error}</p>}{notice&&<p className="md-message" role="status">{notice}</p>}
      </fieldset>
      <footer className="md-dialog-footer"><Button variant="outline" type="button" disabled={busy} onClick={onClose}>Cancel</Button>{!initial&&<Button variant="outline" type="button" disabled={busy||!form.name.trim()} onClick={()=>void save(true)}>Save & new</Button>}<Button type="submit" disabled={busy||!form.name.trim()}>{busy?'Saving…':`Save ${recordLabel}`}</Button></footer>
    </form>
  </DialogContent></Dialog>;
}

function StructuredRows({kind,value,onChange,country}:{kind:'tax'|'address';value:Row[];onChange:(rows:Row[])=>void;country:string}){
  const change=(index:number,key:string,next:string)=>onChange(value.map((r,i)=>i===index?{...r,[key]:next}:r));
  const types=kind==='address'?['Billing','Shipping','Office','Other']:country==='IN'?['GSTIN','PAN','CIN','LLPIN','Other']:country==='AE'?['TRN','Other']:['Other'];
  return <div className="md-structured"><header><strong>{kind==='tax'?'Tax registrations':'Addresses'}</strong><Button type="button" size="sm" variant="outline" onClick={()=>onChange([...value,{type:types[0],country}])}><Plus size={13}/>Add {kind==='tax'?'registration':'address'}</Button></header>{value.map((row,i)=><div className="md-form-grid md-structured-row" key={i}><label>Type<NativeSelect value={row.type||types[0]} onChange={e=>change(i,'type',e.target.value)}>{[...new Set([row.type,...types])].filter(Boolean).map(t=><option key={t}>{t}</option>)}</NativeSelect></label><label>Country<CountrySelect label={`${kind} country ${i+1}`} value={countryIso(row.country||country)} onChange={v=>change(i,'country',v)}/></label>{(kind==='tax'?[['number','Registration number']]:[['line1','Address'],['city','City'],['state','State / region'],['postalCode','Postal code']]).map(([key,label])=><label key={key}>{label}<Input aria-label={`${label} ${i+1}`} maxLength={key==='line1'?500:100} value={row[key]||''} onChange={e=>change(i,key,key==='number'?e.target.value.toUpperCase():e.target.value)}/></label>)}<Button type="button" variant="ghost" size="sm" aria-label={`Remove ${kind} ${i+1}`} onClick={()=>onChange(value.filter((_,n)=>n!==i))}><Trash2 size={13}/>Remove</Button></div>)}</div>;
}
