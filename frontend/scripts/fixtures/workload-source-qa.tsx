/** Development-only native source navigation fixture. No account credentials. */
import React from 'react';
import ReactDOM from 'react-dom/client';
import {MemoryRouter,Link} from 'react-router-dom';
import WorkloadPage from '../../src/apps/project-management/pages/WorkloadPage';
import '../../src/index.css';
if(!import.meta.env.DEV)throw Error('Development fixture only');
ReactDOM.createRoot(document.getElementById('root')!).render(<MemoryRouter initialEntries={['/pms/workload?projectId=7&from=2026-05-04&to=2026-05-17&basis=hours']}>
 <Link to="/pms/workload?projectId=9&from=2026-06-01&to=2026-06-07&basis=hours">Open another workload citation</Link>
 <Link to="/pms/workload?workspace_id=12&from=2026-06-01&to=2026-06-07&basis=hours">Open workspace workload citation</Link>
 <WorkloadPage/>
</MemoryRouter>);
