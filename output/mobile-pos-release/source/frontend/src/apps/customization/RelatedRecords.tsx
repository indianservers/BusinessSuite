import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { api } from '@/services/api';
import { Button } from '@/components/ui/button';

export default function RelatedRecords({ module, record, relation, label }: { module: string; record: number; relation: number; label: string }) {
  const [open, setOpen] = useState(false), [page, setPage] = useState(1);
  const result = useQuery({ queryKey: ['custom-related-records', module, record, relation, page], enabled: open,
    queryFn: () => api.get<{ items: { id: number; values_json: Record<string, unknown> }[]; total: number }>(`/custom/${module}/${record}/related/${relation}`, { params: { page, per_page: 10 }, recordCache: false }).then(r => r.data) });
  return <section className="space-y-2"><Button size="sm" variant="outline" onClick={() => setOpen(v => !v)}>{open ? 'Hide' : 'Show'} {label}</Button>{open && <div className="space-y-2 rounded border p-3">
    {result.isPending && <p role="status">Loading {label}…</p>}{result.isError && <p role="alert">Related records could not be loaded.</p>}
    {result.data && <><p className="text-sm">{result.data.total} related records</p>{result.data.items.map(row => <p key={row.id} className="break-words text-sm">#{row.id} · {Object.values(row.values_json).filter(v => v != null && typeof v !== 'object').map(String).join(' · ')}</p>)}<div className="flex flex-wrap gap-2"><Button aria-label="Previous related records" size="sm" variant="outline" disabled={page === 1} onClick={() => setPage(p => p - 1)}>Previous</Button><Button aria-label="Next related records" size="sm" variant="outline" disabled={page * 10 >= result.data.total} onClick={() => setPage(p => p + 1)}>Next</Button></div></>}
  </div>}</section>;
}
