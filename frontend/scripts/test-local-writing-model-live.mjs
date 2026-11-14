// Legacy entrypoint now checks authenticated server writing, without browser weights.
import {spawnSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';
const backend=fileURLToPath(new URL('../../backend/',import.meta.url));
const python=fileURLToPath(new URL('../../backend/venv/Scripts/python.exe',import.meta.url));
const result=spawnSync(python,['scripts/smoke_server_writing.py'],{cwd:backend,env:{...process.env,PYTHONPATH:backend},stdio:'inherit'});
process.exit(result.status??1);
