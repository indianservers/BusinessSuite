import type { BookingSelection } from '@/apps/srm/industry/POSServiceScheduling';

export type ScheduleDraft = {versionKey?:string; serviceId:number; employeeId?:number; date:string; time:string; timezone?:string; duration:string; resources:number[] };
export type BookingAttempt = { body:Record<string,unknown>; display:Record<string,unknown> };
export type SavedDraft = { version:1; form:Record<string,string>; schedule?:ScheduleDraft; requestId:string; attempt?:BookingAttempt; savedAt:number };
export const draftKey = (scope:string,workspace='default') => `suite-prebooking-v4:${scope}:${workspace}`;
export function readDraft(key:string): SavedDraft | undefined {
  try {
    const value=JSON.parse(sessionStorage.getItem(key)||'null');
    if(value?.version!==1 || (!value.attempt && Date.now()-value.savedAt>86400000) || !/^[\da-f-]{36}$/i.test(value.requestId) || !value.form || Object.values(value.form).some(v=>typeof v!=='string'))return;
    return value;
  } catch { return; }
}
export function saveDraft(key:string,value:SavedDraft) { try{sessionStorage.setItem(key,JSON.stringify(value));return true;}catch{return false;} }
export function clearDraftStorage(key:string){try{sessionStorage.removeItem(key);}catch{/* Retain the in-memory draft if storage is unavailable. */}}
export function bookingError(error:unknown) {
  const response=(error as {response?:{status?:number;data?:{detail?:unknown}}})?.response;
  const detail=typeof response?.data?.detail==='string'?response.data.detail:'';
  if(!response || (response.status||0)>=500)return {uncertain:true,message:'The save outcome is unknown. Check booking status or retry the original request before changing details.'};
  if(response.status===401)return {uncertain:false,message:'Your session expired. Sign in again; this draft is retained for the same account and context.'};
  if(response.status===403)return {uncertain:false,message:'Your booking permission or branch access changed. Check your access before retrying.'};
  if(response.status===409 && /request|replay/i.test(detail))return {uncertain:true,message:'This request needs reconciliation. Check its status before changing details.'};
  if(response.status===409)return {uncertain:false,message:/eligib|policy/i.test(detail)?'Service rules or employee eligibility changed. Review the refreshed options.':'The slot or booking changed. Review current availability and choose an alternative.'};
  return {uncertain:false,message:detail || 'Check the highlighted booking details and try again.'};
}
export function selectionFromDraft(draft:ScheduleDraft,booking:BookingSelection|undefined):ScheduleDraft {
  return booking?{...draft,employeeId:booking.employee_id,duration:String(booking.duration_minutes),resources:booking.additional_resource_ids || []}:draft;
}
export function calendarText(saved:{row:{id:number;revision?:number;status?:string};customer:string;service:string;employee:string;startsAt:string;minutes:number;timezone:string;resources:string[]},scope:string) {
  const escape=(s:string)=>s.replace(/\\/g,'\\\\').replace(/\r?\n/g,'\\n').replace(/;/g,'\\;').replace(/,/g,'\\,');
  const stamp=(at:number)=>new Date(at).toISOString().replace(/[-:]/g,'').replace(/\.\d{3}Z$/,'Z');
  let hash=2166136261;for(const c of scope)hash=Math.imul(hash^c.charCodeAt(0),16777619);
  const lines=['BEGIN:VCALENDAR','VERSION:2.0','PRODID:-//Business Suite//Prebooking//EN','CALSCALE:GREGORIAN','BEGIN:VEVENT',`UID:prebooking-${saved.row.id}-${hash>>>0}@business-suite.invalid`,`DTSTAMP:${stamp(Date.now())}`,`DTSTART:${stamp(Date.parse(saved.startsAt))}`,`DTEND:${stamp(Date.parse(saved.startsAt)+saved.minutes*60000)}`,`SUMMARY:${escape(saved.service)}`,`DESCRIPTION:${escape(`Booking #${saved.row.id}\n${saved.customer}\n${saved.employee}\nBooking timezone: ${saved.timezone}`)}`,`LOCATION:${escape(saved.resources.join(', '))}`,`SEQUENCE:${Math.max(0,(saved.row.revision || 1)-1)}`,`STATUS:${['cancelled','no_show'].includes(saved.row.status || '')?'CANCELLED':'CONFIRMED'}`,'END:VEVENT','END:VCALENDAR'];
  return lines.map(line=>{let result='',part='';for(const c of line){if(new TextEncoder().encode(part+c).length>74){result+=part+'\r\n ';part='';}part+=c;}return result+part;}).join('\r\n')+'\r\n';
}
