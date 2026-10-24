/* Loopback-only real UI/API integration harness. No tokens stored on disk. */
const fs = require("node:fs");
const path = require("node:path");
const target = path.resolve(__dirname, "../__commercial-browser-qa.html");
if (process.argv.includes("--clean")) {
  fs.rmSync(target, { force: true });
  process.exit(0);
}
(async () => {
  const origin = new URL(
    process.env.COMMERCIAL_QA_VITE_ORIGIN || "http://127.0.0.1:5176",
  );
  if (!["127.0.0.1", "localhost"].includes(origin.hostname))
    throw Error("Use loopback Vite only");
  const transformed = await (
    await fetch(
      new URL(
        "/src/apps/project-management/pages/ProjectBillingPage.tsx",
        origin,
      ),
    )
  ).text();
  const react = transformed.match(/deps\/react\.js\?v=([a-f0-9]+)/)[1];
  const router = transformed.match(/react-router-dom\.js\?v=([a-f0-9]+)/)[1];
  const query = transformed.match(
    /@tanstack_react-query\.js\?v=([a-f0-9]+)/,
  )[1];
  fs.writeFileSync(
    target,
    `<html><head><meta name="viewport" content="width=device-width,initial-scale=1"></head><body><div id="root"></div>
<script>window.__AI_HRMS_CONFIG__={apiBaseUrl:'http://127.0.0.1:8775/api/v1'};</script>
<script type="module">import RefreshRuntime from '/@react-refresh';RefreshRuntime.injectIntoGlobalHook(window);window.$RefreshReg$=()=>{};window.$RefreshSig$=()=>type=>type;window.__vite_plugin_react_preamble_installed__=true;</script>
<script type="module">
import React from '/node_modules/.vite/deps/react.js?v=${react}';
import ReactDOM from '/node_modules/.vite/deps/react-dom_client.js?v=${react}';
import {MemoryRouter,Routes,Route,Link} from '/node_modules/.vite/deps/react-router-dom.js?v=${router}';
import {QueryClient,QueryClientProvider} from '/node_modules/.vite/deps/@tanstack_react-query.js?v=${query}';
import Billing from '/src/apps/project-management/pages/ProjectBillingPage.tsx';
import Invoice from '/src/apps/srm/pages/SharedInvoicePage.tsx';
import History from '/src/apps/crm/CustomerCommercialHistory.tsx';
import {api} from '/src/services/api.ts';import {useAuthStore} from '/src/store/authStore.ts';import {applyTheme} from '/src/store/themeStore.ts';import '/src/index.css';
api.defaults.baseURL='http://127.0.0.1:8775/api/v1';
const s=await(await fetch('http://127.0.0.1:8775/qa-session')).json();useAuthStore.setState({user:s.user,accessToken:s.token,isAuthenticated:true});applyTheme('light');
const e=React.createElement;
ReactDOM.createRoot(document.getElementById('root')).render(e(QueryClientProvider,{client:new QueryClient({defaultOptions:{queries:{retry:false}}})},e(MemoryRouter,{initialEntries:['/pms/projects/1/billing']},e('main',{className:'mx-auto max-w-6xl p-4'},e('nav',{className:'flex gap-4 pb-5'},e(Link,{to:'/pms/projects/1/billing'},'Project billing'),e(Link,{to:'/crm/history'},'CRM customer history')),e(Routes,null,e(Route,{path:'/pms/projects/:projectId/billing',element:e(Billing)}),e(Route,{path:'/srm/invoices/:id',element:e(Invoice)}),e(Route,{path:'/crm/history',element:e(History,{customerId:1})}))))));
</script></body></html>`,
  );
  console.log(new URL("/__commercial-browser-qa.html", origin).href);
})().catch((e) => {
  console.error(e.message);
  process.exit(1);
});
