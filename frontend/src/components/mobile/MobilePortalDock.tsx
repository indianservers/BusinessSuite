import {useEffect,useRef,useState} from 'react';
import {Link,useLocation,useNavigate} from 'react-router-dom';
import {Home,FileText,Receipt,FolderKanban,UserRound,Users,Wallet,Plus,ArrowUpRight} from 'lucide-react';
import {MobileSheet} from './MobilePrimitives';
import {useMobile} from './useMobile';
import '../layout/mobile-module-dock.css';

/** Portal links stay inside the current customer or partner session. */
export default function MobilePortalDock({type,links,canSubmitLead=false,sessionScope}:{type:'customer'|'partner';links:string[][];canSubmitLead?:boolean;sessionScope?:string}){
 const mobile=useMobile(),location=useLocation(),[selected,setSelected]=useState<string|null>(null);
 const navigate=useNavigate(),pending=useRef<{key:string;scope?:string}|null>(null),mounted=useRef(true);
 const context=useRef({key:location.key,scope:sessionScope,canSubmitLead,type});context.current={key:location.key,scope:sessionScope,canSubmitLead,type};
 useEffect(()=>{mounted.current=true;return()=>{mounted.current=false;pending.current=null;};},[]);
 useEffect(()=>{setSelected(null);pending.current=null;},[location.key,mobile,sessionScope]);
 if(!mobile)return null;
 const icons:Record<string,typeof Home>={Home,Quotes:FileText,Invoices:Receipt,Projects:FolderKanban,Profile:UserRound,Leads:Users,Commissions:Wallet};
 return <><nav className="mobile-module-dock" style={{gridTemplateColumns:`repeat(${links.length},minmax(0,1fr))`}} aria-label={`${type} portal mobile navigation`}>
  {links.map(([label,to])=>{const Icon=icons[label]||Home,active=location.pathname===to;return <div className={`mobile-dock-item ${active?'is-active':''}`} key={to}><Link to={to} className="mobile-dock-destination" aria-current={active?'page':undefined}><span className="mobile-dock-icon"><Icon size={22} aria-hidden="true"/></span><span>{label}</span></Link><button type="button" className="mobile-dock-submenu" aria-label={`${label} shortcuts`} aria-haspopup="dialog" aria-expanded={selected===label} onClick={()=>setSelected(label)}><Plus size={18} aria-hidden="true"/></button></div>;})}
 </nav><MobileSheet title={`${selected||'Portal'} shortcuts`} open={!!selected} onClose={()=>setSelected(null)} onClosed={()=>{const action=pending.current;pending.current=null;if(action)requestAnimationFrame(()=>{if(mounted.current&&context.current.key===action.key&&context.current.scope===action.scope&&context.current.canSubmitLead&&context.current.type==='partner')navigate('/portal/partner/leads#new-record');});}}><div className="mobile-dock-actions">{selected==='Leads'&&canSubmitLead&&<Link to="/portal/partner/leads#new-record" onClick={event=>{if(event.button===0&&!event.metaKey&&!event.ctrlKey&&!event.shiftKey&&!event.altKey){event.preventDefault();pending.current={key:location.key,scope:sessionScope};}setSelected(null);}}><Plus size={18}/><span>Create partner lead</span></Link>}{links.map(([label,to])=><Link key={to} to={to} onClick={()=>setSelected(null)}><Plus size={18} aria-hidden="true"/><span>{label===selected?`Open ${label}`:label}</span><ArrowUpRight size={18} aria-hidden="true"/></Link>)}</div></MobileSheet></>;
}
