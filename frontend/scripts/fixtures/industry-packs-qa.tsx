import ReactDOM from 'react-dom/client';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import IndustryPackOnboarding from '../../src/apps/crm/templates/IndustryPackOnboarding';
import { useAuthStore } from '../../src/store/authStore';
import '../../src/index.css';
useAuthStore.setState({ user: { id: 1, email: 'admin@example.test', role: 'admin', is_superuser: true }, accessToken: null, isAuthenticated: true });
const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
ReactDOM.createRoot(document.getElementById('root')!).render(<MemoryRouter><QueryClientProvider client={client}><IndustryPackOnboarding packKey="salon-spa" open close={() => {}} onInstalled={() => {}} /></QueryClientProvider></MemoryRouter>);
