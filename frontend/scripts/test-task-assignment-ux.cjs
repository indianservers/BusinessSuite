// Run the current assignment/copy regression against an isolated Vite server.
const path = require('node:path');
const { spawn } = require('node:child_process');
(async () => {
  process.chdir(path.resolve(__dirname, '..'));
  const { createServer } = await import('vite');
  const server = await createServer({ server: { host: '127.0.0.1', port: 0, strictPort: false, hmr: false, watch: null } });
  try {
    await server.listen();
    const origin = `http://127.0.0.1:${server.httpServer.address().port}`;
    const code = await new Promise((resolve, reject) => {
      const child = spawn(process.execPath, [path.join(__dirname, 'test-task-compact.cjs')], {
        stdio: 'inherit', env: { ...process.env, ASSIGNMENT_QA_ORIGIN: origin },
      });
      child.once('error', reject);
      child.once('exit', code => resolve(code ?? 1));
    });
    process.exitCode = code;
  } finally {
    await server.close();
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
