import { ArrowRight, CalendarDays, Check, Clock3, Users } from "lucide-react";
import type { HomeApplication } from "./homeApplications";
import crmArtwork from "@/assets/suite/module-crm.webp";
import financeArtwork from "@/assets/suite/module-fam.webp";
import hrmsArtwork from "@/assets/suite/module-hrms.webp";
import projectsArtwork from "@/assets/suite/module-pms.webp";
import powerAppsArtwork from "@/assets/suite/module-power_apps.webp";
import salesArtwork from "@/assets/suite/module-srm.webp";

const moduleArtwork: Partial<Record<string, string>> = {
  crm: crmArtwork,
  fam: financeArtwork,
  hrms: hrmsArtwork,
  pms: projectsArtwork,
  power_apps: powerAppsArtwork,
  srm: salesArtwork,
};

function ApplicationPreview({ app }: { app: HomeApplication }) {
  const artwork = moduleArtwork[app.key];
  if (app.key === "appointments") return <div className="home-calendar-art" aria-hidden="true"><div className="home-calendar"><div><i/><i/><i/></div><section>{Array.from({ length: 12 }, (_, i) => <span key={i}>{i === 6 && <Check size={18}/>}</span>)}</section></div><span className="home-clock"><Clock3/></span><span className="home-calendar-person"><Users/></span><span className="home-booking"><i/><i/></span></div>;
  return <div className={`home-preview home-preview-${app.key}`} aria-hidden="true"><div className="home-preview-window"><div className="home-window-dots"><i/><i/><i/></div>{app.key === "crm" ? <div className="home-pipeline">{["Lead", "Pipeline", "Won"].map(label => <div key={label}><b>{label}</b><i/><i/><i/></div>)}</div> : app.key === "pms" ? <div className="home-checklist">{[0,1,2].map(i => <div key={i}><Check/><i/></div>)}</div> : app.key === "fam" ? <svg viewBox="0 0 160 75"><path d="M8 65H150M8 45H150M8 25H150" stroke="#d4f2f5"/><path d="M20 62V48m25 14V39m25 23V47m25 15V26m25 36V18m25 44V5" stroke="#4dcdcf" strokeWidth="12"/><path d="m15 41 28-15 27 8 25-20 28 4 25-14" stroke="#00a3af" strokeWidth="3" fill="none"/></svg> : app.key === "power_apps" ? <div className="home-nodes"><i/><i/><i/><i/></div> : <div className="home-profile-lines"><i/><i/><i/></div>}</div>{artwork && <img src={artwork} alt="" width="120" height="120"/>}</div>;
}
export default function HomeApplicationCard({ app, selected, onSelect }: { app: HomeApplication; selected: boolean; onSelect: (path: string) => void }) {
  const Icon = app.key === "appointments" ? CalendarDays : app.module.icon;
  return <article className={`home-app home-app-${app.key}${selected ? " home-app-selected" : ""}`} aria-label={app.title}><div className="home-app-copy"><h3><span className="home-app-icon"><Icon size={23}/></span>{app.title}</h3><p>{app.description}</p></div><ApplicationPreview app={app}/><div className="home-app-chips">{app.chips.map(([ChipIcon, label]) => <span key={label}><ChipIcon size={14}/>{label}</span>)}</div><a className="home-explore" href={`/?next=${encodeURIComponent(app.module.homePath)}#home-auth`} onClick={e => { e.preventDefault(); onSelect(app.module.homePath); }}>Explore app <ArrowRight size={16}/></a></article>;
}
