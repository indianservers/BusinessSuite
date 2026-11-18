import { CalendarDays, Clock3, Hourglass, UserRound, UsersRound, Scissors, Armchair, MessageCircle, Check } from 'lucide-react';
import type { BookingDisplay } from './PrebookingFields';
import { wall } from './booking-time';

export default function BookingSummary({ customer, service, display, available, channels, onChannels }: {
  customer?: { name: string; phone?: string; phone_country_code?: string; email?: string };
  service?: { name: string; price?: number; currency?: string };
  display: BookingDisplay; available: boolean | null; channels: string[]; onChannels: (channels: string[]) => void;
}) {
  const stamp = display.startsAt ? Date.parse(display.startsAt) : NaN;
  const zone = display.timezone || 'Asia/Kolkata';
  const minutes = display.minutes || 0;
  const local = Number.isFinite(stamp) ? wall(stamp,zone) : '';
  const startMinute = local ? Number(local.slice(11,13))*60+Number(local.slice(14,16)) : 720;
  const rangeStart = Math.max(0,Math.min(1200,Math.floor((startMinute-120)/60)*60));
  const span = Math.max(240,minutes+120);
  const clock = (value:number) => new Intl.DateTimeFormat('en-IN',{timeZone:zone,hour:'numeric',minute:'2-digit'}).format(value).toUpperCase();
  const dateLabel = Number.isFinite(stamp) ? new Intl.DateTimeFormat('en-GB',{timeZone:zone,day:'numeric',month:'short',year:'numeric'}).format(stamp) : 'Choose a date';
  const price = service && Number.isFinite(service.price) && service.currency ? new Intl.NumberFormat('en-IN',{style:'currency',currency:service.currency,minimumFractionDigits:0,maximumFractionDigits:2}).format(service.price!) : '—';
  return <aside className="booking-reference-summary" aria-label="Booking summary">
    <div className="booking-mobile-summary"><CalendarDays size={24}/><div><strong>{Number.isFinite(stamp)?`${new Intl.DateTimeFormat('en-GB',{timeZone:zone,day:'numeric',month:'short'}).format(stamp)} · ${clock(stamp)}–${clock(stamp+minutes*60000)}`:'Choose a time'}</strong><small>{[service?.name,display.employee,display.resources.join(', ')].filter(Boolean).join(' · ')||'Choose service and employee'}</small></div><b aria-label="Mobile booking total">{price}</b></div><h2>Booking summary</h2>
    <dl>{[
      {name:'Customer',icon:UserRound,value:customer?.name || 'Choose a customer',detail:customer?.phone ? `${customer.phone_country_code || ''} ${customer.phone}`.trim() : customer?.email},
      {name:'Service',icon:Scissors,value:service?.name || 'Choose a service',detail:service?`${price} · ${minutes || '—'} min`:undefined},
      {name:'Employee',icon:UsersRound,value:display.employee || 'Choose an employee',detail:display.employee ? available===true?'Available':available===false?'Unavailable':'Checking availability':undefined},
      {name:'Resource',icon:Armchair,value:display.resources.join(', ') || 'No resource selected'},
      {name:'Date',icon:CalendarDays,value:dateLabel},
      {name:'Time',icon:Clock3,value:Number.isFinite(stamp)?`${clock(stamp).replace(/ (AM|PM)$/,clock(stamp).slice(-2)===clock(stamp+minutes*60000).slice(-2)?'':' $1')} – ${clock(stamp+minutes*60000)}`:'Choose a start time'},
      {name:'Duration',icon:Hourglass,value:minutes?`${minutes} minutes`:'—'},
    ].map(({name,icon:Icon,value,detail})=><div key={name}><dt><Icon size={18}/>{name}</dt><dd><strong>{name==='Employee'&&display.employee&&<i className="booking-summary-availability" data-available={available}/>} {value}</strong>{detail&&<small>{detail}</small>}</dd></div>)}</dl>
    <div className="booking-summary-total"><strong>Total</strong><b aria-label="Booking estimated total">{price}</b></div>
    <section className="booking-summary-meter"><h3>Availability{Number.isFinite(stamp)?` (${new Intl.DateTimeFormat('en-GB',{timeZone:zone,weekday:'short',day:'numeric',month:'short'}).format(stamp).replace(/^(\w+) /,'$1, ')})`:''}</h3><div className="booking-summary-meter-track" aria-label={available===true?'Selected appointment is available':'Availability needs checking'}>{(display.availableSlots || []).map(slot=>{const localSlot=wall(Date.parse(slot),zone), m=Number(localSlot.slice(11,13))*60+Number(localSlot.slice(14,16));if(m<rangeStart||m>=rangeStart+span)return null;return <span key={slot} style={{left:`${(m-rangeStart)/span*100}%`,width:`${Math.min(minutes,rangeStart+span-m)/span*100}%`}}/>;})}{Number.isFinite(stamp)&&<i style={{left:`${Math.max(0,(startMinute-rangeStart)/span*100)}%`,width:`${Math.min(minutes/span*100,100)}%`}}/>}</div><div className="booking-summary-meter-times">{Array.from({length:5},(_,i)=>{const h=Math.floor((rangeStart+i*span/4)/60)%24;return <span key={i}>{h%12||12} {h<12?'AM':'PM'}</span>;})}</div><div className="booking-summary-meter-legend"><span><i/>This appointment</span><span><i/>Unavailable / unchecked</span></div></section>
    <section className="booking-summary-confirmation"><div><h3>Send confirmation</h3><button type="button" role="switch" className="reference-switch" aria-label="Prepare confirmation" aria-checked={!!channels.length} onClick={()=>onChannels(channels.length?[]:['sms'])}/></div><div>{['sms','whatsapp'].map(channel=><button type="button" key={channel} className={`booking-summary-channel ${channel}`} aria-pressed={channels.includes(channel)} onClick={()=>onChannels(channels.includes(channel)?channels.filter(c=>c!==channel):[...channels,channel])}><MessageCircle size={16}/>{channel==='sms'?'SMS':'WhatsApp'}{channels.includes(channel)&&<Check size={14}/>}</button>)}</div><small>Review and send your message after confirming.</small></section>
  </aside>;
}
