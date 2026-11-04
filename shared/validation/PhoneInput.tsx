import { CountryFlag } from "./CountryFlag";
import { parsePhoneNumberFromString } from "libphonenumber-js/max";
import { useEffect, useId, useRef, useState } from 'react';
import { contract, phoneError, phoneMaxLength, normalizePhonePaste } from './index';
type Props={id?:string;name?:string;label?:string;value:string;countryCode:string;onChange:(value:string)=>void;onCountryCodeChange:(code:string)=>void;onBlur?:()=>void;required?:boolean;disabled?:boolean;countryCodeDisabled?:boolean;error?:string;className?:string};
export function PhoneInput({id,name,label='Phone number',value,countryCode,onChange,onCountryCodeChange,onBlur,required,disabled,countryCodeDisabled,error,className}:Props){
  const popupRef=useRef<HTMLDivElement>(null);
  const [position,setPosition]=useState({top:0,left:0,width:320,maxHeight:300});
  const rootRef=useRef<HTMLDivElement>(null);
  const triggerRef=useRef<HTMLButtonElement>(null);
  const [selectedIso,setSelectedIso]=useState('');
  const [active,setActive]=useState(0);
  const effectiveCode=countryCode||contract.default_calling_code;
  const maxDigits=phoneMaxLength(effectiveCode);
  const inputError=effectiveCode==='+91'?'Use at most 10 digits for an Indian phone number.':'Use national digits only for the selected country.';
  const primaryIso=({'+1':'US','+44':'GB','+7':'RU','+61':'AU','+358':'FI'} as Record<string,string>)[effectiveCode];
  const selected=contract.countries.find(c=>c.iso===selectedIso&&c.code===effectiveCode)||contract.countries.find(c=>c.iso===primaryIso&&c.code===effectiveCode)||contract.countries.find(c=>c.code===effectiveCode);
  useEffect(()=>{if(!countryCode&&!disabled&&!countryCodeDisabled)onCountryCodeChange(contract.default_calling_code);},[countryCode,disabled,countryCodeDisabled,onCountryCodeChange]);
  const inputRef=useRef<HTMLInputElement>(null);
  const uid=useId();const inputId=id||uid;const [search,setSearch]=useState('');const [open,setOpen]=useState(false);const [interactionError,setInteractionError]=useState('');const [touched,setTouched]=useState(false);
  const countries=contract.countries.filter(country=>(country.country+' '+country.iso+' '+country.code).toLowerCase().includes(search.trim().toLowerCase()));
  const message=interactionError||error||(touched?phoneError(value,effectiveCode,required,/mobile/i.test(label)):'');
  useEffect(()=>{inputRef.current?.setCustomValidity(interactionError||error||phoneError(value,effectiveCode,required,/mobile/i.test(label)));},[value,effectiveCode,required,interactionError,error]);
  useEffect(()=>{
    if(!open||disabled||countryCodeDisabled)return;
    const popup=popupRef.current;
    // The browser top layer escapes overflow containers while keeping the selector
    // inside its form/dialog for focus management and outside-click handling.
    popup?.setAttribute('popover','manual');
    popup?.showPopover?.();
    popup?.querySelector('input')?.focus();
    const dismiss=(event:PointerEvent)=>{if(!rootRef.current?.contains(event.target as Node))setOpen(false);};
    const reposition=()=>{
      const rect=triggerRef.current?.getBoundingClientRect();if(!rect)return;
      const width=Math.min(320,window.innerWidth-16);
      const below=window.innerHeight-rect.bottom-8;
      const above=rect.top-8;
      const height=Math.min(300,Math.max(below,above));
      setPosition({left:Math.max(8,Math.min(rect.left,window.innerWidth-width-8)),top:below>=Math.min(300,above)?rect.bottom+4:Math.max(8,rect.top-height-4),width,maxHeight:height});
    };
    reposition();
    const escape=(event:KeyboardEvent)=>{
      if(event.key==='Escape'&&rootRef.current?.contains(event.target as Node)){
        event.preventDefault();event.stopPropagation();setOpen(false);triggerRef.current?.focus();
      }
    };
    window.addEventListener('keydown',escape,true);
    document.addEventListener('pointerdown',dismiss);
    window.addEventListener('resize',reposition);
    const scroll=(event:Event)=>{if(!popup?.contains(event.target as Node))reposition();};
    window.addEventListener('scroll',scroll,true);
    return ()=>{popup?.hidePopover?.();window.removeEventListener('keydown',escape,true);document.removeEventListener('pointerdown',dismiss);window.removeEventListener('resize',reposition);window.removeEventListener('scroll',scroll,true);};
  },[open,disabled,countryCodeDisabled]);
  useEffect(()=>{
    const list=popupRef.current?.querySelector<HTMLElement>('[role="listbox"]');
    const option=list?.querySelector<HTMLElement>(`[data-option-index="${active}"]`);
    if(!list||!option)return;
    if(option.offsetTop<list.scrollTop)list.scrollTop=option.offsetTop;
    else if(option.offsetTop+option.offsetHeight>list.scrollTop+list.clientHeight)list.scrollTop=option.offsetTop+option.offsetHeight-list.clientHeight;
  },[active,open]);
  function showCountries(){setSearch('');const index=contract.countries.findIndex(c=>c.iso===selected?.iso);setActive(Math.max(0,index));setOpen(true);}
  function selectCountry(country:typeof contract.countries[number]){
    setInteractionError('');setSelectedIso(country.iso);onCountryCodeChange(country.code);setOpen(false);setTouched(true);triggerRef.current?.focus();
  }
  function validateCandidate(candidate:string,input:HTMLInputElement){
    // Prevent maxlength from silently turning a pasted full/international number into a different valid number.
    if(candidate&&(candidate.length>maxDigits||/[^0-9]/.test(candidate))){setInteractionError(inputError);input.setCustomValidity(inputError);return false;}
    setInteractionError('');input.setCustomValidity('');onChange(candidate);return true;
  }
  return <div ref={rootRef} className={className} style={{minWidth:0}}>
    <div style={{display:'flex',gap:8,alignItems:'stretch',position:'relative'}}>
      <button ref={triggerRef} type="button" disabled={disabled||countryCodeDisabled} aria-label={`${label} country calling code: ${selected?.country||effectiveCode} ${effectiveCode}`} aria-haspopup="listbox" aria-controls={`${inputId}-countries`} aria-expanded={open} onClick={()=>open?setOpen(false):showCountries()} onKeyDown={event=>{if(event.key==='ArrowDown'){event.preventDefault();showCountries();}}} style={{width:'25%',minWidth:76,maxWidth:112,flexShrink:0,padding:'6px 6px',border:'1px solid #d5dae5',borderRadius:5,background:'inherit',color:'inherit',font:'inherit',display:'flex',alignItems:'center',justifyContent:'space-between',gap:4}}><span>{selected&&<span aria-hidden="true"><CountryFlag iso={selected.iso}/> </span>}{effectiveCode}</span><span aria-hidden="true">&#9662;</span></button>
      {open&&!disabled&&!countryCodeDisabled&&<div ref={popupRef} style={{position:'fixed',...position,margin:0,zIndex:1000,overflow:'hidden',background:'Canvas',color:'CanvasText',border:'1px solid #d5dae5',boxShadow:'0 8px 24px #0002',padding:4,borderRadius:7,boxSizing:'border-box'}} onKeyDown={event=>{
        if(event.key==='Escape'){event.preventDefault();event.stopPropagation();setOpen(false);triggerRef.current?.focus();}
        if(event.key==='Tab'){triggerRef.current?.focus();setOpen(false);}
        if(event.key==='ArrowDown'||event.key==='ArrowUp'){event.preventDefault();setActive(index=>Math.max(0,Math.min(countries.length-1,index+(event.key==='ArrowDown'?1:-1))));}
        if(event.key==='Enter'){event.preventDefault();if(countries[active])selectCountry(countries[active]);}
      }}>
        <input type="search" autoFocus role="combobox" aria-expanded="true" aria-controls={`${inputId}-countries`} aria-activedescendant={countries[active]?`${inputId}-${countries[active].iso}`:undefined} aria-label={`Search ${label.toLowerCase()} country`} value={search} onChange={event=>{setSearch(event.target.value);setActive(0);}} placeholder="Search country or code" style={{width:'100%',boxSizing:'border-box',padding:'9px 10px',border:'1px solid #d5dae5',borderRadius:5,background:'inherit',color:'inherit',font:'inherit',marginBottom:4}}/>
        <div id={`${inputId}-countries`} role="listbox" aria-label="Country calling codes" style={{maxHeight:Math.max(40,position.maxHeight-54),overflowY:'auto',position:'relative',overscrollBehavior:'contain'}}>{countries.map((country,index)=><button id={`${inputId}-${country.iso}`} data-option-index={index} type="button" tabIndex={-1} role="option" aria-selected={country.iso===selected?.iso} key={country.iso} onMouseMove={()=>setActive(index)} onClick={()=>selectCountry(country)} style={{display:'flex',alignItems:'center',gap:10,width:'100%',padding:8,textAlign:'left',background:index===active?'Highlight':'transparent',color:index===active?'HighlightText':'inherit',border:0,borderRadius:4,cursor:'pointer',font:'inherit'}}><span aria-hidden="true" style={{width:20,height:20,border:'1px solid currentColor',borderRadius:'50%',display:'grid',placeItems:'center',flexShrink:0}}>{country.iso===selected?.iso?'●':''}</span><span><span style={{display:'block'}}><CountryFlag iso={country.iso}/> {country.iso} {country.code}</span><span style={{display:'block',fontSize:12,opacity:0.8,marginTop:2}}>{country.country}</span></span></button>)}{!countries.length&&<div role="status" style={{padding:12}}>No countries found</div>}</div>
      </div>}
      <input ref={inputRef} id={inputId} name={name} type="tel" inputMode="numeric" maxLength={maxDigits} autoComplete="tel-national" required={required} disabled={disabled} value={value} aria-label={label} aria-invalid={!!message} aria-describedby={message?`${inputId}-error`:undefined} pattern={`[0-9]{4,${maxDigits}}`} style={{minWidth:0,flex:1,width:0,border:'1px solid #d5dae5',borderRadius:5,padding:'8px 10px',minHeight:40,background:'inherit',color:'inherit',font:'inherit',boxSizing:'border-box'}} onPaste={event=>{const input=event.currentTarget;const paste=normalizePhonePaste(event.clipboardData.getData('text'),effectiveCode);const start=input.selectionStart??value.length;const end=input.selectionEnd??value.length;const candidate=value.slice(0,start)+paste+value.slice(end);event.preventDefault();validateCandidate(candidate,input);}} onBeforeInput={event=>{const native=event.nativeEvent as InputEvent;if(native.data&&/[^0-9]/.test(native.data)){event.preventDefault();setInteractionError(inputError);event.currentTarget.setCustomValidity(inputError);}}} onChange={event=>validateCandidate(event.target.value,event.currentTarget)} onBlur={()=>{setTouched(true);onBlur?.();}}/>
    </div>
    {message&&<small id={`${inputId}-error`} role="alert" style={{display:'block',color:'#b42318',marginTop:4}}>{message}</small>}
  </div>;
}

/** For existing APIs whose single communication field is already E.164. */
export function E164PhoneInput({value,onChange,label='Phone number',required=false}:{value:string;onChange:(value:string)=>void;label?:string;required?:boolean}) {
  const parsed=parsePhoneNumberFromString(value);
  const [code,setCode]=useState(parsed?'+'+parsed.countryCallingCode:'+91');
  useEffect(()=>{if(parsed&&'+'+parsed.countryCallingCode!==code)setCode('+'+parsed.countryCallingCode);},[value]);
  const national=value.startsWith(code)?value.slice(code.length):value;
  return <PhoneInput label={label} value={national} countryCode={code} required={required} onChange={number=>onChange(number?code+number:'')} onCountryCodeChange={next=>{setCode(next);onChange(national?next+national:'');}}/>;
}
