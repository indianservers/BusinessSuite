/** Isolated QA shell; record pages and APIs are the production components. */
import React from 'react';
import ReactDOM from 'react-dom/client';
import {MemoryRouter, Routes, Route, Link} from 'react-router-dom';
import {QueryClient, QueryClientProvider} from '@tanstack/react-query';
import CRMRecordDetailPage from '../../src/apps/crm/CRMRecordDetailPage';
import Deal360Page from '../../src/apps/crm/deals/Deal360Page';
import SharedInvoicePage from '../../src/apps/srm/pages/SharedInvoicePage';
import '../../src/index.css';

const records = (window as Window & {__TEMPLATE_RECORDS__:Record<string,number>}).__TEMPLATE_RECORDS__;
const client = new QueryClient({defaultOptions:{queries:{retry:false}}});
const destinations = [['lead','Leads','/crm/leads/'],['contact','Contacts','/crm/contacts/'],['account','Accounts','/crm/accounts/'],['deal','Deals','/crm/deals/'],['invoice','Invoices','/srm/invoices/']];
ReactDOM.createRoot(document.getElementById('root')!).render(<MemoryRouter initialEntries={[`/crm/leads/${records.lead}`]}><QueryClientProvider client={client}>
  <nav aria-label="Template QA records" style={{display:'flex',flexWrap:'wrap',gap:20,padding:16,borderBottom:'1px solid #ddd'}}>{destinations.map(([entity,label,path])=><Link key={entity} to={path+records[entity]}>{label}</Link>)}</nav>
  <div style={{padding:16}}><Routes>
    <Route path="/crm/leads/:id" element={<CRMRecordDetailPage kind="leads"/>}/>
    <Route path="/crm/contacts/:id" element={<CRMRecordDetailPage kind="contacts"/>}/>
    <Route path="/crm/accounts/:id" element={<CRMRecordDetailPage kind="accounts"/>}/>
    <Route path="/crm/deals/:id" element={<Deal360Page/>}/>
    <Route path="/srm/invoices/:id" element={<SharedInvoicePage/>}/>
  </Routes></div>
</QueryClientProvider></MemoryRouter>);
