import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus, Trash2 } from "lucide-react";
import { api } from "@/services/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { NativeSelect } from "@/components/ui/native-select";
import { dealError } from "./deals/deal-utils";
import { masterScope } from "@/shared/master-data/CompanySelect";
import "./financial-data.css";

type BankAccount = {holderName: string; bankName: string; accountNumber: string; ifsc: string; micr: string; branch: string; primary: boolean};
type UpiAddress = {upiId: string; label: string; mobile: string; primary: boolean};
export type FinancialData = {gstNumber: string; bankAccounts: BankAccount[]; upiIds: UpiAddress[]; version: number};
const emptyData: FinancialData = {gstNumber: "", bankAccounts: [], upiIds: [], version: 0};
const root = "/crm/contact-directory";
async function loadFinancialData(contactId: number) {
  const {data} = await api.get<FinancialData & {canManage?: boolean; canVoid?: boolean}>(`${root}/${contactId}/financial-data`);
  if (!data || !Array.isArray(data.bankAccounts) || !Array.isArray(data.upiIds)) throw new Error("Financial data could not be loaded. Try again.");
  return data;
}


export default function FinancialDataTab({contactId, value, onChange, readOnly = false}: {contactId?: number; value?: FinancialData; onChange?: (data: FinancialData) => void; readOnly?: boolean}) {
  const profile = useQuery<FinancialData & {canManage?: boolean; canVoid?: boolean}>({queryKey: ["contact-financial", masterScope(), contactId], enabled: !!contactId, queryFn: () => loadFinancialData(contactId!), staleTime: 0});
  const {canManage: _canManage, canVoid: _canVoid, ...storedData} = profile.data || {...emptyData, canManage: false};
  const data = value || storedData;
  const change = (next: Partial<FinancialData>) => onChange?.({...data, ...next});
  const bank = (index: number, patch: Partial<BankAccount>) => change({bankAccounts: data.bankAccounts.map((x, i) => i === index ? {...x, ...patch} : x)});
  const upi = (index: number, patch: Partial<UpiAddress>) => change({upiIds: data.upiIds.map((x, i) => i === index ? {...x, ...patch} : x)});
  return <div className="crm-financial">
    <p className="text-sm text-muted-foreground">Optional financial data for customers, vendors and other business relationships.</p>
    {contactId && profile.isPending && <p role="status">Loading financial data…</p>}
    {profile.error && <p role="alert">{dealError(profile.error)} <Button type="button" variant="link" onClick={() => void profile.refetch()}>Retry</Button></p>}
    <fieldset disabled={readOnly || (!!contactId && !profile.data)}>
      <label>Company GST number<Input aria-label="Company GST number" maxLength={15} placeholder="e.g. 27ABCDE1234F1Z5" value={data.gstNumber} onChange={e => change({gstNumber: e.target.value.toUpperCase()})}/></label>
      <section><header><h3>Bank accounts</h3>{!readOnly && <Button type="button" variant="outline" size="sm" disabled={data.bankAccounts.length >= 20} onClick={() => change({bankAccounts: [...data.bankAccounts, {holderName: "", bankName: "", accountNumber: "", ifsc: "", micr: "", branch: "", primary: data.bankAccounts.length === 0}]})}><Plus size={14}/>Add bank account</Button>}</header>
        {!data.bankAccounts.length && <p className="text-sm text-muted-foreground">No bank accounts added.</p>}
        {data.bankAccounts.map((entry, index) => <div className="crm-financial-card" key={index}><header><strong>Bank account {index + 1}</strong>{!readOnly && <Button type="button" variant="ghost" size="icon" aria-label={`Remove bank account ${index+1}`} onClick={() => change({bankAccounts: data.bankAccounts.filter((_, i) => i !== index)})}><Trash2 size={15}/></Button>}</header><div className="crm-financial-grid">
          {([['holderName','Account holder'],['bankName','Bank name'],['accountNumber','Account number'],['ifsc','IFSC'],['micr','MICR'],['branch','Bank branch']] as const).map(([key, title]) => <label key={key}>{title}<Input aria-label={`${title} ${index+1}`} value={entry[key]} maxLength={key === 'holderName' ? 180 : key === 'ifsc' ? 11 : key === 'micr' ? 9 : key === 'accountNumber' ? 34 : 120} inputMode={key === 'micr' ? 'numeric' : undefined} onChange={e => bank(index, {[key]: key === 'ifsc' ? e.target.value.toUpperCase() : e.target.value})}/></label>)}
        </div><label className="crm-financial-check"><input type="checkbox" checked={entry.primary} onChange={e => change({bankAccounts: data.bankAccounts.map((x, i) => ({...x, primary: e.target.checked && i === index}))})}/>Primary bank account</label></div>)}
      </section>
      <section><header><h3>UPI details</h3>{!readOnly && <Button type="button" variant="outline" size="sm" disabled={data.upiIds.length >= 20} onClick={() => change({upiIds: [...data.upiIds, {upiId: "", label: "", mobile: "", primary: data.upiIds.length === 0}]})}><Plus size={14}/>Add UPI</Button>}</header>
        <p className="text-sm text-muted-foreground">Save UPI IDs and linked mobile numbers for future UPI collection requests. A mobile number alone does not confirm a UPI ID. No request is sent here.</p>
        {data.upiIds.map((entry, index) => <div className="crm-financial-card" key={index}><header><strong>UPI {index+1}</strong>{!readOnly && <Button type="button" variant="ghost" size="icon" aria-label={`Remove UPI ${index+1}`} onClick={() => change({upiIds: data.upiIds.filter((_, i) => i !== index)})}><Trash2 size={15}/></Button>}</header><div className="crm-financial-grid">
          <label>UPI ID<Input aria-label={`UPI ID ${index+1}`} placeholder="name@bank" maxLength={100} value={entry.upiId} onChange={e => upi(index, {upiId: e.target.value})}/></label>
          <label>Linked mobile number<Input type="tel" aria-label={`UPI mobile ${index+1}`} placeholder="+919876543210" maxLength={16} value={entry.mobile} onChange={e => upi(index, {mobile: e.target.value})}/></label>
          <label>Label<Input aria-label={`UPI label ${index+1}`} placeholder="Business / personal" maxLength={80} value={entry.label} onChange={e => upi(index, {label: e.target.value})}/></label>
        </div><label className="crm-financial-check"><input type="checkbox" checked={entry.primary} onChange={e => change({upiIds: data.upiIds.map((x, i) => ({...x, primary: e.target.checked && i === index}))})}/>Primary UPI ID</label></div>)}
      </section>
    </fieldset>
    {contactId ? <FinancialTransactions contactId={contactId} readOnly={readOnly} canVoid={profile.data?.canVoid !== false}/> : <p className="text-sm text-muted-foreground">Save the contact to start recording financial transactions.</p>}
  </div>;
}

