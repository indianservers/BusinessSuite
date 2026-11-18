import AppointmentShell from './AppointmentShell';
import type { ReactNode } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { canAccessRoute } from '@/lib/roles';
import { useAuthStore } from '@/store/authStore';
import { CalendarDays, CalendarRange, Clock3, DoorOpen, Layers3, Settings2, ShoppingCart, UsersRound, type LucideIcon } from 'lucide-react';
import './scheduling-workspace.css';
import './appointment-reference.css';
import './appointment-pixel.css';
import './appointment-mobile.css';
import './appointment-fidelity.css';

export type SchedulingNav = { label: string; icon: LucideIcon; active?: boolean; to?: string; onClick?: () => void };
export const schedulingIcons = { calendar: CalendarDays, timeline: CalendarRange, guide: Settings2, resources: DoorOpen, services: Layers3, employees: UsersRound, pos: ShoppingCart, time: Clock3 };

/** Shared full-width surface; secondary setup stays inside More. */
export default function SchedulingFrame({ title, subtitle, nav, children, actions, eyebrow = 'BOOKINGS WORKSPACE' }: {
  title: string; subtitle: string; nav: SchedulingNav[]; children: ReactNode; actions?: ReactNode; eyebrow?: string;
}) {
  const location=useLocation(),user=useAuthStore(state=>state.user);
  const workflow=[{label:'POS',to:'/srm/pos/terminal',icon:ShoppingCart},{label:'Appointments',to:'/srm/appointments',icon:CalendarDays},{label:'Scheduling',to:'/srm/service-scheduling?view=schedule',icon:CalendarRange}];
  if(/^\/(srm|crm)\/appointments\/?$/.test(location.pathname)) return <AppointmentShell nav={nav}>{children}</AppointmentShell>;
  return <div className="bookings-workspace">
    <div className="bookings-main"><header className="bookings-heading"><div><p className="sr-only">{eyebrow}</p><h1>{title}</h1><nav className="booking-workflow-tabs" aria-label="Sales and scheduling">{workflow.filter(item=>canAccessRoute(item.to.split('?')[0],user?.role,user?.is_superuser)).map(({label,to,icon:Icon})=><Link key={label} to={to} aria-current={location.pathname===to.split('?')[0]?'page':undefined}><Icon size={16}/>{label}</Link>)}</nav><span>{subtitle}</span></div>{actions && <div className="bookings-heading-actions">{actions}</div>}</header><details className="bookings-more"><summary><Settings2 size={14}/> More · setup &amp; management</summary><nav aria-label="Booking workspace navigation">{nav.map(({ label, icon: Icon, active, to, onClick }) => to ? <Link key={label} className="bookings-rail-item" aria-current={active ? 'page' : undefined} to={to}><Icon size={16}/>{label}</Link> : <button key={label} type="button" className="bookings-rail-item" aria-pressed={active} onClick={onClick}><Icon size={16}/>{label}</button>)}</nav></details><div className="bookings-content">{children}</div></div>
  </div>;
}
