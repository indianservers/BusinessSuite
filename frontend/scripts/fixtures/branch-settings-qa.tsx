import React from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import BranchSettings from '../../src/pages/settings/BranchSettings';
import BranchSwitcher from '../../src/components/suite/BranchSwitcher';
import { useAuthStore } from '../../src/store/authStore';
import '../../src/index.css';

useAuthStore.getState().setUser({id: 1, email: 'qa@example.test', role: 'admin', is_superuser: true});
createRoot(document.getElementById('root')!).render(<BrowserRouter><QueryClientProvider client={new QueryClient({defaultOptions:{queries:{retry:false}}})}><BranchSwitcher/><BranchSettings/></QueryClientProvider></BrowserRouter>);
