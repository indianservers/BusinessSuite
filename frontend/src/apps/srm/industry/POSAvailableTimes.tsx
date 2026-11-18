import { useEffect, useState } from 'react';
import { ChevronLeft, ChevronRight } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { bookingLabel } from '@/shared/scheduling/booking-view';

export default function POSAvailableTimes({slots,selected,minutes,zone,contextKey,onSelect}:{slots:{starts_at:string;label:string}[];selected?:string;minutes:number;zone:string;contextKey:string;onSelect:(instant:string)=>void}) {
  const [page,setPage]=useState(0);
  const [shortScreen,setShortScreen]=useState(()=>window.matchMedia('(max-width:639px) and (max-height:520px)').matches);
  useEffect(()=>{const media=window.matchMedia('(max-width:639px) and (max-height:520px)'),changed=()=>setShortScreen(media.matches);media.addEventListener('change',changed);return()=>media.removeEventListener('change',changed);},[]);
  const size=shortScreen?2:4, pages=Math.max(1,Math.ceil(slots.length/size)), current=Math.min(page,pages-1);
  useEffect(()=>setPage(0),[contextKey]);
  useEffect(()=>{const index=slots.findIndex(slot=>Date.parse(slot.starts_at)===Date.parse(selected || ''));if(index>=0)setPage(Math.floor(index/size));},[selected,contextKey,size]);
  return <div className="pos-compact-times">
    <div className="pos-compact-time-buttons">{slots.slice(current*size,(current+1)*size).map(slot=><Button key={slot.starts_at} type="button" variant={Date.parse(selected || '')===Date.parse(slot.starts_at)?'default':'outline'} aria-pressed={Date.parse(selected || '')===Date.parse(slot.starts_at)} aria-label={`${slot.label} to ${bookingLabel(Date.parse(slot.starts_at)+minutes*60000,zone,false)}`} onClick={()=>onSelect(slot.starts_at)}>{slot.label}<small>– {bookingLabel(Date.parse(slot.starts_at)+minutes*60000,zone,false)}</small></Button>)}</div>
    {pages>1&&<nav aria-label="Available time pages"><Button type="button" size="icon" variant="ghost" aria-label="Previous available times" disabled={current===0} onClick={()=>setPage(current-1)}><ChevronLeft size={16}/></Button><span>{current*size+1}–{Math.min((current+1)*size,slots.length)} of {slots.length}</span><Button type="button" size="icon" variant="ghost" aria-label="Next available times" disabled={current===pages-1} onClick={()=>setPage(current+1)}><ChevronRight size={16}/></Button></nav>}
  </div>;
}