type Transaction = {id: number; version?: number; status?: string; voidReason?: string; direction: string; amount: string; currency: string; transactionDate: string; method: string; reference: string; notes: string};
function FinancialTransactions({contactId, readOnly, canVoid}: {contactId: number; readOnly: boolean; canVoid: boolean}) {
  const qc = useQueryClient();
  const [page, setPage] = useState(1);
  const [adding, setAdding] = useState(false);
  const [editing, setEditing] = useState<Transaction | null>(null);
  const [voiding, setVoiding] = useState<Transaction | null>(null);
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [form, setForm] = useState({requestId: crypto.randomUUID(), direction: "received", amount: "", currency: "INR", transactionDate: new Date().toLocaleDateString('en-CA'), method: "UPI", reference: "", notes: ""});
  const query = useQuery<{items: Transaction[]; total: number}>({queryKey: ["contact-transactions", masterScope(), contactId, page], queryFn: async () => (await api.get(`${root}/${contactId}/financial-transactions`, {params: {page}})).data});
  const record = async () => {
    setBusy(true); setError("");
    try {if (editing) await api.patch(`${root}/${contactId}/financial-transactions/${editing.id}`, {...form, version: editing.version || 1, reason}); else await api.post(`${root}/${contactId}/financial-transactions`, form); setAdding(false); setEditing(null); setReason(""); setForm(f => ({...f, requestId: crypto.randomUUID(), amount: "", reference: "", notes: ""})); await qc.invalidateQueries({queryKey: ["contact-transactions"]});}
    catch (e) {setError(dealError(e));} finally {setBusy(false);}
  };
  return <section><header><h3>Financial transactions</h3>{!readOnly && <Button type="button" variant="outline" size="sm" onClick={() => {setEditing(null); setReason(""); setError(""); setForm(f => ({...f, requestId: crypto.randomUUID(), amount: "", reference: "", notes: ""})); setAdding(true);}}>Record transaction</Button>}</header><p className="text-sm text-muted-foreground">Record money received or paid. These records do not send money or post entries to the accounting ledger.</p>
    {adding && <div className="crm-financial-card" onKeyDown={event => {if (event.key === "Enter" && event.target instanceof HTMLInputElement) event.preventDefault();}}><div className="crm-financial-grid">
      <label>Direction<NativeSelect aria-label="Transaction direction" value={form.direction} onChange={e => setForm({...form, direction: e.target.value})}><option value="received">Money received</option><option value="paid">Money paid</option></NativeSelect></label>
      <label>Amount<Input aria-label="Transaction amount" type="number" min="0.01" step="0.01" value={form.amount} onChange={e => setForm({...form, amount: e.target.value})}/></label>
      <label>Currency<Input aria-label="Transaction currency" maxLength={3} value={form.currency} onChange={e => setForm({...form, currency: e.target.value.toUpperCase()})}/></label>
      <label>Date<Input aria-label="Transaction date" type="date" value={form.transactionDate} onChange={e => setForm({...form, transactionDate: e.target.value})}/></label>
      <label>Payment method<NativeSelect aria-label="Transaction method" value={form.method} onChange={e => setForm({...form, method: e.target.value})}>{['UPI','Bank transfer','Cash','Cheque','Card','Other'].map(x => <option key={x}>{x}</option>)}</NativeSelect></label>
      <label>Reference / UTR<Input aria-label="Transaction reference" maxLength={120} value={form.reference} onChange={e => setForm({...form, reference: e.target.value})}/></label>
      <label>Notes<Input aria-label="Transaction notes" maxLength={2000} value={form.notes} onChange={e => setForm({...form, notes: e.target.value})}/></label>
    </div>{editing && <label>Reason for correction<Input aria-label="Transaction correction reason" maxLength={500} value={reason} onChange={e => setReason(e.target.value)}/></label>}{error && <p role="alert" className="text-destructive">{error}</p>}<div className="flex justify-end gap-2"><Button type="button" variant="outline" disabled={busy} onClick={() => setAdding(false)}>Cancel transaction</Button><Button type="button" disabled={busy || !(Number(form.amount) > 0) || !form.transactionDate || (!!editing && reason.trim().length < 3)} onClick={() => void record()}>{busy ? "Recording…" : editing ? "Save correction" : "Save transaction"}</Button></div></div>}
    {query.isPending && <p role="status">Loading transactions…</p>}{query.error && <p role="alert">{dealError(query.error)}</p>}
    {query.data?.items.length === 0 && <p className="text-sm text-muted-foreground">No financial transactions recorded.</p>}
    {query.data?.items.map(row => <article className="crm-financial-card" key={row.id}><header><strong>{row.direction === 'received' ? 'Received' : 'Paid'} {row.currency} {row.amount}</strong><span>{row.transactionDate}</span></header><p>{row.method}{row.reference && ` · ${row.reference}`}</p>{row.notes && <p>{row.notes}</p>}{row.status === "void" ? <p className="text-muted-foreground">Void · {row.voidReason}</p> : !readOnly && <div className="flex flex-wrap gap-2"><Button type="button" variant="outline" size="sm" disabled={busy} onClick={() => {setEditing(row); setVoiding(null); setAdding(true); setError(""); setReason(""); setForm({requestId: crypto.randomUUID(), direction: row.direction, amount: row.amount, currency: row.currency, transactionDate: row.transactionDate, method: row.method, reference: row.reference || "", notes: row.notes || ""});}}>Correct transaction</Button>{canVoid && <Button type="button" variant="outline" size="sm" disabled={busy} onClick={() => {setAdding(false); setVoiding(row); setReason(""); setError("");}}>Void transaction</Button>}</div>}</article>)}
    {voiding && <div className="crm-financial-card"><p>Void {voiding.currency} {voiding.amount}. The original payment record remains in the history.</p><label>Reason<Input aria-label="Transaction void reason" maxLength={500} value={reason} onChange={e => setReason(e.target.value)}/></label>{error && <p role="alert" className="text-destructive">{error}</p>}<div className="flex justify-end gap-2"><Button type="button" variant="outline" disabled={busy} onClick={() => setVoiding(null)}>Keep transaction</Button><Button type="button" disabled={busy || reason.trim().length < 3} onClick={() => {setBusy(true); setError(""); void api.delete(`${root}/${contactId}/financial-transactions/${voiding.id}`, {data: {version: voiding.version || 1, reason}}).then(async () => {setVoiding(null); await qc.invalidateQueries({queryKey: ["contact-transactions"]});}).catch(e => setError(dealError(e))).finally(() => setBusy(false));}}>Confirm void</Button></div></div>}
    {(query.data?.total || 0) > 30 && <div className="flex justify-end gap-2"><Button type="button" variant="outline" disabled={page === 1} onClick={() => setPage(page-1)}>Previous transactions</Button><Button type="button" variant="outline" disabled={page*30 >= (query.data?.total || 0)} onClick={() => setPage(page+1)}>Next transactions</Button></div>}
  </section>;
}


