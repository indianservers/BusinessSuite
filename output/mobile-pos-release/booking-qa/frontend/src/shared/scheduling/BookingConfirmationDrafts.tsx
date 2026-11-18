import { useState } from 'react';
import { internationalPhone } from './prebooking-messages';
import type { ConfirmedPrebooking } from './PrebookingSuccess';

/** Confirmation preferences prepare reviewed drafts; they never send a message automatically. */
export default function BookingConfirmationDrafts({ saved }: { saved: ConfirmedPrebooking }) {
  const channels = String(saved.row.data.confirmation_channels || '').split(',').filter(c=>c==='sms'||c==='whatsapp');
  const [preview,setPreview] = useState(false);
  const [message,setMessage] = useState(()=>`${saved.customer}: ${saved.service} with ${saved.employee}, ${new Intl.DateTimeFormat('en-IN',{timeZone:saved.timezone,dateStyle:'medium',timeStyle:'short'}).format(new Date(saved.startsAt))} (${saved.timezone}). Booking #${saved.row.id}.${saved.customerNotes?`\n${saved.customerNotes}`:''}`);
  const recipient=internationalPhone(saved.phone,saved.phoneCountryCode);
  if (!channels.length) return null;
  return <section className="booking-confirmation-drafts"><button type="button" onClick={()=>setPreview(v=>!v)} aria-expanded={preview}>Review selected confirmation messages</button>{preview&&<><p>Review your message, then open your messaging app to send it.</p><label>Confirmation message<textarea aria-label="Selected confirmation message" rows={4} maxLength={8000} value={message} onChange={e=>setMessage(e.target.value)}/></label>{!/^\+[1-9]\d{7,14}$/.test(recipient)?<p role="alert">A valid customer phone number is required. Add one to the customer before sending.</p>:channels.map(channel=><a key={channel} href={channel==='whatsapp'?`https://wa.me/${recipient.replace(/\D/g,'')}?text=${encodeURIComponent(message)}`:`sms:${encodeURIComponent(recipient)}?body=${encodeURIComponent(message)}`}>Open {channel==='sms'?'SMS':'WhatsApp'} confirmation draft</a>)}</>}</section>;
}
