const fs = require('node:fs');
const path = require('node:path');
const { chromium, expect } = require('playwright/test');

(async () => {
  const root = path.resolve(__dirname, '..');
  const fixture = path.join(__dirname, '.toast-modal-keyboard.tsx');
  fs.writeFileSync(fixture, `import {useState} from 'react';import {createRoot} from 'react-dom/client';import {Dialog,DialogContent,DialogTitle} from '@/components/ui/dialog';import {Toaster} from '@/components/ui/toaster';import {toast} from '@/hooks/use-toast';import '@/index.css';
function Fixture(){const [open,setOpen]=useState(false);return <><button onClick={()=>toast({title:'Ordinary notice',duration:60000})}>Show ordinary notice</button><button onClick={()=>setOpen(true)}>Open test modal</button><Dialog open={open} onOpenChange={setOpen}><DialogContent><DialogTitle>Keyboard test modal</DialogTitle><button onClick={()=>toast({title:'Queued modal notice',duration:60000})}>Queue modal notice</button></DialogContent></Dialog><Toaster/></>};createRoot(document.getElementById('root')!).render(<Fixture/>);`);
  const { createServer } = await import('vite');
  const server = await createServer({ root, cacheDir: path.join(root, 'node_modules/.vite-toast-modal-keyboard'), server: { host: '127.0.0.1', port: 0, hmr: false, watch: null } });
  let browser;
  try {
    await server.listen();
    browser = await chromium.launch();
    for (const width of [390, 1280]) {
      const page = await browser.newPage({ viewport: { width, height: 900 } });
      const errors = [];
      page.on('pageerror', error => errors.push(error.message));
      await page.route('**/api/**', route => route.fulfill({ json: { items: [] } }));
      await page.route('**/toast-keyboard-qa', route => route.fulfill({ contentType: 'text/html', body: `<meta name="viewport" content="width=device-width,initial-scale=1"><div id="root"></div><script type="module">import R from '/@react-refresh';R.injectIntoGlobalHook(window);window.$RefreshReg$=()=>{};window.$RefreshSig$=()=>t=>t;window.__vite_plugin_react_preamble_installed__=true;await import('/scripts/.toast-modal-keyboard.tsx');</script>` }));
      await page.goto(`http://127.0.0.1:${server.httpServer.address().port}/toast-keyboard-qa`);
      await page.getByRole('button', { name: 'Show ordinary notice', exact: true }).click();
      await expect(page.getByText('Ordinary notice', { exact: true })).toBeVisible();
      await page.getByRole('button', { name: 'Close notification', exact: true }).click();
      await expect(page.getByText('Ordinary notice', { exact: true })).toHaveCount(0);
      await page.getByRole('button', { name: 'Open test modal', exact: true }).click();
      const modal = page.getByRole('dialog', { name: 'Keyboard test modal', exact: true });
      await modal.getByRole('button', { name: 'Queue modal notice', exact: true }).click();
      await expect(page.getByText('Queued modal notice', { exact: true })).toHaveCount(0);
      await modal.press('Escape');
      await expect(modal).toHaveCount(0);
      await expect(page.getByText('Queued modal notice', { exact: true })).toBeVisible();
      await page.getByRole('button', { name: 'Close notification', exact: true }).click();
      await expect(page.getByText('Queued modal notice', { exact: true })).toHaveCount(0);
      expect(errors).toEqual([]);
      await page.close();
    }
    console.log('PASS toast/modal keyboard: ordinary dismissal, queued notice does not intercept Escape, notice returns after modal closes and remains dismissible at phone/desktop widths');
  } finally {
    await browser?.close();
    await server.close();
    fs.unlinkSync(fixture);
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
