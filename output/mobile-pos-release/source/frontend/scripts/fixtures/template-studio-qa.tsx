/** Development-only preview using the production studio and authenticated API. */
import React from 'react';
import ReactDOM from 'react-dom/client';
import {MemoryRouter} from 'react-router-dom';
import {QueryClient, QueryClientProvider} from '@tanstack/react-query';
import TemplateStudio from '../../src/apps/crm/templates/TemplateStudio';
import '../../src/index.css';

const client = new QueryClient({defaultOptions:{queries:{retry:false}}});
ReactDOM.createRoot(document.getElementById('root')!).render(<MemoryRouter initialEntries={['/crm/templates']}><QueryClientProvider client={client}><TemplateStudio/></QueryClientProvider></MemoryRouter>);
