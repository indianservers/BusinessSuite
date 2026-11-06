import type { Company } from '@/shared/master-data/CompanySelect';
import { phoneLinks } from '@/components/PhoneActions';
import type { Contact, Message } from './whatsapp/types';

export type Recipient = Company & { full_name?:string; fullName?:string; phoneCountryCode?:string; firstName?:string; lastName?:string; ownerName?:string; owner_name?:string; owner_id?:number; assignedTo?:number; stage?:string; lifecycle_stage?:string };
export type Invoice = { id:number; name:string; balance?:number|string; amount:number|string; currency:string; dueAt?:string; url:string; status:string };
export type DirectoryEntry = {to:string;entityType?:string;entityId?:number;contact:Contact|null;invoices:Invoice[];financeAvailable:boolean;unavailable?:boolean};
export type SendPayload = {requestId:string;to:string;body:string;entityType?:'lead'|'contact';entityId?:number;template?:{name:string;language:{code:string};components?:unknown[]};media?:string};
export type PreparedRecipient = {key:string;name:string;preview:string;phone:string;invoice?:Invoice;reason?:string;payload:SendPayload;contact?:Contact|null};
export type DeliveryResult = {key:string;name:string;payload:SendPayload;status:string;message?:Message;error?:string;scheduledId?:number;dueAt?:string};
export const recipientName=(r?:Recipient)=>r?.name||r?.fullName||r?.full_name||[r?.firstName,r?.lastName].filter(Boolean).join(' ')||'Select a contact';
export const recipientPhone=(r:Recipient)=>phoneLinks(r.phone,r.phone_country_code||r.phoneCountryCode)?.call.slice(4)||'';
export const digits=(value:string)=>value.replace(/\D/g,'');
export const ownerName=(r:Recipient)=>r.ownerName||r.owner_name||String(r.owner_id||r.assignedTo||'Unassigned');
export const stageName=(r:Recipient)=>r.stage||r.lifecycle_stage||r.status||'Not recorded';
export const money=(amount:number|string,currency='INR')=>new Intl.NumberFormat('en-IN',{style:'currency',currency,maximumFractionDigits:2}).format(Number(amount)||0);
export function renderTokens(body:string,values:Record<string,string>){return body.replace(/\{\{(\w+)\}\}/g,(token,key)=>values[key]||token);}
export function missingTokens(body:string){return [...new Set(body.match(/\{\{[^}]+\}\}/g)||[])];}
export function localDateTime(date:Date){return `${date.getFullYear()}-${String(date.getMonth()+1).padStart(2,'0')}-${String(date.getDate()).padStart(2,'0')}T${String(date.getHours()).padStart(2,'0')}:${String(date.getMinutes()).padStart(2,'0')}`;}
