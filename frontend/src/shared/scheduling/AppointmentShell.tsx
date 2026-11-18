import type { ReactNode } from 'react';
import type { SchedulingNav } from './SchedulingFrame';
/** Navigation is supplied by AppLayout, shared with scheduling and POS. */
export default function AppointmentShell({nav,children}:{nav:SchedulingNav[];children:ReactNode}){
 const resources=nav.some(item=>item.active&&/resources/i.test(item.label));
 return <div className="appointment-reference-shell appointment-standard-shell"><div className="appointment-reference-body"><div className={`appointment-reference-content ${resources?'is-resources':'is-schedule'}`}><h1 className="text-xl font-semibold mb-3">{resources?'Available resources':'Schedule'}</h1><nav className="flex flex-wrap gap-2 mb-3" aria-label="Appointment views">{nav.filter(item=>item.onClick).map(item=><button type="button" key={item.label} className="rounded-lg border px-3 py-2 text-sm" aria-pressed={!!item.active} onClick={item.onClick}>{item.label}</button>)}</nav>{children}</div></div></div>;
}
