import { useAuthStore } from "@/store/authStore";
import { canAccessRoute } from "@/lib/roles";
import { useState, type ReactNode } from "react";
import * as Tabs from "@radix-ui/react-tabs";
import { Link, useNavigate } from "react-router-dom";
import { Activity, ArrowLeft, ArrowRightLeft, BarChart3, Building2, CalendarCheck, CalendarDays, ChevronRight, FileText, Flag, Handshake, Home, Layers, LayoutGrid, ListTodo, MapPin, MoreVertical, Pencil, Pin, Star, Tag, UserRound, Users, Zap } from "lucide-react";
import { ActionButton, ConfirmActionDialog, MoreActionsMenu, type ActionSpec } from "@/components/actions";
import GlobalSearch from "@/components/app/GlobalSearch";
import ModuleNewMenu from "@/components/app/ModuleNewMenu";
import SuiteNotificationBell from "@/components/suite/SuiteNotificationBell";
import { assetUrl, formatDate } from "@/lib/utils";
import "./mobile-lead-details.css";

type Props = {
  record: Record<string, any>; title: string; actions: ActionSpec[];
  pinned: boolean; onPin: () => void; onAssign: () => void; onCreateDeal?: () => void; onAddActivity: () => void; assignment: ReactNode;
  discussion: ReactNode; ai: ReactNode; insights: ReactNode; details: ReactNode; activity: ReactNode; related: ReactNode;
};
export default function MobileLeadDetails({ record, title, actions, pinned, onPin, onAssign, onCreateDeal, onAddActivity, assignment, discussion, ai, insights, details, activity, related }: Props) {
  const navigate = useNavigate();
  const [avatarFailed, setAvatarFailed] = useState(false);
  const user = useAuthStore(state => state.user);
  const mayOpen = (path: string) => canAccessRoute(path, user?.role, user?.is_superuser);
  const [tab, setTab] = useState("overview");
  const [more, setMore] = useState(false);
  const [confirmation, setConfirmation] = useState<ActionSpec | null>(null);
  const converted = !!record.is_converted || String(record.status).toLowerCase() === "converted";
  const run = (action?: ActionSpec) => {
    if (!action || action.available === false || action.disabled || action.loading) return;
    if (action.confirm) setConfirmation(action);
    else if (action.href) navigate(action.href);
    else void action.onSelect?.();
  };
  const action = (id: string) => actions.find(item => item.id === id);
  const location = [record.city, record.state, record.country].filter(Boolean).join(", ");
  const company = record.company_name || record.companyName || record.company?.name || record.related?.account?.name;
  const avatar = record.avatar_url || record.photo_url || record.profile_image;
  const inactive = record.is_active === false || /^(inactive|lost|archived)$/i.test(record.status || "");
  const tabs = [["overview", "Overview", Home], ["details", "Details", FileText], ["activity", "Activity", Activity], ["related", "Related", Layers]] as const;
  return <div className="mobile-lead-page">
    <header className="ml-header">
      <Link to="/crm/leads" aria-label="Back to leads" className="ml-header-back"><ArrowLeft /></Link>
      <nav aria-label="Lead breadcrumb"><Link to="/crm">CRM</Link><ChevronRight/><Link to="/crm/leads">Leads</Link><ChevronRight/><strong>{title}</strong></nav>
      <div className="ml-header-tools"><GlobalSearch compact/><ModuleNewMenu/><SuiteNotificationBell/></div>
    </header>
    <div className="ml-content">
      <section className="ml-card ml-profile" aria-label="Lead profile">
        <div className="ml-identity">
          <div className="ml-avatar">{typeof avatar === "string" && avatar && !avatarFailed ? <img src={assetUrl(avatar)} alt={title} onError={() => setAvatarFailed(true)}/> : <span aria-label={`${title} initials`}>{title.split(/\s+/).slice(0, 2).map(word => word[0]).join("")}</span>}</div>
          <div className="ml-identity-text"><h1>{title}</h1><div className="ml-badges"><span>{converted ? "Customer" : /prospect/i.test(record.classification || "") ? "Prospect" : "Lead"}</span><span className={inactive ? "inactive" : "active"}><i/>{inactive ? "Inactive" : "Active"}</span></div></div>
          <div className="ml-profile-tools"><button aria-label={pinned ? "Unpin lead" : "Pin lead"} aria-pressed={pinned} onClick={onPin}><Star fill={pinned ? "currentColor" : "none"}/></button><button aria-label="Open lead actions" onClick={() => setMore(true)}><MoreVertical/></button></div>
        </div>
        <div className="ml-business"><span><Building2/>{company || "No company linked"}</span><span><MapPin/>{location || "Location not added"}</span></div>
        <div className="ml-communications" role="group" aria-label="Lead contact actions">{["whatsapp", "email", "call"].map(id => { const item = action(id); return item && item.available !== false && <ActionButton key={id} action={item.kind} disabled={item.disabled} disabledReason={item.disabledReason} tooltip={item.tooltip} onClick={() => run(item)}>{id === "whatsapp" ? "WhatsApp" : id === "email" ? "Email" : "Call"}</ActionButton>; })}<MoreActionsMenu triggerLabel="More" open={more} onOpenChange={setMore} actions={[...actions, {id:"history",kind:"view",label:"Communication history",onSelect:() => setTab("activity")}, {id:"activity",kind:"note",label:"Add activity",onSelect:onAddActivity}, {id:"assign",kind:"assign",label:"Assign employee",onSelect:() => {setTab("overview");onAssign();}}, ...(onCreateDeal ? [{id:"deal",kind:"quotation" as const,label:"Create deal",onSelect:onCreateDeal}] : [])]} onAction={run}/></div>
        <button className="ml-convert" disabled={action("convert")?.disabled || action("convert")?.loading} aria-busy={action("convert")?.loading} onClick={() => run(action("convert"))}><ArrowRightLeft/>{action("convert")?.loading ? "Converting…" : converted ? "Converted to Customer" : "Convert Lead to Customer"}</button>
      </section>
      <Tabs.Root value={tab} onValueChange={setTab} className="ml-tabs">
        <Tabs.List aria-label="CRM record information" className="ml-tab-list">{tabs.map(([id, label, Icon]) => <Tabs.Trigger key={id} value={id}><Icon/>{label}</Tabs.Trigger>)}</Tabs.List>
        <Tabs.Content value="overview" forceMount hidden={tab !== "overview"}>
          <section className="ml-card"><div className="ml-card-heading"><h2><BarChart3/>Lead Summary</h2><button onClick={() => run(action("edit"))}><Pencil/>Edit</button></div>
            <div className="ml-summary"><div><UserRound/><div><span>Assigned Employee</span>{assignment}</div></div><div><CalendarCheck/><div><span>Last Update</span><strong>{formatDate(record.updatedAt || record.updated_at || record.created_at)}</strong></div></div><div><Tag/><div><span>Source</span><strong className="ml-source">{record.source || "Not recorded"}</strong></div></div><div><Flag/><div><span>Priority</span><strong className="ml-priority">{record.priority || record.rating || "Not recorded"}</strong></div></div><div><Activity/><div><span>Current Status</span><strong>{record.status || "Not recorded"}</strong></div></div>{(record.next_follow_up_at || record.next_followup_at || record.next_follow_up_date) && <div><CalendarDays/><div><span>Next Follow-up</span><strong>{formatDate(record.next_follow_up_at || record.next_followup_at || record.next_follow_up_date)}</strong></div></div>}</div>
          </section>
          <section className="ml-card"><h2><Zap/>Quick Actions</h2><div className="ml-quick"><button onClick={onPin} aria-pressed={pinned}><Pin/>{pinned ? "Pinned" : "Pin"}</button><div>{discussion}</div><div>{ai}</div><button onClick={() => run(action("followup"))}><CalendarDays/>Follow-up</button><button onClick={() => run(action("task"))}><FileText/>Add Task</button></div></section>
          <section className="ml-card"><h2><ListTodo/>Lead Actions</h2><div className="ml-action-rows"><button onClick={() => run(action("followup"))}><CalendarDays/>Schedule Follow-up<ChevronRight/></button><button onClick={() => run(action("note"))}><FileText/>Add Note / Update<ChevronRight/></button><button onClick={() => setMore(true)}><LayoutGrid/>All lead actions<ChevronRight/></button></div></section>
          <details className="ml-detail-group"><summary>AI insights</summary>{insights}</details>
        </Tabs.Content>
        <Tabs.Content value="details" forceMount hidden={tab !== "details"}>{details}</Tabs.Content>
        <Tabs.Content value="activity" forceMount hidden={tab !== "activity"}>{activity}</Tabs.Content>
        <Tabs.Content value="related" forceMount hidden={tab !== "related"}>{related}</Tabs.Content>
      </Tabs.Root>
    </div>
    <nav className="ml-bottom-nav" aria-label="CRM mobile navigation"><button className={!more ? "selected" : ""} onClick={() => { setTab("overview"); document.getElementById("suite-main")?.scrollTo({ top: 0, behavior: "smooth" }); }}><Home/>Overview</button>{([["/crm/companies", "Customers", Users], ["/crm/deals", "Deals", Handshake], ["/crm/follow-ups", "Follow-ups", CalendarCheck]] as const).map(([path, label, Icon]) => mayOpen(path) ? <Link key={path} to={path}><Icon/>{label}</Link> : <button key={path} disabled aria-label={`${label} unavailable for your role`}><Icon/>{label}</button>)}<button className={more ? "selected" : ""} onClick={() => setMore(true)} aria-haspopup="menu" aria-expanded={more}><LayoutGrid/>Actions</button></nav>
    {confirmation?.confirm && <ConfirmActionDialog open onOpenChange={open => { if (!open) setConfirmation(null); }} {...confirmation.confirm} onConfirm={() => { const current = action(confirmation.id); setConfirmation(null); if (current && !current.disabled && !current.loading) void current.onSelect?.(); }}/>}
  </div>;
}
