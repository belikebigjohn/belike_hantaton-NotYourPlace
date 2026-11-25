# Тестовый запуск на Mac Mini

Схема остаётся прежней: KeenDNS HTTPS → Keenetic → `192.168.2.32:8766` (отдельный Python 3.14 HTTP proxy) → `127.0.0.1:8000` (Python 3.12 FastAPI). Не меняйте настройки роутера, KeenDNS, Happ и других сервисов. Не запускайте Uvicorn на `8766`.

## Работа после закрытия Terminal

Для постоянного запуска установите пользовательскую службу macOS `launchd`. Сначала остановите старый ручной запуск проекта через **Ctrl+C в его терминале**. Скрипт установки откажется создавать второй экземпляр, если порты `8000` или `8766` уже заняты. Затем:

```sh
cd ~/apps/belike_hantaton-NotYourPlace
export PATH="$HOME/tools/node-v22.23.5-darwin-x64/bin:$PATH"
git switch main
git pull --ff-only origin main
npm run build
bash scripts/site-service-mac.sh install
bash scripts/site-service-mac.sh status
```

После установки Terminal можно закрыть. `launchd` поддерживает процесс и запускает его при следующем входе пользователя в macOS. Во время установки пользователь должен быть вошедшим в графический сеанс Mac Mini (при необходимости войдите через VNC). При полном выходе пользователя из macOS служба остановится до следующего входа; запуск сразу после включения Mac без входа требует системного LaunchDaemon и здесь не настроен.

После обновления кода или `.env`:

```sh
git pull --ff-only origin main
npm run build
bash scripts/site-service-mac.sh restart
bash scripts/site-service-mac.sh status
```

Остановить службу вручную: `bash scripts/site-service-mac.sh stop`. Снова включить: `bash scripts/site-service-mac.sh start`. Логи: `runtime-data/logs/site.out.log` и `runtime-data/logs/site.err.log`. Служба запускает тот же `start-site-mac.sh`, включая проверку MAX, без дополнительных портов.

## Быстрый запуск одной командой

```sh
cd ~/apps/belike_hantaton-NotYourPlace
bash scripts/start-site-mac.sh
```

Скрипт использует уже проверенное `.venv-cv/bin/python`, если оно есть, иначе штатное `.venv/bin/python`; можно явно задать `APP_PYTHON=.venv/bin/python`. Он проверяет `8000` и `8766` и запускает только отсутствующие части. Если порт занят, но сервис на нём не отвечает, скрипт показывает владельца порта и останавливается без массового завершения процессов. После запуска он проверяет настройки MAX и подключает webhook этого проекта, если бот ещё не подписан; подробности в [MAX_SETUP.md](MAX_SETUP.md). При уже работающем backend новый `.env` не подхватится без перезапуска именно этого процесса. Оставьте терминал открытым. `Ctrl+C` завершает только процессы, запущенные этой командой. Логинов и паролей нет. Сообщение об исправности локальной цепочки не подтверждает доступность внешнего HTTPS: проверьте адрес в браузере.

## Перед запуском

```sh
cd ~/apps/belike_hantaton-NotYourPlace
git status --short
lsof -nP -iTCP:8000 -sTCP:LISTEN
lsof -nP -iTCP:8766 -sTCP:LISTEN
```

Если `8000` уже занят, проверьте `curl -fsS http://127.0.0.1:8000/api/health` и не запускайте второй backend. Если `8766` уже занят, проверьте владельца процесса в `lsof` и не запускайте второй proxy. Если в `git status` есть изменения, разберите их до слияния новой ветки.

`npm start` использует `.venv/bin/python` по умолчанию. После остановки **только своего** старого backend обновите это окружение и проверьте модели:

```sh
.venv/bin/python -m pip install -r backend/requirements.txt
.venv/bin/python -m pip check
.venv/bin/python models/setup_models.py
.venv/bin/python -m backend.verify_models
```

`setup_models.py` проверяет размер и SHA-256 весов и загрузку моделей. Для текущей цепочки оставьте `COOKIE_SECURE=0`: приложение автоматически помечает cookie как Secure при запросе через HTTPS proxy, сохраняя локальный HTTP-доступ. Сам `.env` не отправляйте в Git. Настройка бота — в [MAX_SETUP.md](MAX_SETUP.md).

## Два отдельных терминала

Терминал 1, только если `8000` свободен:

```sh
cd ~/apps/belike_hantaton-NotYourPlace
bash scripts/start-backend-mac.sh
```

Скрипт использует `~/tools/node-v22.23.5-darwin-x64/bin`, `.venv/bin/python` и штатный `npm start`. Если frontend ещё не собран, предварительно запустите `~/tools/node-v22.23.5-darwin-x64/bin/npm run build`.

Терминал 2, только если `8766` свободен и backend отвечает:

```sh
cd ~/apps/belike_hantaton-NotYourPlace
bash scripts/start-proxy-mac.sh
```

Скрипт запускает отдельный `python3.14 scripts/keen_proxy.py` на `192.168.2.32:8766`. По явному запросу владельца тестовый сайт открыт без логина и пароля, как в прежней рабочей схеме. Не загружайте реальные персональные данные; ограничение доступа при необходимости настраивается отдельно в KeenDNS.

## Проверка

В третьем терминале:

```sh
curl -fsSI http://127.0.0.1:8000/
curl -fsS http://127.0.0.1:8000/api/health
curl -fsSI http://192.168.2.32:8766/
curl -fsS http://192.168.2.32:8766/api/health
curl -fsS \
  -F scene_photo=@demo/overview-demo.png \
  -F plate_photo=@demo/plate-demo.png \
  http://192.168.2.32:8766/api/analyze
```

Последний запрос проверяет загрузку двух изображений и реальный инференс через proxy. На этих синтетических кадрах OCR может ошибаться, поэтому смотрите `analysis_status`, `plate`, `signs` и `needs_review`, не требуйте точного номера.

Откройте `https://test.agentsofcremlin.netcraze.pro/` в браузере. Проверьте загрузку страницы, создание черновика и анализ только на синтетических фотографиях. Положительное обнаружение знаков 6.4 и 8.17 потребует отдельных обезличенных кадров. До проверки безопасности не загружайте реальные персональные данные.

Здесь нет доступа к самому Mac Mini: локальные тесты скрипта не доказывают доступность KeenDNS. Запишите результаты каждого участка цепочки и журналы двух терминалов, если внешний адрес не откроется.
