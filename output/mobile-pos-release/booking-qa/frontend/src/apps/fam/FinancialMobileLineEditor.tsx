import FinancialRecordLookup from "./FinancialRecordLookup";
import {useState,type HTMLAttributes} from 'react';
import {MobileSheet} from '@/components/mobile/MobilePrimitives';
import {Button} from '@/components/ui/button';
import {Input} from '@/components/ui/input';
import {NativeSelect} from '@/components/ui/native-select';
import type {FAMRecord} from './types';
export type FinancialLineField={key:string;label:string;inputMode?:HTMLAttributes<HTMLInputElement>['inputMode'];wide?:boolean;lookup?:"ledger"};
/** Present existing financial fields; parent retains conversion, calculations and authorization. */
export default function FinancialMobileLineEditor({title,lines,fields,canEdit,onChange,onAdd,addLabel='Add line'}:{title:string;lines:FAMRecord[];fields:FinancialLineField[];canEdit:boolean;onChange:(index:number,key:string,value:string)=>void;onAdd?:()=>void;addLabel?:string}){
 const[open,setOpen]=useState(false),[selected,setSelected]=useState(0),index=Math.min(selected,Math.max(0,lines.length-1)),line=lines[index];
 return <><Button type="button" variant="outline" onClick={()=>setOpen(true)}>{canEdit?'Edit':'View'} {title.toLowerCase()}s</Button><MobileSheet open={open} onClose={()=>setOpen(false)} title={title}>
  <div className="fam-financial-line-editor"><p>{canEdit?'Edits update this draft immediately. Save when ready.':'These lines are read-only.'}</p>
   <label className="fam-financial-line-wide">Entry line<NativeSelect aria-label="Entry line" disabled={!lines.length} value={index} onChange={event=>setSelected(Number(event.target.value))}>{lines.map((row,i)=><option key={i} value={i}>Line {i+1}{row.description?` · ${String(row.description)}`:''}</option>)}</NativeSelect></label>
   {line?fields.map(field=>field.lookup?<div key={field.key} className="fam-financial-line-wide"><span>Ledger account</span><FinancialRecordLookup kind={field.lookup} value={String(line[field.key]??'')} disabled={!canEdit} aria-label={`Line ${index+1} ${field.label}`} onChange={value=>onChange(index,field.key,value)}/></div>:<label key={field.key} className={field.wide?'fam-financial-line-wide':undefined}>{field.label}<Input aria-label={`Line ${index+1} ${field.label}`} inputMode={field.inputMode} disabled={!canEdit} value={String(line[field.key]??'')} onChange={event=>onChange(index,field.key,event.target.value)}/></label>):<p>No lines.</p>}
   <div className="fam-financial-line-nav"><Button type="button" variant="outline" disabled={index===0} onClick={()=>setSelected(index-1)}>Previous line</Button><span>{lines.length?index+1:0} / {lines.length}</span><Button type="button" variant="outline" disabled={index>=lines.length-1} onClick={()=>setSelected(index+1)}>Next line</Button></div>
   {canEdit&&onAdd&&<Button className="fam-financial-line-wide" type="button" variant="outline" onClick={()=>{onAdd();setSelected(lines.length);}}>{addLabel}</Button>}
   <Button className="fam-financial-line-wide" type="button" onClick={()=>setOpen(false)}>Done</Button>
  </div></MobileSheet></>;
}
