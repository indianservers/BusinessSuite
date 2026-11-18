import type { ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { CalendarDays, CalendarRange, CheckCheck, Clock3, DoorOpen, Layers3, Settings2, ShoppingCart, UsersRound, type LucideIcon } from 'lucide-react';
import './scheduling-workspace.css';

export type SchedulingNav = { label: string; icon: LucideIcon; active?: boolean; to?: string; onClick?: () => void };
export const schedulingIcons = { calendar: CalendarDays, timeline: CalendarRange, guide: Settings2, resources: DoorOpen, services: Layers3, employees: UsersRound, pos: ShoppingCart, time: Clock3 };

/** The module sidebar remains global; this rail contains only booking operations. */
export default function SchedulingFrame({ title, subtitle, nav, children, actions, eyebrow = 'BOOKINGS WORKSPACE' }: {
  title: string; subtitle: string; nav: SchedulingNav[]; children: ReactNode; actions?: ReactNode; eyebrow?: string;
}) {
  return <div className="bookings-workspace">
    <aside className="bookings-rail" aria-label="Booking workspace navigation">
      <div className="bookings-brand"><span><CalendarDays size={21}/></span><div><strong>Bookings</strong><small>People. Services. Time.</small></div></div>
      <p className="bookings-rail-label">WORKSPACE</p>
      <nav>{nav.map(({ label, icon: Icon, active, to, onClick }) => to
        ? <Link key={label} className={`bookings-rail-item ${active ? 'is-active' : ''}`} aria-current={active ? 'page' : undefined} to={to}><Icon size={17}/><span>{label}</span></Link>
        : <button key={label} type="button" className={`bookings-rail-item ${active ? 'is-active' : ''}`} aria-pressed={active} onClick={onClick}><Icon size={17}/><span>{label}</span></button>)}</nav>
      <div className="bookings-rail-note"><CheckCheck size={18}/><p>One connected schedule<small>Employee categories and resources stay connected to HRMS.</small></p></div>
    </aside>
    <div className="bookings-main"><header className="bookings-heading"><div><p>{eyebrow}</p><h1>{title}</h1><span>{subtitle}</span></div>{actions && <div className="bookings-heading-actions">{actions}</div>}</header><div className="bookings-content">{children}</div></div>
  </div>;
}
