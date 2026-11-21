import FinancialRecordLookup from "./FinancialRecordLookup";
import {useState,type HTMLAttributes} from 'react';
import {MobileSheet} from '@/components/mobile/MobilePrimitives';
import {Button} from '@/components/ui/button';
import {Input} from '@/components/ui/input';
import {NativeSelect} from '@/components/ui/native-select';
import type {FAMRecord} from './types';
export type FinancialLineField={key:string;label:string;inputMode?:HTMLAttributes<HTMLInputElement>['inputMode'];wide?:boolean;lookup?:"ledger"};
const decimalSeparator = Intl.NumberFormat().formatToParts(1.1).find(part => part.type === "decimal")?.value ?? ".";

export function MobileLineAmount({label, value, disabled, onChange}: {
  label: string;
  value: string;
  disabled: boolean;
  onChange: (value: string) => void;
}) {
  const [raw, setRaw] = useState<string | null>(null);

  return (
    <Input
      aria-label={label}
      inputMode="decimal"
      disabled={disabled}
      value={raw ?? value}
      onFocus={() => setRaw(value)}
      onBlur={() => setRaw(null)}
      onChange={event => {
        const entered = event.target.value;
        const normalized = entered.replace(decimalSeparator, ".");
        if (!/^-?\d*(?:\.\d*)?$/.test(normalized)) return;
        setRaw(entered);
        if (Number.isFinite(Number(normalized))) onChange(normalized);
      }}
    />
  );
}

/** Present existing financial fields; parent retains conversion, calculations and authorization. */
export default function FinancialMobileLineEditor({title,lines,fields,canEdit,onChange,onAdd,addLabel='Add line'}:{title:string;lines:FAMRecord[];fields:FinancialLineField[];canEdit:boolean;onChange:(index:number,key:string,value:string)=>void;onAdd?:()=>void;addLabel?:string}){
 const[open,setOpen]=useState(false),[selected,setSelected]=useState(0),index=Math.min(selected,Math.max(0,lines.length-1)),line=lines[index];
 return <><Button type="button" variant="outline" onClick={()=>setOpen(true)}>{canEdit?'Edit':'View'} {title.toLowerCase()}s</Button><MobileSheet open={open} onClose={()=>setOpen(false)} title={title}>
  <div className="fam-financial-line-editor"><p>{canEdit?'Edits update this draft immediately. Save when ready.':'These lines are read-only.'}</p>
   <label className="fam-financial-line-wide">Entry line<NativeSelect aria-label="Entry line" disabled={!lines.length} value={index} onChange={event=>setSelected(Number(event.target.value))}>{lines.map((row,i)=><option key={i} value={i}>Line {i+1}{row.description?` · ${String(row.description)}`:''}</option>)}</NativeSelect></label>
   <div className="fam-financial-line-nav"><Button type="button" variant="outline" disabled={index===0} onClick={()=>setSelected(index-1)}>Previous line</Button><span>{lines.length?index+1:0} / {lines.length}</span><Button type="button" variant="outline" disabled={index>=lines.length-1} onClick={()=>setSelected(index+1)}>Next line</Button></div>
   {line ? fields.map(field => {
    const label = `Line ${index + 1} ${field.label}`;
    const value = String(line[field.key] ?? "");
    const change = (input: string) => onChange(index, field.key, input);

    if (field.lookup) {
      return (
        <div key={field.key} className="fam-financial-line-wide">
          <span>Ledger account</span>
          <FinancialRecordLookup kind={field.lookup} value={value} disabled={!canEdit} aria-label={label} onChange={change} />
        </div>
      );
    }

    return (
      <label key={field.key} className={field.wide ? "fam-financial-line-wide" : undefined}>
        {field.label}
        {field.inputMode === "decimal" ? (
          <MobileLineAmount key={index} label={label} disabled={!canEdit} value={value} onChange={change} />
        ) : (
          <Input aria-label={label} inputMode={field.inputMode} disabled={!canEdit} value={value} onChange={event => change(event.target.value)} />
        )}
      </label>
    );
   }) : <p>No lines.</p>}
  </div>
  <div className="fam-line-editor-footer fam-financial-line-actions">
   {canEdit&&onAdd&&<Button type="button" variant="outline" onClick={()=>{onAdd();setSelected(lines.length);}}>{addLabel}</Button>}
   <Button type="button" onClick={()=>setOpen(false)}>Done</Button>
  </div>
  </MobileSheet></>;
}
