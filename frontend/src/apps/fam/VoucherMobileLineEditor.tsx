import {useState} from 'react';
import {MobileSheet} from '@/components/mobile/MobilePrimitives';
import {Button} from '@/components/ui/button';
import {Input} from '@/components/ui/input';
import {NativeSelect} from '@/components/ui/native-select';
import type {FAMRecord} from './types';
/** Phone entry for existing line fields; delegates all conversion and accounting rules. */
export default function VoucherMobileLineEditor({lines,ledgers,loading,error,canEdit,onChange,onAdd}:{lines:FAMRecord[];ledgers:FAMRecord[];loading:boolean;error:boolean;canEdit:boolean;onChange:(index:number,key:string,value:string)=>void;onAdd:()=>void}){
 const[open,setOpen]=useState(false),[selected,setSelected]=useState(0);
 const index=Math.min(selected,Math.max(0,lines.length-1)),line=lines[index];
 return <><Button type="button" variant="outline" onClick={()=>setOpen(true)}>{canEdit?'Edit entry lines':'View entry lines'}</Button>
  <MobileSheet open={open} onClose={()=>setOpen(false)} title={canEdit?'Edit voucher line':'Voucher line details'}>
   <div className="fam-voucher-line-editor">
    <p>{canEdit?'Edits update this voucher draft immediately. Save the draft when ready.':'This voucher is read-only.'}</p>
    <label>Entry line<NativeSelect aria-label="Entry line" disabled={!lines.length} value={index} onChange={event=>setSelected(Number(event.target.value))}>{lines.map((row,i)=><option value={i} key={i}>Line {i+1} · {String(ledgers.find(item=>Number(item.id)===Number(row.ledger_id))?.ledger_name||row.ledger_id||'Ledger not set')}</option>)}</NativeSelect></label>
    {line?<>
     <label>Ledger<NativeSelect aria-label={`Line ${index+1} Ledger`} loading={loading} error={error} disabled={!canEdit} value={String(line.ledger_id||1)} onChange={event=>onChange(index,'ledger_id',event.target.value)}>{ledgers.map(ledger=><option key={String(ledger.id)} value={String(ledger.id)}>{String(ledger.ledger_name||ledger.id)}</option>)}</NativeSelect></label>
     <div className="fam-voucher-line-pair">{(['debit_amount','credit_amount'] as const).map(key=><label key={key}>{key==='debit_amount'?'Debit':'Credit'}<Input aria-label={`Line ${index+1} ${key==='debit_amount'?'Debit':'Credit'}`} type="number" disabled={!canEdit} value={String(line[key]||0)} onChange={event=>onChange(index,key,event.target.value)}/></label>)}</div>
     <label>Cost Center<Input aria-label={`Line ${index+1} Cost Center`} inputMode="numeric" disabled={!canEdit} value={String(line.cost_center_id||'')} onChange={event=>onChange(index,'cost_center_id',event.target.value)}/></label>
     <label>Narration<Input aria-label={`Line ${index+1} Narration`} disabled={!canEdit} value={String(line.narration||'')} onChange={event=>onChange(index,'narration',event.target.value)}/></label>
    </>:<p>No entry lines.</p>}
    <div className="fam-voucher-line-navigation"><Button type="button" variant="outline" disabled={index===0} onClick={()=>setSelected(index-1)}>Previous line</Button><span>{lines.length?index+1:0} / {lines.length}</span><Button type="button" variant="outline" disabled={index>=lines.length-1} onClick={()=>setSelected(index+1)}>Next line</Button></div>
    {canEdit&&<Button type="button" variant="outline" onClick={()=>{onAdd();setSelected(lines.length);}}>Add line</Button>}
    <Button type="button" onClick={()=>setOpen(false)}>Done</Button>
   </div>
  </MobileSheet>
 </>;
}
