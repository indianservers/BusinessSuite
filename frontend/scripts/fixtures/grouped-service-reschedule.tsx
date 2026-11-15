import React, { useState } from 'react';
import { createRoot } from 'react-dom/client';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { useAuthStore } from '@/store/authStore';
import GroupedServiceReschedule from '@/apps/srm/industry/GroupedServiceReschedule';
import '@/index.css';

useAuthStore.setState({ isAuthenticated: true, isHydrated: true, accessToken: 'fixture', user: { id: 1, email: 'qa@example.invalid', role: 'super_admin', is_superuser: true } });
sessionStorage.setItem('suite-branch', '1');
function Fixture() {
  const [saved, setSaved] = useState('');
  return <main><GroupedServiceReschedule row={{ id: 17, revision: 3, title: 'Booked service', kind: 'appointment', status: 'booked', created_by: 1, data: { service_id: 9, pos_checkout_id: 1 } }} saved={async row => setSaved(`Saved revision ${row.revision}`)}/><p role="status">{saved}</p></main>;
}
createRoot(document.getElementById('root')!).render(<MemoryRouter><QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><Fixture/></QueryClientProvider></MemoryRouter>);
