import React from 'react';
import {createRoot} from 'react-dom/client';
import {QueryClient,QueryClientProvider} from '@tanstack/react-query';
import {MemoryRouter} from 'react-router-dom';
import {useAuthStore} from '../src/store/authStore';
import CompaniesPage from '../src/shared/master-data/CompaniesPage';
import '../src/index.css';
useAuthStore.setState({user:{id:1,email:'qa@example.test',role:'admin',is_superuser:true},isAuthenticated:true,isHydrated:true});
createRoot(document.getElementById('root')!).render(<QueryClientProvider client={new QueryClient()}><MemoryRouter><CompaniesPage role="Customer"/></MemoryRouter></QueryClientProvider>);
