import React from 'react';
import {createRoot} from 'react-dom/client';
import {BrowserRouter} from 'react-router-dom';
import {QueryClient,QueryClientProvider} from '@tanstack/react-query';
import {useAuthStore} from '../../src/store/authStore';
import CommunicationHubPage from '../../src/apps/communication/CommunicationHubPage';
import '../../src/index.css';
useAuthStore.setState({user:{id:1,role:'admin',email:'qa@example.invalid',is_superuser:true},accessToken:'isolated-qa'});
createRoot(document.getElementById('root')!).render(<BrowserRouter><QueryClientProvider client={new QueryClient({defaultOptions:{queries:{retry:false}}})}><CommunicationHubPage/></QueryClientProvider></BrowserRouter>);
