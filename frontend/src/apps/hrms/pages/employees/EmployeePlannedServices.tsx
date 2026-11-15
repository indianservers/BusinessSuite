import { useDeferredValue, useState } from 'react';
import { useInfiniteQuery, useQuery } from '@tanstack/react-query';
import { isAxiosError } from 'axios';
import { api } from '@/services/api';
import { useRecordScope } from '@/lib/record-scope';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { NativeSelect } from '@/components/ui/native-select';

type PlannedService = {
  appointment_id: number; revision: number; service_id: number | null; service_name: string;
  starts_at: string; ends_at: string; planned_minutes: number; status: string; blocks_availability: boolean;
};
type PlannedServices = {
  employee_id: number; timezone: string; items: PlannedService[]; next_cursor: string | null;
};

function dateText(value: Date) {
  return `${value.getFullYear()}-${String(value.getMonth() + 1).padStart(2, '0')}-${String(value.getDate()).padStart(2, '0')}`;
}

export function EmployeePlannedServicesBrowser({ defaultEmployeeId, canBrowse }: { defaultEmployeeId?: number; canBrowse: boolean }) {
  const scope = useRecordScope();
  return <EmployeeScheduleBrowser key={scope} defaultEmployeeId={defaultEmployeeId} canBrowse={canBrowse} scope={scope}/>;
}

function EmployeeScheduleBrowser({ defaultEmployeeId, canBrowse, scope }: { defaultEmployeeId?: number; canBrowse: boolean; scope: string }) {
  const [readGeneration] = useState(() => crypto.randomUUID());
  const [search, setSearch] = useState(''), deferred = useDeferredValue(search);
  const [selected, setSelected] = useState('');
  const employees = useQuery({
    queryKey: ['planned-service-employee-options', scope, readGeneration, deferred],
    queryFn: ({ signal }) => api.get<{ items: { id: number; full_name: string; employee_id: string }[]; total: number }>('/employees/directory', { signal, recordCache: false, params: { search: deferred || undefined, per_page: 50 } }).then(result => result.data),
    enabled: canBrowse, retry: false, gcTime: 0,
  });
  const employeeId = selected ? Number(selected) : defaultEmployeeId;
  return <div className="space-y-4">
    {canBrowse && <div className="space-y-2 rounded-lg border bg-card p-4">
      <label className="block text-sm">Search employee<Input aria-label="Search planned services employee" value={search} onChange={event => { setSearch(event.target.value); setSelected(''); }}/></label>
      <NativeSelect className="w-full min-w-0" aria-label="Planned services employee" value={selected} loading={employees.isFetching} error={employees.isError} onChange={event => setSelected(event.target.value)}>
        <option value="">{defaultEmployeeId ? 'Use the selected timesheet employee or my profile' : 'Choose an employee'}</option>
        {!employees.isError && employees.data?.items.map(employee => <option key={employee.id} value={employee.id}>{employee.full_name} ({employee.employee_id})</option>)}
      </NativeSelect>
      {employees.isError && <p role="alert" className="text-sm">Employee search could not load. <Button variant="outline" onClick={() => void employees.refetch()}>Retry search</Button></p>}
      {!!employees.data && employees.data.total > employees.data.items.length && <p className="text-xs text-muted-foreground">Showing 50 matches. Refine the search to find another employee.</p>}
    </div>}
    {employeeId ? <EmployeePlannedServices employeeId={employeeId}/> : <p className="text-sm text-muted-foreground">{canBrowse ? 'Choose an employee to see scheduled services.' : 'An employee profile must be linked to view your schedule.'}</p>}
  </div>;
}

/** Booked services are a read-only plan, independent of actual timesheet entries. */
export default function EmployeePlannedServices({ employeeId, packContextId }: { employeeId: number; packContextId?: number }) {
  const scope = useRecordScope();
  return <PlannedServicesPanel key={`${scope}:${employeeId}:${packContextId || ''}`} employeeId={employeeId} packContextId={packContextId} scope={scope}/>;
}

