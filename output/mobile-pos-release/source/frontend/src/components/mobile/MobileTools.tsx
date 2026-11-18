import BranchSwitcher from "@/components/suite/BranchSwitcher";
import ModuleSwitcher from "@/components/layout/ModuleSwitcher";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { useEffect, useState } from "react";
import { ArrowUp, CalendarDays, LayoutGrid, MoreHorizontal, Sparkles } from "lucide-react";
import GlobalSearch from "@/components/app/GlobalSearch";
import MobileToday from "./MobileToday";
import { MobileSheet } from "./MobilePrimitives";
import { useMobile } from "./useMobile";
import "./mobile-tools.css";
export default function MobileTools({ onQuickActions, quickActionsLabel }: { onQuickActions?: () => void; quickActionsLabel?: string } = {}) {
  const mobile = useMobile(), phone = useMobile(480), [open, setOpen] = useState(false);
  const navigate = useNavigate(), location = useLocation();
  const [today, setToday] = useState(false);
  const existingModule = /^\/(crm|pms|srm|hrms)(\/|$)/.test(location.pathname);
  useEffect(() => { setOpen(false); setToday(false); }, [location.key, mobile, phone]);
  if (!mobile || (!existingModule && !phone)) return null;
  return <>
    <button type="button" className="mobile-tools-trigger suite-mobile-tools-trigger" aria-label="Workspace tools" aria-haspopup="dialog" aria-expanded={open} onClick={() => setOpen(true)}><MoreHorizontal size={22}/></button>
    <MobileSheet title="Workspace tools" open={open} onClose={() => setOpen(false)}>
      <div className="mobile-tools-search"><GlobalSearch compact shortcuts={false} /><span>Search pages, people and records</span></div>
      {existingModule && <button type="button" className="mobile-filter-trigger" onClick={() => { setOpen(false); requestAnimationFrame(() => setToday(true)); }}><CalendarDays size={18} />Today & recent work</button>}
      {onQuickActions && <button type="button" className="mobile-filter-trigger" onClick={() => { setOpen(false); requestAnimationFrame(onQuickActions); }}>{quickActionsLabel || "Page shortcuts"}</button>}
      <div className="suite-mobile-tools-fields"><ModuleSwitcher/><BranchSwitcher/></div>
      <Link className="mobile-filter-trigger" to="/dashboard" onClick={() => setOpen(false)}><LayoutGrid size={18}/>All applications</Link>
      <Link className="mobile-filter-trigger" to="/settings" onClick={() => setOpen(false)}>Settings & preferences</Link>
      <button type="button" className="mobile-primary-action" onClick={() => {setOpen(false);navigate(`/ai-agents/operator?module=${location.pathname.split('/')[1].toUpperCase()}`);}}><Sparkles size={18}/>AI assistant</button>
      <button type="button" className="mobile-filter-trigger" onClick={() => {setOpen(false);(document.querySelector('#suite-main,.mobile-dock-tasks') || document.scrollingElement)?.scrollTo({top:0,behavior:window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth'});}}><ArrowUp size={18}/>Back to top</button>
    </MobileSheet>
    <MobileSheet title="Today" open={today} onClose={() => setToday(false)}><MobileToday close={() => setToday(false)} /></MobileSheet>
  </>;
}
