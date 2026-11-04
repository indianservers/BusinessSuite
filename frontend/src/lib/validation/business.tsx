import {z} from 'zod';
import definitions from '../../../../backend/app/core/business_forms.json';
import {contract, emailError, phoneError} from './index';
import {NativeSelect} from '@/components/ui/native-select';

export const businessDefinitions=definitions;
export const countryIso=(value?:string)=>contract.countries.find(c=>c.iso===value||c.country.toLowerCase()===value?.toLowerCase())?.iso||({UAE:'AE',UK:'GB'}[value||''] as string|undefined)||'IN';
export const canonicalBusinessType=(value?:string)=>{
  if(!value)return '';
  const key=value.toLowerCase().replace(/[^a-z0-9]/g,'');
  return definitions.businessTypes.find(t=>t.id===value||t.label.toLowerCase().replace(/[^a-z0-9]/g,'')===key)?.id||(definitions.aliases as Record<string,string>)[key]||value;
};
export function normalizedWebsite(value:string){
  if(!value.trim())return '';
  const url=new URL(/^[a-z][a-z0-9+.-]*:/i.test(value.trim())?value.trim():`https://${value.trim()}`);
  if(!['http:','https:'].includes(url.protocol)||!url.hostname.includes('.')||url.username||url.password||/\s/.test(value))throw Error('Enter an HTTP/HTTPS website or domain name');
  return url.href;
}
export const companyBasicsSchema=z.object({
  name:z.string().trim().min(1,'Company name is required').max(180),
  email:z.string().refine(v=>!emailError(v),{message:'Enter a valid email address'}),
  website:z.string().refine(v=>{try{normalizedWebsite(v);return true;}catch{return false;}},{message:'Enter an HTTP/HTTPS website or domain name'}),
  phone:z.string(),phone_country_code:z.string(),
}).superRefine((v,ctx)=>{const message=phoneError(v.phone,v.phone_country_code);if(message)ctx.addIssue({code:'custom',path:['phone'],message});});

export function registrationError(kind:string,value:string,country:string){
  const n=value.replace(/\s/g,'').toUpperCase(),type=kind.toUpperCase();if(!n)return '';
  const patterns:Record<string,RegExp>={PAN:/^[A-Z]{5}[0-9]{4}[A-Z]$/,GSTIN:/^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]$/,CIN:/^[LU][0-9]{5}[A-Z]{2}[0-9]{4}[A-Z]{3}[0-9]{6}$/,LLPIN:/^(?:[A-Z]{3}-[0-9]{4}|F[A-Z]{2}-[0-9]{4})$/,TRN:/^[0-9]{15}$/};
  if(patterns[type]&&country!==(type==='TRN'?'AE':'IN'))return `${type} is not applicable to this country`;
  if(patterns[type]&&!patterns[type].test(n))return `Enter a valid ${type} format`;
  if(type==='GSTIN'){const alphabet='0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ';const sum=[...n.slice(0,14)].reduce((s,c,i)=>{const p=alphabet.indexOf(c)*(1+i%2);return s+Math.floor(p/36)+p%36;},0);if(n[14]!==alphabet[(36-sum%36)%36])return 'GSTIN checksum is invalid';}
  return '';
}
export function bankCodeError(kind:string,input:string,country?:string){
  const n=input.replace(/\s/g,'').toUpperCase();if(!n)return '';
  if(kind==='IFSC'&&((country&&country!=='IN')||!/^[A-Z]{4}0[A-Z0-9]{6}$/.test(n)))return 'Enter a valid Indian IFSC';
  if(kind==='BIC'&&!/^[A-Z]{6}[A-Z0-9]{2}(?:[A-Z0-9]{3})?$/.test(n))return 'Enter an 8- or 11-character SWIFT/BIC';
  if(kind==='IBAN'){
    if(!/^[A-Z]{2}[0-9]{2}[A-Z0-9]{11,30}$/.test(n))return 'Enter a valid IBAN';
    const length=(definitions.ibanLengths as Record<string,number>)[n.slice(0,2)];
    if(!length||n.length!==length||(country&&n.slice(0,2)!==country))return 'IBAN country or length is invalid';
    const digits=[...(n.slice(4)+n.slice(0,4))].map(c=>/[A-Z]/.test(c)?String(c.charCodeAt(0)-55):c).join('');
    let remainder=0;for(const digit of digits)remainder=(remainder*10+Number(digit))%97;
    if(remainder!==1)return 'IBAN checksum is invalid';
  }return '';
}
export function CountrySelect({value,onChange,label='Country',disabled=false}:{value:string;onChange:(value:string)=>void;label?:string;disabled?:boolean}){
  return <NativeSelect searchable aria-label={label} value={value} onChange={e=>onChange(e.target.value)} disabled={disabled}>{contract.countries.map(c=><option key={c.iso} value={c.iso}>{c.country} ({c.iso})</option>)}</NativeSelect>;
}
export { CurrencySelect } from './CurrencySelect';
export function BusinessTypeSelect({value,onChange,country}:{value:string;onChange:(value:string)=>void;country:string}){
  const items=definitions.businessTypes.filter(t=>!t.countries.length||t.countries.includes(country)||t.id===value);
  return <NativeSelect searchable aria-label="Business type" value={value} onChange={e=>onChange(e.target.value)}><option value="">Not specified</option>{value&&!definitions.businessTypes.some(t=>t.id===value)&&<option value={value}>{value} (saved legacy value)</option>}{items.map(t=><option key={t.id} value={t.id}>{t.label}</option>)}</NativeSelect>;
}
