import { spawn } from 'node:child_process';
import { existsSync } from 'node:fs';
import { resolve } from 'node:path';

const windows = process.platform === 'win32';
const python = resolve(windows ? '.venv/Scripts/python.exe' : '.venv/bin/python');
const production = process.argv.includes('--production');
if (existsSync('.env')) process.loadEnvFile('.env');
if (!existsSync(python)) {
  console.error('Сначала создайте окружение .venv и установите backend/requirements.txt — команды в README.md.');
  process.exit(1);
}
if (production && !existsSync('frontend/dist/index.html')) {
  console.error('Сначала выполните npm run build.');
  process.exit(1);
}
const children = [];
let stopping = false;
function shutdown() {
  if (stopping) return;
  stopping = true;
  for (const child of children) child.kill('SIGTERM');
}
function launch(command, args) {
  const child = spawn(command, args, { stdio: 'inherit', cwd: process.cwd(), windowsHide: true });
  children.push(child);
  child.on('error', error => { console.error(error.message); shutdown(); process.exitCode = 1; });
  child.on('exit', code => { if (!stopping) { shutdown(); process.exitCode = code || 0; } });
}
launch(python, ['-m', 'uvicorn', 'backend.main:app', '--host', '127.0.0.1', '--port', '8000', ...(production ? [] : ['--reload'])]);
if (!production) {
  const npm = process.env.npm_execpath;
  if (!npm) { console.error('Запустите через npm run dev.'); shutdown(); process.exitCode = 1; }
  else launch(process.execPath, [npm, '--prefix', 'frontend', 'run', 'dev']);
}
process.on('SIGINT', shutdown);
process.on('SIGTERM', shutdown);
console.log(production ? 'ЧужоеМесто: http://127.0.0.1:8000' : 'ЧужоеМесто: http://127.0.0.1:5173 · API: http://127.0.0.1:8000/api/health');