export function FinancialDataPanel({contactId}: {contactId: number}) {
  const qc = useQueryClient();
  const profile = useQuery<FinancialData & {canManage?: boolean; canVoid?: boolean}>({queryKey: ["contact-financial", masterScope(), contactId], queryFn: () => loadFinancialData(contactId!)});
  const [draft, setDraft] = useState<FinancialData>();
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  return <div className="crm-financial"><FinancialDataTab contactId={contactId} value={draft} onChange={setDraft} readOnly={!profile.data?.canManage}/>{draft && profile.data?.canManage && <div className="flex flex-wrap gap-2"><Button type="button" disabled={busy} onClick={() => {setBusy(true); setMessage(""); void api.put(`${root}/${contactId}/financial-data`, draft).then(async () => {setDraft(undefined); setMessage("Financial data saved."); await Promise.all([qc.invalidateQueries({queryKey: ["contact-financial"]}), qc.invalidateQueries({queryKey: ["universal-contacts"]}), qc.invalidateQueries({queryKey:["shared-grid"]}), qc.invalidateQueries({queryKey:["master-company"]})]);}).catch(e => setMessage(dealError(e))).finally(() => setBusy(false));}}>Save financial data</Button><Button type="button" variant="outline" disabled={busy} onClick={() => setDraft(undefined)}>Discard financial changes</Button></div>}{message && <p role="status">{message}</p>}</div>;
}


export function CompanyFinancialDataPanel({companyId}: {companyId: number}) {
  const company = useQuery<{financialContactId?: number}>({queryKey:["master-company",masterScope(),"crm",String(companyId)],queryFn:async()=>(await api.get(`/master-data/companies/${companyId}`,{params:{source:"crm"}})).data});
  if(company.isPending)return <p role="status">Loading financial data...</p>;
  if(company.error)return <p role="alert">{dealError(company.error)}</p>;
  return company.data?.financialContactId ? <FinancialDataPanel key={company.data.financialContactId} contactId={company.data.financialContactId}/> : <p>Financial data requires an accessible, verified contact identity. Link existing business records in Relationship Hub if needed.</p>;
}
