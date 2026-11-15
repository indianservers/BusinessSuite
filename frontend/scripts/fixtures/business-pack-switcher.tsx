import React from 'react';
import { createRoot } from 'react-dom/client';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import BranchSwitcher from '@/components/suite/BranchSwitcher';
import { useAuthStore } from '@/store/authStore';
import { setPackContext } from '@/lib/pack-context';
import '@/index.css';
if (!sessionStorage.getItem('pack-switch-proof')) {
  sessionStorage.setItem('pack-switch-proof', '1'); sessionStorage.setItem('suite-tenant', 'fixture'); sessionStorage.setItem('suite-organization', '1'); sessionStorage.setItem('suite-branch', '1'); setPackContext('11');
  useAuthStore.setState({isAuthenticated:true,isHydrated:true,accessToken:'fixture',user:{id:1,email:'qa@example.invalid',role:'employee',is_superuser:false,access:{companyId:1,grants:{},isAccessAdmin:false}} as never});
}
window.addEventListener('suite:before-context-change', event => { if (sessionStorage.getItem('proof-dirty') === '1') event.preventDefault(); });
createRoot(document.getElementById('root')!).render(<MemoryRouter><QueryClientProvider client={new QueryClient({defaultOptions:{queries:{retry:false,refetchOnWindowFocus:false}}})}><main className="p-3"><BranchSwitcher/></main></QueryClientProvider></MemoryRouter>);
