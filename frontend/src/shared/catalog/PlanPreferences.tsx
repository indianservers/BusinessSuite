import {useState} from 'react';
import {NativeSelect} from '@/components/ui/native-select';
import {Button} from '@/components/ui/button';
import {defaultText} from '@/lib/form-defaults';

export function BillingTimezone({value,onChange}:{value:string;onChange:(value:string)=>void}){
 const zones=[...new Set([value,defaultText('timezone'),'Asia/Kolkata','UTC',...((Intl as typeof Intl&{supportedValuesOf?:(key:string)=>string[]}).supportedValuesOf?.('timeZone')||[])])].filter(Boolean);
 return <label>Billing timezone<NativeSelect aria-label="Billing timezone" searchable value={value} onChange={e=>onChange(e.target.value)}>{zones.map(zone=><option value={zone} key={zone}>{zone.replace(/_/g,' ')}</option>)}</NativeSelect><small className="sc-muted">Starts with your business timezone for new plans. Existing plan settings are preserved.</small></label>;
}
export function ReminderDays({value,onChange}:{value:number[];onChange:(days:number[])=>void}){
 const [custom,setCustom]=useState('');
 function toggle(day:number,checked:boolean){if(checked&&!value.includes(day)&&value.length>=20)return;onChange([...new Set(checked?[...value,day]:value.filter(v=>v!==day))].sort((a,b)=>b-a));}
 const valid=value.length<20&&/^\d+$/.test(custom)&&Number(custom)>=0&&Number(custom)<=3650;
 return <fieldset className="sc-section"><legend>Reminder preferences</legend><p className="sc-muted">Select up to 20 intervals before expiry. These are configured preferences; no messages have been scheduled or delivered by this setting.</p><div className="sc-form-grid">{[30,7,1].map(day=><label key={day}>{day} {day===1?'day':'days'} before expiry<input aria-label={`Remind ${day} days before expiry`} type="checkbox" checked={value.includes(day)} disabled={!value.includes(day)&&value.length>=20} onChange={e=>toggle(day,e.target.checked)}/></label>)}<label>Additional reminder days<input aria-label="Additional reminder days" type="number" min={0} max={3650} step={1} value={custom} onChange={e=>setCustom(e.target.value)}/></label></div><Button type="button" size="sm" variant="outline" disabled={!valid} onClick={()=>{toggle(Number(custom),true);setCustom('');}}>Add reminder interval</Button>{value.filter(day=>![30,7,1].includes(day)).map(day=><div className="sc-preview-line" key={day}><span>{day===0?'On expiry day':`${day} days before expiry`}</span><Button type="button" variant="ghost" size="sm" aria-label={`Remove ${day} day reminder`} onClick={()=>toggle(day,false)}>Remove</Button></div>)}{value.length===0&&<p className="sc-muted">No reminder preferences selected.</p>}</fieldset>;
}
