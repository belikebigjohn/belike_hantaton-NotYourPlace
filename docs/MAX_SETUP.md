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

Если сайт уже запущен, новый токен не попадёт в работающий процесс сам. При ручном запуске остановите **только процесс этого проекта** в его терминале (Ctrl+C). Если сайт работает под службой `launchd`, выполните `bash scripts/site-service-mac.sh restart`. Не останавливайте другие сервисы. Для текущей схемы с локальным HTTP и KeenDNS оставьте `COOKIE_SECURE=0`: приложение само ставит Secure-cookie для запросов, пришедших через HTTPS proxy.

На Mac Mini MAX работает внутри той же службы `launchd`, что и сайт. Terminal можно закрыть. После изменения `.env` или кода перезапускайте службу, отдельный бот-процесс не нужен. Команды остановки, обновления из GitHub и повторного запуска есть в [README](../README.md#тестовый-сервер-на-mac-mini).

## Сертификат API MAX на Mac Mini

Если в логах `fetch failed`, а `curl https://platform-api2.max.ru/subscriptions` сообщает `SSL certificate problem: unable to get local issuer certificate`, токен ещё даже не проверялся: соединение прервано на проверке TLS. MAX требует доверять сертификату Минцифры. [Официальная документация MAX](https://dev.max.ru/docs-api) и [страница сертификатов Госуслуг](https://www.gosuslugi.ru/crt).

Скрипт скачивает корневой и выпускающий сертификаты с государственного домена `gu-st.ru`, проверяет их имена, сроки и цепочку, затем сохраняет **только для этого проекта** в игнорируемую Git папку `runtime-data/certs`. Системное хранилище macOS он не меняет, проверку TLS не отключает.

```sh
cd ~/apps/belike_hantaton-NotYourPlace
bash scripts/setup-max-trust-mac.sh
bash scripts/site-service-mac.sh restart
sleep 70
bash scripts/site-service-mac.sh status
tail -n 40 runtime-data/logs/site.err.log
tail -n 40 runtime-data/logs/site.out.log
```

`setup-max-trust-mac.sh` ожидает `HTTP 401` от MAX без токена: это значит, что TLS прошёл и API ответил. Если ранее появился `curl: (77)` или `PEM routines::bad end line`, после обновления проекта запустите скрипт ещё раз: он теперь проверяет готовый PEM до замены файла. После перезапуска в `site.out.log` должно быть `MAX: webhook подключён` или `MAX: webhook уже подключён`. Если подписка существовала со старым секретом, обновите её отдельной командой после перезапуска:

```sh
NODE_EXTRA_CA_CERTS="$PWD/runtime-data/certs/max-ca.pem" node scripts/ensure-max-webhook.mjs --refresh
```

Если сервер MAX вернёт другой код, сохраните строку ошибки из лога без токена. Не используйте `curl -k`, `NODE_TLS_REJECT_UNAUTHORIZED=0` или `verify=False`: они отключают проверку адресата, которому отправляется токен бота и архив.

Для ручного запуска (когда служба остановлена):

```sh
cd ~/apps/belike_hantaton-NotYourPlace
export PATH="$HOME/tools/node-v22.23.5-darwin-x64/bin:$PATH"
git switch main
git pull --ff-only origin main
npm run build
bash scripts/start-site-mac.sh
```

Скрипт запускает backend, proxy и проверку MAX одной командой, пока открыт терминал. Для работы после закрытия Terminal используйте [службу launchd](MAC_TEST_SERVER.md#работа-после-закрытия-terminal). Вебхук MAX обслуживает тот же backend на порту 8000; отдельный сервер или новый порт для бота не нужны.

## Приветствие и кнопка Mini App

MAX присылает события бота по webhook. `bash scripts/start-site-mac.sh` запускает backend с обработчиком MAX и, если заполнены все три переменные, проверяет подписку webhook. При отсутствии подписки на этот проект скрипт создаёт её для `https://test.agentsofcremlin.netcraze.pro/api/max/webhook` с событиями `bot_started` и `message_created`. Токен читается из `.env` и не выводится.

Если бот уже подписан на **другой** адрес, скрипт не переключает его: нужно сначала понять, кто использует этого бота. При ошибке подключения сайт остаётся запущен, а лог покажет, что MAX не готов. При смене `MAX_WEBHOOK_SECRET` перезапустите службу проекта и выполните команду `--refresh` из раздела о сертификате выше.

Затем откройте чат бота в MAX и нажмите **Старт** или отправьте `/start`: должно прийти краткое приветствие с кнопкой «Открыть приложение». Проверьте отправку архива только на синтетических фото. Сообщение скрипта о наличии подписки не подтверждает доставку события через KeenDNS; её подтверждают ответ бота и журнал сервера.

Webhook и long polling для одного бота одновременно не работают. Если у бота уже есть активная подписка или другая программа использует его токен, сначала проверьте её назначение и не переключайте чужой сервис.

Официальные инструкции MAX: [токен и настройки бота](https://dev.max.ru/docs/chatbots/bots-create/manage/), [подписка webhook](https://dev.max.ru/docs-api/methods/POST/subscriptions), [валидация Mini App](https://dev.max.ru/docs/webapps/validation).
