import React from 'react';
import ReactDOM from 'react-dom/client';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { useAuthStore } from '../../src/store/authStore';
import TemplateStudio from '../../src/apps/crm/templates/TemplateStudio';
import '../../src/index.css';

useAuthStore.setState({user: {id: 7, email: 'gallery@example.test', role: 'admin', is_superuser: true}, accessToken: 'qa', isAuthenticated: true});
const client = new QueryClient({defaultOptions: {queries: {retry: false}}});
ReactDOM.createRoot(document.getElementById('root')!).render(<MemoryRouter initialEntries={['/crm/email-templates']}><QueryClientProvider client={client}><TemplateStudio/></QueryClientProvider></MemoryRouter>);
