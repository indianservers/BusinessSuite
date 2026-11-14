import { useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import { api } from '@/services/api';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { writeClipboard } from '@/lib/clipboard';
import { dealError } from '@/apps/crm/deals/deal-utils';
import { useBusinessTerms } from '@/hooks/use-business-terms';

type Link = { id: number; url: string; expires_at: string };
export default function AppointmentBookingLink({ customerId, serviceId, resourceIds, durationMinutes, workspaceId }: {
  customerId: number; serviceId: number; resourceIds: number[]; durationMinutes: number; workspaceId?: string;
}) {
  const { term } = useBusinessTerms();
  const [expires, setExpires] = useState('168');
  const [link, setLink] = useState<Link>();
  const [notice, setNotice] = useState('');
  const [revoked, setRevoked] = useState(false);
  const mutation = useMutation({ mutationFn: async (action: 'create' | 'revoke') => {
    if (action === 'revoke' && link) { await api.post(`/srm/industry/booking-links/${link.id}/revoke`); return undefined; }
    return (await api.post<Link>('/srm/industry/booking-links', { customer_id: customerId, service_id: serviceId,
      resource_ids: resourceIds, duration_minutes: durationMinutes, expires_hours: Number(expires), workspace_id: workspaceId || null })).data;
  }, onSuccess: (value, action) => {
    if (action === 'create') { setLink(value); setRevoked(false); setNotice('Private booking link created.'); }
    else { setRevoked(true); setNotice('Booking link revoked.'); }
  } });
  const valid = customerId > 0 && serviceId > 0 && resourceIds.length > 0 && durationMinutes >= 5 && durationMinutes <= 720;
  return <section className="grid gap-3 rounded border p-3" aria-label="Private appointment booking link">
    <h3 className="font-medium">Let the {term('customer').toLowerCase()} choose a time</h3>
    <p className="text-sm text-muted-foreground">Choose the {term('customer').toLowerCase()}, {term('service').toLowerCase()}, {term('provider').toLowerCase()} and duration above. This private link allows one booking without another login.</p>
    <label className="text-sm">Link validity<select className="ml-2 rounded border bg-background p-2" aria-label="Booking link validity" disabled={mutation.isPending} value={expires} onChange={event => setExpires(event.target.value)}><option value="24">1 day</option><option value="72">3 days</option><option value="168">7 days</option></select></label>
    <div className="flex flex-wrap gap-2"><Button type="button" variant="outline" disabled={!valid || mutation.isPending} onClick={() => { setNotice(''); mutation.mutate('create'); }}>Create private booking link</Button>{link && !revoked && <Button type="button" variant="outline" disabled={mutation.isPending} onClick={() => mutation.mutate('revoke')}>Revoke link</Button>}</div>
    {link && !revoked && <><Input readOnly aria-label="Private booking URL" value={link.url}/><div className="flex flex-wrap items-center gap-3 text-sm"><Button type="button" variant="outline" onClick={() => void writeClipboard(link.url).then(() => setNotice('Booking link copied.'), () => setNotice('Select and copy the booking URL.'))}>Copy link</Button><a href={link.url} target="_blank" rel="noopener noreferrer" className="underline">Preview booking page</a><span>Expires {new Date(link.expires_at).toLocaleString()}</span></div><p className="text-xs text-muted-foreground">Share only with the selected {term('customer').toLowerCase()}. Current availability and charges are checked again when they book.</p></>}
    {notice && <p role="status">{notice}</p>}{mutation.isError && <p role="alert">{dealError(mutation.error)}</p>}
  </section>;
}
