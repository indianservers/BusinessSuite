import React from 'react';
import {createRoot} from 'react-dom/client';
import {QueryClient, QueryClientProvider} from '@tanstack/react-query';
import {EmployeePlannedServicesBrowser} from '@/apps/hrms/pages/employees/EmployeePlannedServices';
import {useAuthStore} from '@/store/authStore';
import '@/index.css';

sessionStorage.setItem('suite-organization', '1');
sessionStorage.setItem('suite-branch', '1');
function authority(employee_id: number) {
  useAuthStore.setState({isAuthenticated: true, isHydrated: true, accessToken: 'fixture', user: {
    id: 77, employee_id, email: 'fixture@example.invalid', role: 'employee',
    access: {companyId: 1, managed: true, memberships: [1], permissions: ['employee_view'],
      grants: {hrms: {enabled: true, role: 'employee', scope: 'own', permissions: ['employee_view'], actions: ['view']}}},
  } as never});
}
authority(900);
const client = new QueryClient({defaultOptions: {queries: {retry: false}}});
Object.assign(window, {plannedServiceAuthority: authority, refreshPlannedServices: () => client.invalidateQueries()});
function Screen() {
  const employeeId = useAuthStore(state => state.user?.employee_id);
  return <EmployeePlannedServicesBrowser defaultEmployeeId={employeeId || undefined} canBrowse/>;
}
createRoot(document.getElementById('root')!).render(<QueryClientProvider client={client}><Screen/></QueryClientProvider>);
