import { useLocation } from 'react-router-dom';
import { useState, useSyncExternalStore } from 'react';

import { useQueryClient } from '@tanstack/react-query';

import { recordCache } from './integration';

export default function CacheDiagnostics() {

  const [open, setOpen] = useState(false);

  const status = useSyncExternalStore(recordCache.subscribe, recordCache.getSyncStatus);

  const client = useQueryClient();
  const location = useLocation();

  const module = location.pathname.startsWith('/pms') ? 'pms' : location.pathname.startsWith('/crm') ? 'crm' : location.pathname.startsWith('/srm') ? 'sales' : 'hrms';

  return <aside aria-label="Cache and sync diagnostics" style={{ position: 'fixed', bottom: 8, left: 8, zIndex: 80, background: 'hsl(var(--card))', color: 'hsl(var(--foreground))', border: '1px solid hsl(var(--border))', borderRadius: 8, padding: 8, maxWidth: 310, fontSize: 12 }}>

    <button onClick={() => setOpen(!open)} aria-expanded={open}>Cache & sync · {status.health}</button>

    {open && <><dl style={{ display: 'grid', gridTemplateColumns: '1fr auto', gap: '3px 12px', margin: '8px 0' }}>

      {Object.entries({ 'IndexedDB storage': `${(status.diskBytes / 1024).toFixed(1)} KB`, 'Hit rate': `${status.hits + status.misses ? Math.round(status.hits / (status.hits + status.misses) * 100) : 0}%`, 'Memory storage': `${(status.bytes / 1024).toFixed(1)} KB`, 'Cached views': status.views, 'Cache hits / misses': `${status.hits} / ${status.misses}`, 'API calls avoided': status.avoided, 'Sync checks': status.requests, 'API network requests': status.networkRequests, 'Rows changed': status.updated, 'Checks pending': status.pending, 'Last sync': status.lastSync ? new Date(status.lastSync).toLocaleTimeString() : 'Never', 'Failed checks': status.failures }).map(([key, value]) => <div key={key} style={{ display: 'contents' }}><dt>{key}</dt><dd>{value}</dd></div>)}

    </dl><p role="status">{status.error}</p><button onClick={() => void recordCache.syncModuleChanges(module, true)}>Refresh current view</button><br/><button onClick={() => void recordCache.invalidateCache(module).then(() => client.invalidateQueries({ type: 'active' }))}>Clear {module} cache</button><p>Development only · Record contents are never shown.</p></>}

  </aside>;

}
