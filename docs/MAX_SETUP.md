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

Если сайт уже запущен, новый токен не попадёт в работающий процесс сам. Остановите **только процесс этого проекта** в его терминале (Ctrl+C). Не останавливайте другие сервисы. Для текущей схемы с локальным HTTP и KeenDNS оставьте `COOKIE_SECURE=0`: приложение само ставит Secure-cookie для запросов, пришедших через HTTPS proxy.

Обычный запуск после обновления кода:

```sh
cd ~/apps/belike_hantaton-NotYourPlace
export PATH="$HOME/tools/node-v22.23.5-darwin-x64/bin:$PATH"
git switch main
git pull --ff-only origin main
npm run build
bash scripts/start-site-mac.sh
```

Скрипт запускает backend, proxy и проверку MAX одной командой. Вебхук MAX обслуживает тот же backend на порту 8000; отдельный сервер или новый порт для бота не нужны.

## Приветствие и кнопка Mini App

MAX присылает события бота по webhook. `bash scripts/start-site-mac.sh` запускает backend с обработчиком MAX и, если заполнены все три переменные, проверяет подписку webhook. При отсутствии подписки на этот проект скрипт создаёт её для `https://test.agentsofcremlin.netcraze.pro/api/max/webhook` с событиями `bot_started` и `message_created`. Токен читается из `.env` и не выводится.

Если бот уже подписан на **другой** адрес, скрипт не переключает его: нужно сначала понять, кто использует этого бота. При ошибке подключения сайт остаётся запущен, а терминал покажет, что MAX не готов. При смене `MAX_WEBHOOK_SECRET` перезапустите backend проекта и обновите существующую подписку командой:

```sh
cd ~/apps/belike_hantaton-NotYourPlace
export PATH="$HOME/tools/node-v22.23.5-darwin-x64/bin:$PATH"
node scripts/ensure-max-webhook.mjs --refresh
```

Затем откройте чат бота в MAX и нажмите **Старт** или отправьте `/start`: должно прийти краткое приветствие с кнопкой «Открыть приложение». Проверьте отправку архива только на синтетических фото. Сообщение скрипта о наличии подписки не подтверждает доставку события через KeenDNS; её подтверждают ответ бота и журнал сервера.

Webhook и long polling для одного бота одновременно не работают. Если у бота уже есть активная подписка или другая программа использует его токен, сначала проверьте её назначение и не переключайте чужой сервис.

Официальные инструкции MAX: [токен и настройки бота](https://dev.max.ru/docs/chatbots/bots-create/manage/), [подписка webhook](https://dev.max.ru/docs-api/methods/POST/subscriptions), [валидация Mini App](https://dev.max.ru/docs/webapps/validation).
