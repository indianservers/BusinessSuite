import '../src/index.css';
import React from 'react';
import {createRoot} from 'react-dom/client';
import {QueryClient,QueryClientProvider} from '@tanstack/react-query';
import {MemoryRouter} from 'react-router-dom';
import Page from '../src/apps/crm/UniversalContactsPage';
createRoot(document.getElementById('root')!).render(<QueryClientProvider client={new QueryClient()}><MemoryRouter><Page/></MemoryRouter></QueryClientProvider>);
