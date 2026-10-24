/* Local browser QA entry pages. These use the real React UI and real local API.
 * Start backend/scripts/run_pms_messaging_qa.py and Vite before running this script.
 * No access tokens are written to disk. Never deploy the generated pages.
 */
const fs = require('node:fs');
const path = require('node:path');
const root = path.resolve(__dirname, '..');
const names = [0, 1, 2].map(i => `__pms-messaging-qa-${i}.html`);
if (process.argv.includes('--clean')) {
  for (const name of names) fs.rmSync(path.join(root, name), { force: true });
  process.exit(0);
}
(async () => {
  const vite = new URL(process.env.PMS_QA_VITE_ORIGIN || 'http://127.0.0.1:5176');
  const server = new URL(process.env.PMS_QA_API_ORIGIN || 'http://127.0.0.1:8774');
  for (const origin of [vite, server]) if (!['127.0.0.1', 'localhost'].includes(origin.hostname)) throw Error('QA origins must be loopback addresses');
  const transformed = await (await fetch(new URL('/src/apps/project-management/pages/DirectMessagesPage.tsx', vite))).text();
  const react = transformed.match(/deps\/react\.js\?v=([a-f0-9]+)/)[1];
  const router = transformed.match(/react-router-dom\.js\?v=([a-f0-9]+)/)[1];
  const query = transformed.match(/@tanstack_react-query\.js\?v=([a-f0-9]+)/)[1];
  for (let index = 0; index < 3; index++) {
    const html = `<html><head><meta name="viewport" content="width=device-width,initial-scale=1"></head><body><div id="root"></div>
<script>window.__AI_HRMS_CONFIG__={apiBaseUrl:${JSON.stringify(server.origin + '/api/v1')}};</script>
<script type="module">import RefreshRuntime from '/@react-refresh';RefreshRuntime.injectIntoGlobalHook(window);window.$RefreshReg$=()=>{};window.$RefreshSig$=()=>type=>type;window.__vite_plugin_react_preamble_installed__=true;</script>
<script type="module">
import React from '/node_modules/.vite/deps/react.js?v=${react}';
import ReactDOM from '/node_modules/.vite/deps/react-dom_client.js?v=${react}';
import {BrowserRouter} from '/node_modules/.vite/deps/react-router-dom.js?v=${router}';
import {QueryClient,QueryClientProvider} from '/node_modules/.vite/deps/@tanstack_react-query.js?v=${query}';
import Chat from '/src/apps/project-management/pages/DirectMessagesPage.tsx';
import {usePMSRealtime,useRealtimeStore} from '/src/apps/project-management/realtime.ts';
import {api} from '/src/services/api.ts';import {useAuthStore} from '/src/store/authStore.ts';import {applyTheme} from '/src/store/themeStore.ts';import '/src/index.css';
api.defaults.baseURL=${JSON.stringify(server.origin + '/api/v1')};
api.interceptors.request.use(async c=>{if(location.search.includes('delay')&&c.method==='post'&&c.url?.endsWith('/messages'))await new Promise(r=>setTimeout(r,1500));return c;});
const session=await(await fetch(${JSON.stringify(server.origin + '/qa-session/' + index)})).json();useAuthStore.setState({user:session.user,accessToken:session.token,isAuthenticated:true});applyTheme('light');
function QAChat(){usePMSRealtime({enabled:!location.search.includes('poll-only'),showToast:false});const connected=useRealtimeStore(s=>s.connected);return React.createElement(React.Fragment,null,React.createElement('output',null,location.search.includes('poll-only')?'Polling only':connected?'Realtime connected':'Realtime reconnecting'),React.createElement(Chat));}
ReactDOM.createRoot(document.getElementById('root')).render(React.createElement(QueryClientProvider,{client:new QueryClient({defaultOptions:{queries:{retry:false}}})},React.createElement(BrowserRouter,null,React.createElement(QAChat))));
</script></body></html>`;
    fs.writeFileSync(path.join(root, names[index]), html);
    console.log(new URL('/' + names[index], vite).href);
  }
})().catch(error => { console.error(error.message); process.exit(1); });
