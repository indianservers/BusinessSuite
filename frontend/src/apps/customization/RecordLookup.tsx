import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { api } from '@/services/api';
import { Input } from '@/components/ui/input';
import { NativeSelect } from '@/components/ui/native-select';

export default function RecordLookup({ module, value, onChange, disabled, label }: {
  module: string; value: unknown; onChange: (value: unknown) => void; disabled?: boolean; label: string;
}) {
  const [search, setSearch] = useState('');
  const choices = useQuery({ queryKey: ['custom-record-lookup', module, search], enabled: !!module,
    queryFn: ({ signal }) => api.get<{ items: { id: number; values_json: Record<string, unknown> }[] }>(`/custom/${encodeURIComponent(module)}`, { params: { search, per_page: 25 }, signal }).then(r => r.data.items) });
  return <div className="space-y-2">
    <Input aria-label={`Search ${label}`} placeholder="Search records…" disabled={disabled || !module} value={search} onChange={e => setSearch(e.target.value)} />
    <NativeSelect aria-label={label} disabled={disabled || !module || choices.isPending || choices.isError} value={String(value ?? '')} onChange={e => onChange(e.target.value ? Number(e.target.value) : null)}>
      <option value="">Select a record</option>
      {value != null && !choices.data?.some(r => r.id === Number(value)) && <option value={String(value)}>Record #{String(value)}</option>}
      {choices.data?.map(r => <option key={r.id} value={r.id}>{String(Object.values(r.values_json).find(v => typeof v === 'string' && v.trim()) || `Record #${r.id}`)} · #{r.id}</option>)}
    </NativeSelect>
    {choices.isError && <p role="alert" className="text-sm text-destructive">Records could not be loaded. Search again to retry.</p>}
  </div>;
}
