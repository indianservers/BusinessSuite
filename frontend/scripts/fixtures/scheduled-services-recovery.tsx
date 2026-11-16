import React from 'react';
import {MemoryRouter} from 'react-router-dom';
import {createRoot} from 'react-dom/client';
import {QueryClient, QueryClientProvider} from '@tanstack/react-query';
import ScheduledServicesPage from '@/apps/srm/pages/ScheduledServicesPage';
import {useAuthStore} from '@/store/authStore';
import '@/index.css';

sessionStorage.setItem('suite-organization', '1');
sessionStorage.setItem('suite-branch', '1');
useAuthStore.setState({isAuthenticated: true, isHydrated: true, accessToken: 'fixture', user: {
  id: 77, email: 'fixture@example.invalid', role: 'employee',
  access: {companyId: 1, managed: true, memberships: [1], permissions: ['timesheet_view'],
    grants: {hrms: {enabled: true, role: 'employee', scope: 'own', permissions: ['timesheet_view'], actions: ['view']}}},
} as never});
const client = new QueryClient({defaultOptions: {queries: {retry: false}}});
Object.assign(window, {refreshSchedule: () => client.invalidateQueries()});
createRoot(document.getElementById('root')!).render(<MemoryRouter><QueryClientProvider client={client}><ScheduledServicesPage/></QueryClientProvider></MemoryRouter>);
