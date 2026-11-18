import { NativeSelect } from '@/components/ui/native-select';

export type POSBookingPresentation='cart'|'dialog';
export default function POSBookingSettings({value,onChange}:{value:POSBookingPresentation;onChange:(value:POSBookingPresentation)=>void}) {
  return <label className="grid gap-2 text-sm">Service booking
    <NativeSelect aria-label="Service booking layout" value={value} onChange={event=>onChange(event.target.value==='dialog'?'dialog':'cart')}>
      <option value="cart">Employee &amp; time in cart</option>
      <option value="dialog">Compact booking dialog</option>
    </NativeSelect>
    <small className="text-slate-400">Saved for this POS browser. Availability and checkout checks apply to both layouts.</small>
  </label>;
}
