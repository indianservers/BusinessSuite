import { useEffect, useId, useRef, useState } from 'react';
import { contract, phoneError, PHONE_ERROR } from './index';
type Props={id?:string;name?:string;label?:string;value:string;countryCode:string;onChange:(value:string)=>void;onCountryCodeChange:(code:string)=>void;onBlur?:()=>void;required?:boolean;disabled?:boolean;countryCodeDisabled?:boolean;error?:string;className?:string};
export function PhoneInput({id,name,label='Phone number',value,countryCode,onChange,onCountryCodeChange,onBlur,required,disabled,countryCodeDisabled,error,className}:Props){
  const rootRef=useRef<HTMLDivElement>(null);
  const triggerRef=useRef<HTMLButtonElement>(null);
  const [selectedIso,setSelectedIso]=useState('');
  const [active,setActive]=useState(0);
  const effectiveCode=countryCode||contract.default_calling_code;
  const selected=contract.countries.find(c=>c.iso===selectedIso&&c.code===effectiveCode)||contract.countries.find(c=>c.code===effectiveCode);
  useEffect(()=>{if(!countryCode&&!disabled&&!countryCodeDisabled)onCountryCodeChange(contract.default_calling_code);},[countryCode,disabled,countryCodeDisabled,onCountryCodeChange]);
  const inputRef=useRef<HTMLInputElement>(null);
  const uid=useId();const inputId=id||uid;const [search,setSearch]=useState('');const [open,setOpen]=useState(false);const [interactionError,setInteractionError]=useState('');const [touched,setTouched]=useState(false);
  const countries=contract.countries.filter(country=>(country.country+' '+country.iso+' '+country.code).toLowerCase().includes(search.trim().toLowerCase()));
  const message=interactionError||error||(touched?phoneError(value,effectiveCode,required):'');
  useEffect(()=>{inputRef.current?.setCustomValidity(interactionError||error||phoneError(value,effectiveCode,required));},[value,effectiveCode,required,interactionError,error]);
  useEffect(()=>{
    if(!open)return;
    const dismiss=(event:PointerEvent)=>{if(!rootRef.current?.contains(event.target as Node))setOpen(false);};
    document.addEventListener('pointerdown',dismiss);
    return ()=>document.removeEventListener('pointerdown',dismiss);
  },[open]);
  useEffect(()=>{if(open)rootRef.current?.querySelector(`[data-option-index="${active}"]`)?.scrollIntoView({block:'nearest'});},[active,open]);
  function selectCountry(country:typeof contract.countries[number]){
    setSelectedIso(country.iso);onCountryCodeChange(country.code);setOpen(false);setTouched(true);triggerRef.current?.focus();
  }
  function validateCandidate(candidate:string,input:HTMLInputElement){
    // Prevent maxlength from silently turning a pasted full/international number into a different valid number.
    if(candidate&&(candidate.length>contract.national_phone_length||/[^0-9]/.test(candidate))){setInteractionError(PHONE_ERROR);input.setCustomValidity(PHONE_ERROR);return false;}
    setInteractionError('');input.setCustomValidity('');onChange(candidate);return true;
  }
  return <div ref={rootRef} className={className} style={{minWidth:0}}>
    <div style={{display:'flex',gap:8,alignItems:'stretch',position:'relative'}}>
      <button ref={triggerRef} type="button" disabled={disabled||countryCodeDisabled} aria-label={`${label} country calling code: ${selected?.country||effectiveCode} ${effectiveCode}`} aria-haspopup="listbox" aria-controls={`${inputId}-countries`} aria-expanded={open} onClick={()=>{setSearch('');setActive(0);setOpen(!open);}} onKeyDown={event=>{if(event.key==='ArrowDown'){event.preventDefault();setSearch('');setActive(0);setOpen(true);}}} style={{minWidth:108,padding:'6px 10px',border:'1px solid #d5dae5',borderRadius:5,background:'inherit',color:'inherit',font:'inherit',display:'flex',alignItems:'center',justifyContent:'space-between',gap:12}}><span>{selected?.iso} {effectiveCode}</span><span aria-hidden="true">&#9662;</span></button>
      {open&&!disabled&&!countryCodeDisabled&&<div style={{position:'absolute',top:'100%',left:0,zIndex:1000,width:'min(320px,80vw)',background:'Canvas',color:'CanvasText',border:'1px solid #d5dae5',boxShadow:'0 8px 24px #0002',padding:4,borderRadius:7,boxSizing:'border-box'}} onKeyDown={event=>{
        if(event.key==='Escape'){event.preventDefault();setOpen(false);triggerRef.current?.focus();}
        if(event.key==='Tab')setOpen(false);
        if(event.key==='ArrowDown'||event.key==='ArrowUp'){event.preventDefault();setActive(index=>Math.max(0,Math.min(countries.length-1,index+(event.key==='ArrowDown'?1:-1))));}
        if(event.key==='Enter'){event.preventDefault();if(countries[active])selectCountry(countries[active]);}
      }}>
        <input type="search" autoFocus role="combobox" aria-expanded="true" aria-controls={`${inputId}-countries`} aria-activedescendant={countries[active]?`${inputId}-${countries[active].iso}`:undefined} aria-label={`Search ${label.toLowerCase()} country`} value={search} onChange={event=>{setSearch(event.target.value);setActive(0);}} placeholder="Search country or code" style={{width:'100%',boxSizing:'border-box',padding:'9px 10px',border:'1px solid #d5dae5',borderRadius:5,background:'inherit',color:'inherit',font:'inherit',marginBottom:4}}/>
        <div id={`${inputId}-countries`} role="listbox" aria-label="Country calling codes" style={{maxHeight:248,overflowY:'auto',overscrollBehavior:'contain'}}>{countries.map((country,index)=><button id={`${inputId}-${country.iso}`} data-option-index={index} type="button" tabIndex={-1} role="option" aria-selected={country.iso===selected?.iso} key={country.iso} onMouseMove={()=>setActive(index)} onClick={()=>selectCountry(country)} style={{display:'flex',alignItems:'center',gap:10,width:'100%',padding:8,textAlign:'left',background:index===active?'Highlight':'transparent',color:index===active?'HighlightText':'inherit',border:0,borderRadius:4,cursor:'pointer',font:'inherit'}}><span aria-hidden="true" style={{width:20,height:20,border:'1px solid currentColor',borderRadius:'50%',display:'grid',placeItems:'center',flexShrink:0}}>{country.iso===selected?.iso?'●':''}</span><span><span style={{display:'block'}}>{country.iso} {country.code}</span><span style={{display:'block',fontSize:12,opacity:0.8,marginTop:2}}>{country.country}</span></span></button>)}{!countries.length&&<div role="status" style={{padding:12}}>No countries found</div>}</div>
      </div>}
      <input ref={inputRef} id={inputId} name={name} type="tel" inputMode="numeric" maxLength={contract.national_phone_length} autoComplete="tel-national" required={required} disabled={disabled} value={value} aria-label={label} aria-invalid={!!message} aria-describedby={message?`${inputId}-error`:undefined} pattern={`[0-9]{${contract.national_phone_length}}`} style={{minWidth:0,flex:1,width:0,border:'1px solid #d5dae5',borderRadius:5,padding:'8px 10px',minHeight:40,background:'inherit',color:'inherit',font:'inherit',boxSizing:'border-box'}} onPaste={event=>{const input=event.currentTarget;const paste=event.clipboardData.getData('text');const start=input.selectionStart??value.length;const end=input.selectionEnd??value.length;const candidate=value.slice(0,start)+paste+value.slice(end);event.preventDefault();validateCandidate(candidate,input);}} onBeforeInput={event=>{const native=event.nativeEvent as InputEvent;if(native.data&&/[^0-9]/.test(native.data)){event.preventDefault();setInteractionError(PHONE_ERROR);event.currentTarget.setCustomValidity(PHONE_ERROR);}}} onChange={event=>validateCandidate(event.target.value,event.currentTarget)} onBlur={()=>{setTouched(true);onBlur?.();}}/>
    </div>
    {message&&<small id={`${inputId}-error`} role="alert" style={{display:'block',color:'#b42318',marginTop:4}}>{message}</small>}
  </div>;
}
