import { Link } from 'react-router-dom';
import { ArrowRight, CalendarDays, ClipboardList, CreditCard, Users } from 'lucide-react';
import { useBusinessTerms } from '@/hooks/use-business-terms';
import { businessProfileCatalog } from '@/lib/business-profile';
import { canAccessRoute } from '@/lib/roles';
import { useAuthStore } from '@/store/authStore';

export default function BusinessWorkspace() {
  const { profile, term, loading } = useBusinessTerms();
  const user = useAuthStore(state => state.user);
  const business = businessProfileCatalog.profiles.find(item => item.id === profile.business_type);
  if (loading || !business || ['general', 'custom'].includes(profile.business_type)) return null;
  const title = business.name.split(' / ')[0];
  const actions = [
    { path: '/srm/appointments', label: term('appointment', true), description: `Schedule, check in and manage ${term('appointment', true).toLowerCase()}.`, icon: CalendarDays },
    { path: '/srm/customers', label: term('customer', true), description: `Manage ${term('customer').toLowerCase()} profiles and shared history.`, icon: Users },
    { path: '/srm/appointments?resources=1', label: `${term('provider', true)} & ${term('resource', true)}`, description: 'Manage staff availability and bookable resources.', icon: ClipboardList },
    { path: '/srm/collections', label: 'Payments & collections', description: 'Track receipts, advances and invoice balances.', icon: CreditCard },
  ];
  if (profile.business_type === 'construction') actions.unshift({ path: '/srm/construction', label: 'Construction operations', description: 'Scope, site work, certification and billing.', icon: ClipboardList });
  if (['retail', 'pharma', 'restaurant'].includes(profile.business_type)) actions.unshift({ path: '/srm/pos', label: 'Sales & checkout', description: 'Sell from the shared catalog and manage stock.', icon: CreditCard });
  if (['construction', 'manufacturing', 'logistics', 'real_estate'].includes(profile.business_type)) actions.unshift({ path: '/pms/projects', label: term('project', true), description: 'Plan delivery, assign work and track progress.', icon: ClipboardList });
  const allowed = actions.filter(action => user && canAccessRoute(action.path.split('?')[0], user.role, user.is_superuser));
  if (!allowed.length) return null;
  return <section data-business-type={profile.business_type} aria-label={`${title} workspace`} className="my-6 rounded-2xl border bg-card p-4 sm:p-6">
    <div className="mb-5"><p className="text-xs font-semibold uppercase tracking-widest text-primary">Your business</p><h2 className="mt-1 text-2xl font-semibold">{title} workspace</h2><p className="mt-2 text-sm text-muted-foreground">{term('customer', true)}, {term('provider', true)}, {term('appointment', true).toLowerCase()} and payments in one connected workspace.</p></div>
    <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">{allowed.map(action => <Link key={action.path} to={action.path} className="group flex min-w-0 gap-3 rounded-xl border p-4 transition-colors hover:bg-muted/50"><action.icon className="mt-1 shrink-0 text-primary" size={22}/><div className="min-w-0"><h3 className="break-words font-semibold">{action.label}</h3><p className="mt-1 text-sm text-muted-foreground">{action.description}</p></div><ArrowRight className="ml-auto mt-1 shrink-0" size={16}/></Link>)}</div>
    <p className="mt-4 text-sm text-muted-foreground">Open a {term('appointment').toLowerCase()} to manage its schedule, visit status, invoice and payments together.</p>
  </section>;
}
