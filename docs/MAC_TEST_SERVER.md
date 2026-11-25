# Тестовый запуск на Mac Mini

Схема остаётся прежней: KeenDNS HTTPS → Keenetic → `192.168.2.32:8766` (отдельный Python 3.14 HTTP proxy) → `127.0.0.1:8000` (Python 3.12 FastAPI). Не меняйте настройки роутера, KeenDNS, Happ и других сервисов. Не запускайте Uvicorn на `8766`.

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

`setup_models.py` проверяет размер и SHA-256 весов и загрузку моделей. Установите `COOKIE_SECURE=1` в локальном `.env` для HTTPS тестового адреса. Сам `.env` не отправляйте в Git.

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

Скрипт запускает отдельный `python3.14 scripts/keen_proxy.py` на `192.168.2.32:8766`. Он запросит имя и пароль длиной от 16 символов для внешнего тестового доступа. Пароль не сохраняется в репозитории. Для автоматизированного запуска можно заранее установить `TEST_PROXY_USER` и `TEST_PROXY_PASSWORD` в окружении процесса, но не передавайте пароль в командной строке, URL или чате. HTTP Basic доступ работает только за внешним HTTPS KeenDNS; локальный участок маршрута остаётся HTTP.

## Проверка

В третьем терминале:

```sh
curl -fsSI http://127.0.0.1:8000/
curl -fsS http://127.0.0.1:8000/api/health
curl -u 'ИМЯ_ПОЛЬЗОВАТЕЛЯ' -fsSI http://192.168.2.32:8766/
curl -u 'ИМЯ_ПОЛЬЗОВАТЕЛЯ' -fsS http://192.168.2.32:8766/api/health
curl -u 'ИМЯ_ПОЛЬЗОВАТЕЛЯ' -fsS \
  -F scene_photo=@demo/overview-demo.png \
  -F plate_photo=@demo/plate-demo.png \
  http://192.168.2.32:8766/api/analyze
```

`curl -u 'ИМЯ_ПОЛЬЗОВАТЕЛЯ'` спросит пароль; это позволяет не оставлять его в истории команд. Последний запрос проверяет загрузку двух изображений и реальный инференс через proxy. На этих синтетических кадрах OCR может ошибаться, поэтому смотрите `analysis_status`, `plate`, `signs` и `needs_review`, не требуйте точного номера.

Откройте `https://test.agentsofcremlin.netcraze.pro/` в браузере и введите тестовые логин и пароль. Проверьте загрузку страницы, создание черновика и анализ только на синтетических фотографиях. Положительное обнаружение знаков 6.4 и 8.17 потребует отдельных обезличенных кадров. До проверки безопасности не загружайте реальные персональные данные.

Здесь нет доступа к самому Mac Mini: локальные тесты скрипта не доказывают доступность KeenDNS. Запишите результаты каждого участка цепочки и журналы двух терминалов, если внешний адрес не откроется.
