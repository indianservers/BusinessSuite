import { useState } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import { api } from '@/services/api';
import { useRecordScope } from '@/lib/record-scope';
import { useRecordScopeOwner } from '@/hooks/use-record-scope-owner';
import { Button } from '@/components/ui/button';
import { dealError } from '@/apps/crm/deals/deal-utils';
import POSServiceScheduling, { type BookingSelection } from './POSServiceScheduling';

type Row = { id: number; title: string; kind: string; status: string; revision: number; created_by: number; customer_id?: number; invoice_id?: number; data: Record<string, string | number | number[]> };
type Schedule = { service_id?: number; provider_timezone?: string; appointment_id: number; appointment_revision: number; occurrence_id: number; occurrence_revision: number; booking: BookingSelection; additional_resource_ids: number[] };
type Props = { row: Row; serviceId?: number; resources?: Row[]; saved: (row: Row) => Promise<void> };
const additionalTypes = new Set(['room', 'chair', 'equipment', 'location']);
function scheduleTime(booking: BookingSelection, zone?: string) {
  if (!zone) return '';
  try {
    const format = new Intl.DateTimeFormat(undefined, { timeZone: zone, year: 'numeric', month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit', timeZoneName: 'short' });
    const start = Date.parse(booking.starts_at);
    return `${format.format(start)} – ${format.format(start + booking.duration_minutes * 60000)} (${zone})`;
  } catch { return ''; }
}

export default function GroupedServiceReschedule(props: Props) {
  const scope = useRecordScope();
  return <GroupedSchedule key={`${scope}:${props.row.id}:${props.row.revision}`} {...props} scope={scope}/>;
}

function GroupedSchedule({ row, serviceId, resources = [], saved, scope }: Props & { scope: string }) {
  const [reload, setReload] = useState(0);
  const owns = useRecordScopeOwner();
  const query = useQuery({ queryKey: ['grouped-service-schedule', scope, row.id, row.revision], retry: false,
    refetchOnWindowFocus: false, queryFn: ({ signal }) => api.get<Schedule>(`/srm/service-checkout/appointments/${row.id}/schedule`, { signal }).then(response => response.data) });
  return <details className="rounded-md border p-3"><summary className="cursor-pointer text-sm">Reschedule</summary>
    <div className="mt-3 space-y-3">
      {query.isPending && <p role="status">Loading current service schedule…</p>}
      {query.isError && <p role="alert">{dealError(query.error)}</p>}
      {query.data && <ScheduleDraft key={reload} initial={query.data} row={row} resources={resources} saved={saved} serviceId={serviceId}/>}
      <Button type="button" size="sm" variant="outline" disabled={query.isFetching} onClick={() => {
        void query.refetch().then(result => { if (owns() && result.isSuccess) setReload(value => value + 1); });
      }}>Reload current schedule</Button>
      <p className="text-xs text-muted-foreground">Reload replaces this draft with the current appointment schedule.</p>
    </div>
  </details>;
}

function ScheduleDraft({ initial, row, serviceId, resources = [], saved }: Props & { initial: Schedule }) {
  const [held] = useState(initial);
  const [booking, setBooking] = useState<BookingSelection | undefined>(initial.booking);
  const [additional, setAdditional] = useState(initial.additional_resource_ids);
  const owns = useRecordScopeOwner();
  const product = held.service_id || serviceId || Number(row.data.service_id);
  const choices = resources.filter(resource => additionalTypes.has(String(resource.data.resource_type)));
  const heldTime = scheduleTime(held.booking, held.provider_timezone);
  const missing = additional.filter(id => !choices.some(resource => resource.id === id));
  const mutation = useMutation({ mutationFn: async () => {
    if (!booking || !owns()) throw new Error('Apply current booking details before saving.');
    return (await api.post<{ appointment: Row; schedule: Schedule }>(`/srm/service-checkout/appointments/${row.id}/schedule`, {
      expected_appointment_revision: held.appointment_revision, expected_occurrence_revision: held.occurrence_revision,
      booking, additional_resource_ids: additional,
    })).data;
  }, onSuccess: async response => { if (owns()) await saved(response.appointment); } });
  if (!Number.isSafeInteger(product) || product <= 0) return <p role="alert">The service for this appointment could not be verified. Reload the current schedule.</p>;
  return <form className="grid gap-3" aria-label="Reschedule booked service" onSubmit={event => { event.preventDefault(); mutation.mutate(); }}>
    {heldTime && <p className="text-sm">Current schedule: {heldTime}</p>}
    <p className="text-xs text-muted-foreground">Choose fresh booking details for this service. Saving updates its planned appointment.</p>
    <POSServiceScheduling productId={product} lineKey={`reschedule-${row.id}`} value={booking} onChange={setBooking} context="reschedule"/>
    {(choices.length > 0 || missing.length > 0) && <fieldset className="grid gap-2"><legend className="mb-2 text-sm">Additional rooms and equipment</legend>
      {choices.map(resource => <label key={resource.id} className="flex gap-2 text-sm"><input type="checkbox" checked={additional.includes(resource.id)} disabled={mutation.isPending} onChange={event => setAdditional(previous => event.target.checked ? [...previous, resource.id] : previous.filter(id => id !== resource.id))}/>{resource.title}</label>)}
      {missing.map(id => <label key={id} className="flex gap-2 text-sm"><input type="checkbox" checked disabled={mutation.isPending} onChange={() => setAdditional(previous => previous.filter(value => value !== id))}/>Current resource #{id}</label>)}
    </fieldset>}
    <Button type="submit" disabled={!booking || mutation.isPending}>{mutation.isPending ? 'Saving schedule…' : 'Save new schedule'}</Button>
    {mutation.isError && <p role="alert">{dealError(mutation.error)} Your draft is retained. Review it or reload the current schedule before retrying.</p>}
  </form>;
}
