// Called by start-site-mac.sh after the existing backend and proxy are healthy.
// Uses only the token in the ignored .env file; never prints it.
import { existsSync } from 'node:fs';

if (existsSync('.env')) process.loadEnvFile('.env');

const token = process.env.MAX_BOT_TOKEN || '';
const username = process.env.MAX_BOT_USERNAME || '';
const secret = process.env.MAX_WEBHOOK_SECRET || '';
const webhook = 'https://test.agentsofcremlin.netcraze.pro/api/max/webhook';
const requiredEvents = ['bot_started', 'message_created'];
const refresh = process.argv.includes('--refresh');

async function main() {
  if (!token && !username && !secret) {
    console.log('MAX: настройки не заданы в .env; сайт работает без бота.');
    return;
  }
  if (!token || !username || !secret) throw new Error('MAX: заполните MAX_BOT_TOKEN, MAX_BOT_USERNAME и MAX_WEBHOOK_SECRET в .env.');
  if (!/^[A-Za-z0-9_-]{5,256}$/.test(secret)) throw new Error('MAX: MAX_WEBHOOK_SECRET содержит недопустимые символы.');

  const healthResponse = await fetch('http://127.0.0.1:8000/api/health', { signal: AbortSignal.timeout(5000) });
  if (!healthResponse.ok) throw new Error('MAX: backend не отвечает на /api/health.');
  const health = await healthResponse.json();
  if (!health.integrations?.max?.configured) {
    throw new Error('MAX: работающий backend не прочитал .env. Остановите только процесс этого проекта и запустите start-site-mac.sh снова.');
  }
  const proxyResponse = await fetch('http://192.168.2.32:8766/api/health', { signal: AbortSignal.timeout(5000) });
  if (!proxyResponse.ok || !(await proxyResponse.json()).integrations?.max?.configured) {
    throw new Error('MAX: прокси ещё не ведёт к backend с настройками бота. Проверьте процессы на 8000 и 8766.');
  }

  const headers = { Authorization: token };
  const listResponse = await fetch('https://platform-api2.max.ru/subscriptions', { headers, signal: AbortSignal.timeout(15000) });
  if (!listResponse.ok) throw new Error(`MAX: не удалось проверить webhook (HTTP ${listResponse.status}).`);
  const subscriptions = (await listResponse.json()).subscriptions;
  if (!Array.isArray(subscriptions)) throw new Error('MAX: неожиданный ответ при проверке webhook.');
  const other = subscriptions.find(item => item.url !== webhook);
  if (other) throw new Error('MAX: у этого бота есть webhook по другому адресу. Автоскрипт его не меняет.');
  const current = subscriptions.find(item => item.url === webhook);
  if (current && requiredEvents.every(event => current.update_types?.includes(event)) && !refresh) {
    console.log('MAX: webhook уже подключён к этому проекту (секрет проверяется только входящим событием).');
    return;
  }

  const response = await fetch('https://platform-api2.max.ru/subscriptions', {
    method: 'POST',
    headers: { ...headers, 'Content-Type': 'application/json' },
    body: JSON.stringify({ url: webhook, update_types: requiredEvents, secret }),
    signal: AbortSignal.timeout(15000),
  });
  const result = await response.json().catch(() => ({}));
  if (!response.ok || result.success !== true) throw new Error(`MAX: не удалось подключить webhook (HTTP ${response.status}, ${result.code || 'без кода ошибки'}).`);
  console.log('MAX: webhook подключён. Проверьте команду /start в чате бота.');
}

main().catch(error => {
  const code = error.cause?.code || error.code;
  console.error(code ? `MAX: ${error.message} (${code})` : error.message);
  process.exitCode = 1;
});
