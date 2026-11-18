export default function SchedulingBrand() {
  return <svg viewBox="0 0 32 36" width="32" height="36" fill="none" aria-hidden="true" className="scheduling-brand-mark">
    {[3,14,25].map(y=><g key={y}><rect x="2" y={y} width="28" height="8" rx="2" stroke="currentColor" strokeWidth="2.2"/><path d={`M6 ${y+4}h4`} stroke="currentColor" strokeWidth="1.8" strokeLinecap="round"/><circle cx="24.5" cy={y+4} r="1" fill="currentColor"/><circle cx="27" cy={y+4} r="1" fill="currentColor"/></g>)}
  </svg>;
}
