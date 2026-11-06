import React from 'react';
import ReactDOM from 'react-dom/client';
import { MemoryRouter, Routes, Route, Link } from 'react-router-dom';
import { useAuthStore } from '../../src/store/authStore';
import EngagementWorkspace from '../../src/apps/crm/EngagementWorkspace';
import CRMReportDirectory from '../../src/apps/crm/CRMReportDirectory';
import '../../src/index.css';

useAuthStore.setState({user:{id:7,email:'conversations@example.test',role:'admin',is_superuser:true},accessToken:'qa',isAuthenticated:true});
ReactDOM.createRoot(document.getElementById('root')!).render(<MemoryRouter initialEntries={['/crm/meetings']}><Routes><Route path="/crm/meetings" element={<EngagementWorkspace key="meetings" kind="meetings"/>}/><Route path="/crm/calls" element={<EngagementWorkspace key="calls" kind="calls"/>}/><Route path="/crm/reports" element={<CRMReportDirectory/>}/></Routes><Link to="/crm/reports">Reports</Link></MemoryRouter>);