function PlannedServicesPanel({ employeeId, packContextId, scope }: { employeeId: number; packContextId?: number; scope: string }) {
  const [readGeneration] = useState(() => crypto.randomUUID());
  const [from, setFrom] = useState(() => dateText(new Date()));
  const [until, setUntil] = useState(() => { const value = new Date(); value.setDate(value.getDate() + 6); return dateText(value); });
  const start = new Date(`${from}T00:00:00`), end = new Date(`${until}T00:00:00`);
  end.setDate(end.getDate() + 1);
  const valid = Number.isFinite(start.getTime()) && Number.isFinite(end.getTime()) && end > start && end.getTime() - start.getTime() <= 93 * 86400000;
  const query = useInfiniteQuery({
    queryKey: ['employee-planned-services', scope, readGeneration, employeeId, packContextId, from, until],
    initialPageParam: null as string | null,
    getNextPageParam: (lastPage: PlannedServices) => lastPage.next_cursor || undefined,
    queryFn: ({ signal, pageParam }) => api.get<PlannedServices>(`/employees/${employeeId}/planned-services`, {
      signal, recordCache: false, params: { from_at: start.toISOString(), until_at: end.toISOString(), pack_context_id: packContextId, limit: 100, cursor: pageParam || undefined },
    }).then(result => result.data),
    enabled: valid && employeeId > 0, retry: false, gcTime: 0,
  });
  const error = isAxiosError(query.error) && typeof query.error.response?.data?.detail === 'string'
    ? query.error.response.data.detail : 'Scheduled services could not be loaded.';
  const timezone = query.data?.pages[0]?.timezone;
  const items = !query.isError ? query.data?.pages.flatMap(page => page.items) || [] : [];
  const formatter = new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'short', timeZone: timezone || undefined });
  return <Card>
    <CardHeader><CardTitle className="text-base">Planned services</CardTitle><p className="text-sm text-muted-foreground">Scheduled bookings only. Record actual work separately in timesheets.</p></CardHeader>
    <CardContent className="space-y-4">
      <div className="flex flex-wrap gap-3">
        <label className="min-w-0">From<Input aria-label="Planned services from" type="date" value={from} onChange={event => setFrom(event.target.value)}/></label>
        <label className="min-w-0">Through<Input aria-label="Planned services through" type="date" value={until} onChange={event => setUntil(event.target.value)}/></label>
      </div>
      <p className="text-xs text-muted-foreground">Date filters use {Intl.DateTimeFormat().resolvedOptions().timeZone}.</p>
      {!valid && <p role="alert" className="text-sm text-destructive">Choose a date range of up to 93 days.</p>}
      {query.isPending && valid && <p role="status" className="text-sm text-muted-foreground">Loading planned services…</p>}
      {query.isError && <div role="alert" className="space-y-2"><p className="text-sm text-destructive">{error}</p><Button variant="outline" onClick={() => void query.refetch()}>Retry</Button></div>}
      {query.data && !query.isError && <>
        <p className="text-xs text-muted-foreground">Times shown in {timezone || Intl.DateTimeFormat().resolvedOptions().timeZone}.</p>
        {!items.length && <p className="text-sm text-muted-foreground">No scheduled services in this period.</p>}
        <div className="space-y-3">{items.map(item => <article key={item.appointment_id} className="min-w-0 space-y-2 rounded-lg border p-3">
          <div className="flex flex-wrap items-center justify-between gap-2"><strong className="break-words text-sm">{item.service_name}</strong><Badge variant="outline">{item.status.replace(/_/g, ' ')}</Badge></div>
          <p className="text-sm">{formatter.format(new Date(item.starts_at))} – {formatter.format(new Date(item.ends_at))}</p>
          <p className="text-xs text-muted-foreground">{item.planned_minutes} planned minutes{!item.blocks_availability ? ' · Does not reserve availability' : ''}</p>
        </article>)}</div>
        {query.hasNextPage && <Button variant="outline" disabled={query.isFetchingNextPage} onClick={() => void query.fetchNextPage()}>{query.isFetchingNextPage ? 'Loading…' : 'Load more bookings'}</Button>}
      </>}
    </CardContent>
  </Card>;
}
