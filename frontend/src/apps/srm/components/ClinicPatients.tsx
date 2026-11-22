import { useEffect, useRef, useState } from 'react';
import { useInfiniteQuery, useQuery, useQueryClient } from '@tanstack/react-query';
import { dealError } from '@/apps/crm/deals/deal-utils';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { accessQueryOptions } from '@/features/access/access-query';
import type { BusinessPackDiscovery } from '@/lib/business-pack-types';
import { selectedPackContext } from '@/lib/pack-context';
import { useRecordScope } from '@/lib/record-scope';
import { api } from '@/services/api';
import { useDebounced } from '@/shared/master-data/CompanySelect';
import { POSQuickAddCustomer, type POSFeatures } from './POSBasicCustomer';
import type { PosCustomerRecord } from './QuickAddCustomer';

export function usePatientWorkspace(enabled = true) {
  const scope = useRecordScope();
  const selector = selectedPackContext();
  const branch = sessionStorage.getItem('suite-branch');
  const query = useQuery({ ...accessQueryOptions(), enabled: enabled && !!branch && branch !== 'all' });
  const discovery = (query.data as { businessPacks?: BusinessPackDiscovery } | undefined)?.businessPacks;
  const choices = discovery?.contexts.filter(choice => choice.branchId === Number(branch)) ?? [];
  const context = selector === null
    ? (choices.length === 1 ? choices[0] : undefined)
    : (discovery?.selectionState === 'verified' && discovery.selectedContextId === Number(selector)
      ? choices.find(choice => String(choice.contextId) === selector)
      : undefined);
  return {
    scope,
    loading: enabled && !!branch && branch !== 'all' && query.isPending,
    hospital: enabled && discovery?.state === 'ready' && !discovery.hasMore && discovery.selectionState !== 'invalid' && context?.packKey === 'hospital',
  };
}

type PatientPage = { items: PosCustomerRecord[]; next: number | null; features: POSFeatures };

type PatientProps = {
  selected?: string;
  onSelect?: (patient: PosCustomerRecord) => void;
  onResolved?: (patient: PosCustomerRecord) => void;
};

export default function ClinicPatients({ selected, onSelect, onResolved }: PatientProps) {
  const scope = useRecordScope();
  const cache = useQueryClient();
  const listKey = ['clinic-patients', scope];
  const [search, setSearch] = useState('');
  const [adding, setAdding] = useState(false);
  const needle = useDebounced(search.trim());
  const query = useInfiniteQuery({
    queryKey: [...listKey, needle],
    initialPageParam: 0,
    queryFn: ({ signal, pageParam }) => api.get<PatientPage>('/srm/pos/customers', {
      signal, params: { after: pageParam, search: needle }, recordCache: false,
    }).then(result => result.data),
    getNextPageParam: page => page.next ?? undefined,
    retry: false,
  });
  const current = useQuery({
    queryKey: ['clinic-patient', scope, selected],
    enabled: !!selected,
    queryFn: ({ signal }) => api.get<PosCustomerRecord>(`/srm/pos/customers/${selected}`, {
      signal, recordCache: false,
    }).then(result => result.data),
    retry: false,
  });
  const resolved = useRef(onResolved);
  resolved.current = onResolved;
  useEffect(() => {
    if (current.data) resolved.current?.(current.data);
  }, [current.data]);
  const features = query.data?.pages[0]?.features;
  const patients = query.data?.pages.flatMap(page => page.items) ?? [];
  return <section aria-label="Patients" className="space-y-4 p-4">
    {!onSelect && <h1 className="text-xl font-semibold">Patients</h1>}
    {current.data && <p>Selected patient: <strong>{current.data.name}</strong></p>}
    {current.isError && <p role="alert">{dealError(current.error)}</p>}
    <div className="flex flex-wrap items-end gap-3">
      <label className="min-w-48 flex-1">Search patients
        <Input value={search} onChange={event => setSearch(event.target.value)} maxLength={100} placeholder="Name or phone number"/>
      </label>
      {features?.customers_register && <Button type="button" onClick={() => setAdding(true)}>Register patient</Button>}
    </div>
    {query.isPending && <p role="status">Loading patients…</p>}
    {query.isError && <p role="alert">{dealError(query.error)} <Button type="button" variant="outline" onClick={() => void query.refetch()}>Retry</Button></p>}
    {features?.registration_unavailable_reason && <p role="status">{features.registration_unavailable_reason}</p>}
    {query.isSuccess && !patients.length && <p>No patients found.</p>}
    <ul className="divide-y">{patients.map(patient => <li key={patient.id} className="py-3">
      {onSelect ? <Button type="button" variant="outline" onClick={() => onSelect(patient)}>{patient.name}</Button> : <strong>{patient.name}</strong>}
      {patient.phone && <p>{patient.phone_country_code} {patient.phone}</p>}
      {patient.email && <p>{patient.email}</p>}
    </li>)}</ul>
    {query.hasNextPage && <Button type="button" variant="outline" disabled={query.isFetchingNextPage} onClick={() => void query.fetchNextPage()}>Load more patients</Button>}
    {adding && features && <POSQuickAddCustomer features={features} patient onClose={() => setAdding(false)} onCreated={patient => {
      setAdding(false);
      setSearch('');
      onSelect?.(patient);
      void cache.invalidateQueries({ queryKey: listKey });
    }}/>}
  </section>;
}
