# Настройка MAX на тестовом сервере

Эта инструкция для оператора сервера. Токен бота не входит в Git и не должен попадать в README, скриншоты или сообщения.

## Где взять токен

В [MAX для бизнеса](https://business.max.ru/) откройте нужного бота: **Чат-боты → ⋮ → Настройки → Токен доступа → копировать**. В том же разделе укажите адрес Mini App `https://test.agentsofcremlin.netcraze.pro/`. Публичное имя бота возьмите из его ссылки `https://max.ru/<имя_бота>`.

## Где находится `.env`

Приложение читает файл из корня проекта: `~/apps/belike_hantaton-NotYourPlace/.env`. Это скрытый файл. Он игнорируется Git и может отсутствовать, пока вы его не создадите.

На Mac Mini выполните:

```sh
cd ~/apps/belike_hantaton-NotYourPlace
ls -la .env*
if [ ! -f .env ]; then cp .env.example .env; fi
chmod 600 .env
nano .env
```

В редакторе заполните три строки, сохранив остальные настройки:

```dotenv
MAX_BOT_TOKEN=токен_из_настроек_бота
MAX_BOT_USERNAME=имя_из_ссылки_max.ru_без_символа_@
MAX_WEBHOOK_SECRET=случайная_строка_из_букв_цифр_дефиса_и_подчёркивания
```

Для секрета можно получить случайную строку командой `python3.14 -c 'import secrets; print(secrets.token_urlsafe(32))'` и вставить её в `.env`. В `nano`: **Ctrl+O**, Enter, **Ctrl+X**. Не отправляйте содержимое `.env` в чат. Проверить, что файл игнорируется Git: `git check-ignore .env` должен вывести `.env`.

Если сайт уже запущен, новый токен не попадёт в работающий процесс сам. Остановите **только процесс этого проекта** в его терминале (Ctrl+C) и снова выполните `bash scripts/start-site-mac.sh`. Не останавливайте другие сервисы. Для текущей схемы с локальным HTTP и KeenDNS оставьте `COOKIE_SECURE=0`: приложение само ставит Secure-cookie для запросов, пришедших через HTTPS proxy.

## Приветствие и кнопка Mini App

MAX присылает события бота по webhook. После запуска проекта создайте подписку на `https://test.agentsofcremlin.netcraze.pro/api/max/webhook` с типами `bot_started` и `message_created`. Секрет подписки должен совпасть с `MAX_WEBHOOK_SECRET`. Команда ниже читает значения из `.env`, не выводит токен и не записывает его в историю оболочки:

```sh
cd ~/apps/belike_hantaton-NotYourPlace
export PATH="$HOME/tools/node-v22.23.5-darwin-x64/bin:$PATH"
node --input-type=module <<'NODE'
process.loadEnvFile('.env');
const {MAX_BOT_TOKEN: token, MAX_WEBHOOK_SECRET: secret, MAX_BOT_USERNAME: username} = process.env;
if (!token || !secret || !username) throw new Error('Заполните MAX_BOT_TOKEN, MAX_WEBHOOK_SECRET и MAX_BOT_USERNAME в .env');
const response = await fetch('https://platform-api2.max.ru/subscriptions', {
  method: 'POST',
  headers: {'Authorization': token, 'Content-Type': 'application/json'},
  body: JSON.stringify({
    url: 'https://test.agentsofcremlin.netcraze.pro/api/max/webhook',
    update_types: ['bot_started', 'message_created'],
    secret
  })
});
const result = await response.json();
console.log(`MAX webhook: HTTP ${response.status}`, result);
if (!response.ok || result.success !== true) process.exitCode = 1;
NODE
```

Убедитесь, что ответ сообщает `success: true`. Затем откройте чат бота в MAX и нажмите **Старт** или отправьте `/start`: должно прийти краткое приветствие с кнопкой «Открыть приложение». Проверьте отправку архива только на синтетических фото. Сам факт `success: true` подтверждает подписку, но не доставку события через KeenDNS; её подтверждают сообщение в чате и журнал сервера.

Webhook и long polling для одного бота одновременно не работают. Если у бота уже есть активная подписка или другая программа использует его токен, сначала проверьте её назначение и не переключайте чужой сервис.

Официальные инструкции MAX: [токен и настройки бота](https://dev.max.ru/docs/chatbots/bots-create/manage/), [подписка webhook](https://dev.max.ru/docs-api/methods/POST/subscriptions), [валидация Mini App](https://dev.max.ru/docs/webapps/validation).
