import React from 'react';
import {createRoot} from 'react-dom/client';
import {BrowserRouter} from 'react-router-dom';
import {QueryClient, QueryClientProvider} from '@tanstack/react-query';
import BranchSwitcher from '../../src/components/suite/BranchSwitcher';
import {WorkspaceDirectoryMenu} from '../../src/shared/workspace/WorkspaceDirectoryMenu';
import {useAuthStore, type AuthUser} from '../../src/store/authStore';
import '../../src/index.css';
sessionStorage.setItem('suite-organization', '1');
sessionStorage.setItem('suite-branch', 'all');
const companyAdmin = new URLSearchParams(location.search).has('company');
useAuthStore.getState().setUser({id:companyAdmin?2:1,email:'admin@example.test',role:'admin',is_superuser:!companyAdmin,
  access:{companyId:1,isAccessAdmin:true,managed:false,grants:{},modules:[],memberships:[1],isGlobalAdmin:!companyAdmin}} as AuthUser);
createRoot(document.getElementById('root')!).render(<BrowserRouter><QueryClientProvider client={new QueryClient({defaultOptions:{queries:{retry:false}}})}><BranchSwitcher/><WorkspaceDirectoryMenu/></QueryClientProvider></BrowserRouter>);
