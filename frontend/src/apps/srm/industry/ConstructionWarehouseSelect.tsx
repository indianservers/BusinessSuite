import { useEffect, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import SmartRecordPicker from '@/shared/records/SmartRecordPicker';
import { api } from '@/services/api';
import { useRecordScope } from '@/lib/record-scope';
import { dealError } from '@/apps/crm/deals/deal-utils';

type Warehouse = { id: number; name: string };

export default function ConstructionWarehouseSelect({ value, onChange }: { value: string; onChange: (id: string) => void }) {
  const scope = useRecordScope();
  return <ScopedWarehouseSelect key={scope} scope={scope} value={value} onChange={onChange} />;
}

function ScopedWarehouseSelect({ scope, value, onChange }: { scope: string; value: string; onChange: (id: string) => void }) {
  const [search, setSearch] = useState(''), [term, setTerm] = useState(''), [offset, setOffset] = useState(0);
  const [items, setItems] = useState<Warehouse[]>([]), [selected, setSelected] = useState<Warehouse>();
  useEffect(() => {
    const timer = setTimeout(() => { setTerm(search.trim()); setOffset(0); }, 250);
    return () => clearTimeout(timer);
  }, [search]);
  const query = useQuery({
    queryKey: ['construction-material-warehouse-options', scope, term, offset], retry: false,
    queryFn: async ({ signal }) => (await api.get<{ items: Warehouse[]; has_more: boolean }>('/srm/industry/material-warehouse-options', {
      params: { search: term, offset }, signal,
    })).data,
  });
  useEffect(() => {
    if (query.data) setItems(previous => offset === 0 ? query.data.items : [...new Map([...previous, ...query.data.items].map(item => [item.id, item])).values()]);
  }, [query.data, offset]);
  const current = selected && String(selected.id) === value ? selected : items.find(item => String(item.id) === value);
  const option = (record: Warehouse) => ({ id: String(record.id), label: record.name, record });
  return <SmartRecordPicker name="Warehouse" value={value} search={search} onSearch={text => setSearch(text.slice(0, 180))}
    items={items.map(option)} selected={current ? option(current) : undefined}
    onSelect={record => { setSelected(record); onChange(String(record.id)); setSearch(''); }}
    onClear={() => { setSelected(undefined); onChange(''); setSearch(''); }} loading={query.isFetching}
    error={query.isError ? dealError(query.error) : undefined} retry={() => void query.refetch()}
    hasMore={!!query.data?.has_more && offset < 100000} loadMore={() => setOffset(previous => previous + 50)} />;
}
