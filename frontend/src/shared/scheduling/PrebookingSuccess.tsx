import { useEffect, useRef, useState } from 'react';
import { calendarText } from './prebooking-state';
import type { BookingSelection } from '@/apps/srm/industry/POSServiceScheduling';
import { Link } from 'react-router-dom';
import { useBusinessTerms } from '@/hooks/use-business-terms';
import { Button } from '@/components/ui/button';
import AppointmentVisitPanel from '@/apps/srm/industry/AppointmentVisitPanel';

export type ConfirmedPrebooking = {
  row: {id:number;title:string;status:string;revision:number;customer_id?:number;data:Record<string,string|number|number[]>};
  customerId?:number;serviceId?:number;booking?:BookingSelection;email?:string;phone?:string;
  customer: string; service: string; employee: string; startsAt: string; minutes: number; timezone: string; resources: string[];
};
export default function PrebookingSuccess({ saved, onAnother, capabilities, onChanged }: { saved: ConfirmedPrebooking; onAnother: (mode?:'same_customer'|'repeat') => void; onChanged: () => void; capabilities: {billing?:boolean;collect?:boolean;invoice?:boolean;approve_invoice?:boolean} }) {
  const [preview,setPreview]=useState(false);
  const {term} = useBusinessTerms();
  const heading = useRef<HTMLHeadingElement>(null);
  useEffect(() => { heading.current?.focus(); }, []);
  const formatter = new Intl.DateTimeFormat(undefined,{timeZone:saved.timezone,dateStyle:'medium',timeStyle:'short'});
  return <section className="prebooking-success" aria-label="Prebooking confirmation">
    <h2 ref={heading} tabIndex={-1}>Prebooking confirmed</h2><p role="status">Saved successfully. Reference #{saved.row.id}</p>
    <dl>{[[term('customer'),saved.customer],[term('service'),saved.service],[term('provider'),saved.employee],['Starts',formatter.format(new Date(saved.startsAt))],['Ends',formatter.format(new Date(Date.parse(saved.startsAt)+saved.minutes*60000))],['Timezone',saved.timezone],['Resources',saved.resources.join(', ') || 'No additional resources']].map(([label,value])=><div key={label}><dt>{label}</dt><dd>{value}</dd></div>)}</dl>
    <p>No payment collected. Collect later in POS.</p><div className="prebooking-success-actions">
      <AppointmentVisitPanel timezone={saved.timezone} row={saved.row} triggerLabel="View booking" providers={[saved.employee,...saved.resources]} canViewBilling={!!capabilities.billing} canCollect={!!capabilities.collect} canInvoice={!!capabilities.invoice} canApprove={!!capabilities.approve_invoice} onChanged={onChanged}/>
      {capabilities.billing && <Button asChild variant="outline"><Link to={`/srm/pos/terminal?prebooking=${saved.row.id}`}>Open in POS</Link></Button>}
      <Button type="button" onClick={()=>onAnother()}>Book another</Button>
      <Button type="button" variant="outline" onClick={()=>onAnother('same_customer')}>Book another for this customer</Button>
      <Button type="button" variant="outline" onClick={()=>onAnother('repeat')}>Repeat as new draft</Button>
      <Button type="button" variant="outline" onClick={()=>{const blob=new Blob([calendarText(saved,location.origin)],{type:'text/calendar;charset=utf-8'});const url=URL.createObjectURL(blob);const link=document.createElement('a');link.href=url;link.download=`booking-${saved.row.id}.ics`;link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}}>Download calendar event</Button>
      <Button type="button" variant="outline" onClick={()=>setPreview(v=>!v)}>Preview confirmation</Button>
    </div>
    {preview && <section aria-label="Confirmation preview"><h3>Confirmation preview</h3><p>{saved.customer}: {saved.service} with {saved.employee}, {formatter.format(new Date(saved.startsAt))} ({saved.timezone}). Reference #{saved.row.id}.</p><p>Open your messaging app to review and send. Delivery is not tracked here.</p>{saved.email && <Button asChild variant="outline"><a href={`mailto:${encodeURIComponent(saved.email)}?subject=${encodeURIComponent(`Booking #${saved.row.id}`)}&body=${encodeURIComponent(`${saved.service} with ${saved.employee}, ${formatter.format(new Date(saved.startsAt))} (${saved.timezone}). Reference #${saved.row.id}.`)}`}>Open email draft</a></Button>}{saved.phone && <Button asChild variant="outline"><a href={`sms:${encodeURIComponent(saved.phone)}?body=${encodeURIComponent(`${saved.service}, ${formatter.format(new Date(saved.startsAt))} (${saved.timezone}). Reference #${saved.row.id}.`)}`}>Open SMS draft</a></Button>}{!saved.email && !saved.phone && <p>No email or phone is recorded for this customer.</p>}</section>}
  </section>;
}
