import { useEffect, useId, useRef, useState } from 'react';
import { contract, phoneError, PHONE_ERROR } from './index';
type Props={id?:string;name?:string;label?:string;value:string;countryCode:string;onChange:(value:string)=>void;onCountryCodeChange:(code:string)=>void;onBlur?:()=>void;required?:boolean;disabled?:boolean;error?:string;className?:string};
export function PhoneInput({id,name,label='Phone number',value,countryCode,onChange,onCountryCodeChange,onBlur,required,disabled,error,className}:Props){
  const inputRef=useRef<HTMLInputElement>(null);
  const uid=useId();const inputId=id||uid;const [search,setSearch]=useState('');const [open,setOpen]=useState(false);const [interactionError,setInteractionError]=useState('');const [touched,setTouched]=useState(false);
  const countries=contract.countries.filter(country=>(country.country+' '+country.code).toLowerCase().includes(search.toLowerCase()));
  const message=interactionError||error||(value&&!countryCode?'Existing phone needs correction. Select its country code and enter exactly 10 ASCII digits.':touched?phoneError(value,countryCode,required):'');
  useEffect(()=>{inputRef.current?.setCustomValidity(interactionError || error || phoneError(value,countryCode,required));},[value,countryCode,required,interactionError,error]);
  function validateCandidate(candidate:string,input:HTMLInputElement){
    // Prevent maxlength from silently turning a pasted full/international number into a different valid number.
    if(candidate&&(candidate.length>contract.national_phone_length||/[^0-9]/.test(candidate))){setInteractionError(PHONE_ERROR);input.setCustomValidity(PHONE_ERROR);return false;}
    setInteractionError('');input.setCustomValidity('');onChange(candidate);return true;
  }
  return <div className={className} style={{minWidth:0}}>
    <div style={{display:'flex',gap:8,alignItems:'stretch',position:'relative'}}>
      <button type="button" disabled={disabled} aria-label={`${label} country calling code`} aria-expanded={open} onClick={()=>setOpen(!open)} style={{minWidth:70,padding:'6px 8px',border:'1px solid #d5dae5',borderRadius:5,background:'inherit',color:'inherit'}}>{countryCode||'Code'} ▾</button>
      {open&&<div style={{position:'absolute',top:'100%',left:0,zIndex:40,width:'min(300px,80vw)',background:'Canvas',color:'CanvasText',border:'1px solid GrayText',padding:8,borderRadius:6}}>
        <input type="search" autoFocus aria-label={`Search ${label.toLowerCase()} country`} value={search} onChange={event=>setSearch(event.target.value)} placeholder="Search country or calling code" style={{width:'100%'}}/>
        <div role="listbox" aria-label="Supported country calling codes" style={{maxHeight:220,overflowY:'auto'}}>{countries.map(country=><button type="button" role="option" aria-selected={country.code===countryCode} key={country.iso} onClick={()=>{onCountryCodeChange(country.code);setOpen(false);setTouched(true);}} style={{display:'block',width:'100%',padding:7,textAlign:'left',background:'inherit',color:'inherit',border:0}}>{country.country} ({country.code})</button>)}</div>
      </div>}
      <input ref={inputRef} id={inputId} name={name} type="tel" inputMode="numeric" maxLength={contract.national_phone_length} autoComplete="tel-national" required={required} disabled={disabled} value={value} aria-label={label} aria-invalid={!!message} aria-describedby={message?`${inputId}-error`:undefined} pattern={`[0-9]{${contract.national_phone_length}}`} style={{minWidth:0,flex:1,width:0,border:'1px solid #d5dae5',borderRadius:5,padding:'8px 10px',minHeight:40,background:'inherit',color:'inherit',font:'inherit',boxSizing:'border-box'}} onPaste={event=>{const input=event.currentTarget;const paste=event.clipboardData.getData('text');const start=input.selectionStart??value.length;const end=input.selectionEnd??value.length;const candidate=value.slice(0,start)+paste+value.slice(end);event.preventDefault();validateCandidate(candidate,input);}} onBeforeInput={event=>{const native=event.nativeEvent as InputEvent;if(native.data&&/[^0-9]/.test(native.data)){event.preventDefault();setInteractionError(PHONE_ERROR);event.currentTarget.setCustomValidity(PHONE_ERROR);}}} onChange={event=>validateCandidate(event.target.value,event.currentTarget)} onBlur={()=>{setTouched(true);onBlur?.();}}/>
    </div>
    {message&&<small id={`${inputId}-error`} role="alert" style={{display:'block',color:'#b42318',marginTop:4}}>{message}</small>}
  </div>;
}
