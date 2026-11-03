import BranchSwitcher from "@/components/suite/BranchSwitcher";
import { Link } from "react-router-dom";
import { useState } from "react";
import { ArrowUp, MoreHorizontal, Sparkles } from "lucide-react";
import { MobileSheet } from "./MobilePrimitives";
import { useMobile } from "./useMobile";
import { useLocation, useNavigate } from "react-router-dom";
export default function MobileTools() {
 const mobile=useMobile(), [open,setOpen]=useState(false); const navigate=useNavigate(), location=useLocation();
 if(!mobile||!/^\/(crm|pms|srm|hrms)(\/|$)/.test(location.pathname))return null;
 return <><button type="button" className="mobile-tools-trigger" aria-label="Workspace tools" onClick={()=>setOpen(true)}><MoreHorizontal size={22}/></button><MobileSheet title="Workspace tools" open={open} onClose={()=>setOpen(false)}><BranchSwitcher /><Link className="mobile-filter-trigger" to="/settings" onClick={()=>setOpen(false)}>Settings & preferences</Link><button type="button" className="mobile-primary-action" onClick={()=>{setOpen(false);navigate(`/ai-agents/operator?module=${location.pathname.split('/')[1].toUpperCase()}`);}}><Sparkles size={18}/>AI assistant</button><button type="button" className="mobile-filter-trigger" onClick={()=>{setOpen(false);(document.querySelector('#suite-main,.mobile-dock-tasks')||document.scrollingElement)?.scrollTo({top:0,behavior:'smooth'});}}><ArrowUp size={18}/>Back to top</button></MobileSheet></>;
}
