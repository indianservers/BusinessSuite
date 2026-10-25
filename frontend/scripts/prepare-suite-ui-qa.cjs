const fs = require("node:fs"),
  path = require("node:path");
(async () => {
  const target = path.resolve(__dirname, "../__suite-ui-qa.html");
  if (process.argv.includes("--clean")) {
    fs.rmSync(target, { force: true });
    return;
  }
  const source = await (
    await fetch(
      "http://127.0.0.1:5191/src/apps/project-management/pages/ProjectBillingPage.tsx",
    )
  ).text();
  const version = (name) =>
    source.match(new RegExp(name + "\\.js\\?v=([a-f0-9]+)"))[1];
  fs.writeFileSync(
    target,
    `<html lang="en"><head><title>KaryaFlow Business Suite — UI verification</title><meta name="viewport" content="width=device-width,initial-scale=1"></head><body><div id="root"></div><script>window.__AI_HRMS_CONFIG__={apiBaseUrl:'http://127.0.0.1:8775/api/v1'};</script><script type="module">import RefreshRuntime from '/@react-refresh';RefreshRuntime.injectIntoGlobalHook(window);window.$RefreshReg$=()=>{};window.$RefreshSig$=()=>type=>type;window.__vite_plugin_react_preamble_installed__=true;</script><script type="module">
import React from '/node_modules/.vite/deps/react.js?v=${version("react")}';import ReactDOM from '/node_modules/.vite/deps/react-dom_client.js?v=${version("react")}';import {MemoryRouter} from '/node_modules/.vite/deps/react-router-dom.js?v=${version("react-router-dom")}';import {QueryClient,QueryClientProvider} from '/node_modules/.vite/deps/@tanstack_react-query.js?v=${version("@tanstack_react-query")}';
import App from '/src/App.tsx';import {api} from '/src/services/api.ts';import {useAuthStore} from '/src/store/authStore.ts';import {applyTheme} from '/src/store/themeStore.ts';import '/src/index.css';import '/src/design-system/premium.css';
api.defaults.baseURL='http://127.0.0.1:8775/api/v1';const params=new URLSearchParams(location.search);const session=await(await fetch('http://127.0.0.1:8775/qa-session'+(params.get('guest')==='1'?'?guest=true':''))).json();useAuthStore.setState({user:session.user,accessToken:session.token,isAuthenticated:true,isHydrated:true});applyTheme(params.get('theme')==='dark'?'dark':'light');const e=React.createElement;ReactDOM.createRoot(document.getElementById('root')).render(e(QueryClientProvider,{client:new QueryClient({defaultOptions:{queries:{retry:false}}})},e(MemoryRouter,{initialEntries:[params.get('path')||'/pms']},e(App))));</script></body></html>`,
  );
  console.log("Suite QA harness ready");
})().catch((e) => {
  console.error(e);
  process.exitCode = 1;
});
