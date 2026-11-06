import ReactDOM from 'react-dom/client';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import CustomizationStudioPage from '../../src/apps/customization/CustomizationStudioPage';
import { useAuthStore } from '../../src/store/authStore';
import '../../src/index.css';

useAuthStore.setState({ user: { id: 1, email: 'qa@example.test', role: 'admin', is_superuser: true }, isAuthenticated: true });
const client = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: 0 } } });
ReactDOM.createRoot(document.getElementById('root')!).render(<MemoryRouter initialEntries={['/admin/customization/modules']}><QueryClientProvider client={client}><CustomizationStudioPage /></QueryClientProvider></MemoryRouter>);
