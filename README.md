# ЧужоеМесто

Веб-приложение для подготовки проекта обращения о возможном нарушении на специальном парковочном месте. Пользователь делает два снимка, проверяет номер и обозначение места, указывает адрес и время, затем получает ZIP с текстом и исходными фотографиями. Приложение **не подаёт обращение автоматически** и не делает юридический вывод.

## Быстрый запуск на Mac Mini

Рабочая схема: KeenDNS HTTPS → 192.168.2.32:8766 (Python 3.14 reverse proxy) → 127.0.0.1:8000 (FastAPI, Python 3.12). Роутер, DNS и другие сервисы не трогаются.

```sh
cd ~/apps/belike_hantaton-NotYourPlace
bash scripts/start-site-mac.sh
```

Скрипт проверяет занятые порты, собирает нужную цепочку и не запускает второй backend или proxy. Терминал оставьте открытым. Ctrl+C останавливает только процессы, запущенные этим скриптом. Если один из процессов уже работает, он используется без перезапуска. Требуется заранее собранный `frontend/dist`, установленное окружение `.venv-cv` либо `.venv`, Node.js в `~/tools/node-v22.23.5-darwin-x64/bin` и Python 3.14 для proxy.

Проверка после запуска:

```sh
curl -fsS http://127.0.0.1:8000/api/health
curl -fsS http://192.168.2.32:8766/api/health
curl -I https://test.agentsofcremlin.netcraze.pro/
```

Откройте [тестовый адрес](https://test.agentsofcremlin.netcraze.pro/) и пройдите путь на синтетических фотографиях. Ответы первых двух команд подтверждают лишь локальную цепочку; доступность KeenDNS проверяется отдельно. Пароля у тестового приложения нет. До проверки безопасности не загружайте реальные персональные данные.

Отдельный запуск при необходимости: `bash scripts/start-backend-mac.sh` и в другом терминале `bash scripts/start-proxy-mac.sh`. Первый скрипт требует `.venv`; для проверенного `.venv-cv` используйте `APP_PYTHON=.venv-cv/bin/python npm start`. Proxy запускайте только после backend. Порты 8000 и 8766 не занимайте вторыми экземплярами. Подробная диагностика: [docs/MAC_TEST_SERVER.md](docs/MAC_TEST_SERVER.md).

## Установка на Mac Mini с нуля

Нужны Python 3.12 для CV, Python 3.14 для прокси, Node.js 22 и доступ в интернет при однократной загрузке весов. macOS Monterey Intel использует отдельные версии NumPy/OpenCV/PyTorch из `backend/requirements.txt`.

```sh
cd ~/apps/belike_hantaton-NotYourPlace
python3.12 -m venv .venv-cv
.venv-cv/bin/python -m pip install -r backend/requirements.txt
export PATH="$HOME/tools/node-v22.23.5-darwin-x64/bin:$PATH"
npm --prefix frontend ci
.venv-cv/bin/python models/setup_models.py
.venv-cv/bin/python models/setup_models.py --verify-only
.venv-cv/bin/python -m backend.verify_models
npm run build
bash scripts/start-site-mac.sh
```

Веса моделей не хранятся в Git. Установщик проверяет SHA-256. `/api/health` показывает загрузку OpenCV, детектора номера, OCR и дорожных знаков. На синтетическом демо OCR может ошибаться: номер всегда подтверждает человек.

## Локальный запуск на ПК

Нужны Python 3.12 и Node.js 20.19+ либо 22.12+. Создайте своё окружение; перенесённое `.venv` с другой машины не работает.

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend/requirements.txt
npm --prefix frontend ci
.\.venv\Scripts\python.exe models/setup_models.py
npm run build
npm start
```

Откройте http://127.0.0.1:8000. Для разработки: `npm run dev` (Vite на 127.0.0.1:5173, API на 127.0.0.1:8000). Сервер останавливается Ctrl+C. Параметры окружения считываются из игнорируемого Git файла `.env`; образец — `.env.example`.

## MAX

Бот и Mini App используют один `MAX_BOT_TOKEN`. В `.env` на сервере задайте `MAX_BOT_TOKEN`, `MAX_BOT_USERNAME` (публичное имя бота) и случайный `MAX_WEBHOOK_SECRET` длиной 5–256 символов из букв, цифр, `_` и `-`. Не добавляйте токен в Git или frontend. При запуске через MAX подписанные `WebAppData` проверяются на сервере; архив отправляется в чат пользователя через бота. При обычном открытии сайта архив скачивается браузером. Материалы MAX привязаны к подтверждённому MAX ID; одного имени пользователя из браузера недостаточно.

Для приветствия с кнопкой «Открыть приложение» подключите существующий HTTPS адрес к Mini App бота и оформите webhook подписку в MAX на `https://test.agentsofcremlin.netcraze.pro/api/max/webhook` с типами `bot_started`, `message_created` и тем же `secret`. При `/start` бот отправит короткую инструкцию и inline кнопку `open_app`. Webhook требует реальной доставки POST через KeenDNS; её надо проверить в кабинете MAX и в логах сервера. Не включайте параллельный long polling для этого бота.

Актуальный протокол: [валидация Mini App](https://dev.max.ru/docs/webapps/validation), [webhook](https://dev.max.ru/docs-api/methods/POST/subscriptions), [загрузка файла](https://dev.max.ru/docs-api/methods/POST/uploads), [отправка сообщения](https://dev.max.ru/docs-api/methods/POST/messages). Без токена и настроенного webhook MAX доставка не активна; обычный веб-сайт работает отдельно.

## Состав и проверки

Frontend: React 19, TypeScript, Vite, Lucide. Backend: FastAPI, Uvicorn, SQLite, OpenCV, FastALPR/ONNX, Nomeroff OCR, Ultralytics YOLO, python-docx, reportlab, httpx. `scripts/keen_proxy.py` использует только стандартную библиотеку Python. Данные и фото хранятся в `runtime-data/`, игнорируются Git. Экспорт содержит DOCX, TXT, HTML, оригиналы и manifest SHA-256. Камера отправляет уменьшенные кадры на сервер только для живых подсказок; в пакет попадает сделанный снимок.

```sh
npm run check
npm run lint
npm test
npm run build
.venv-cv/bin/python -m pytest tests/backend tests/test_documents.py -q
```

На Windows в последней команде используйте `.venv\Scripts\python.exe`. Сквозная проверка API на синтетических фото: `python scripts/integration_smoke.py` из рабочего окружения.

## Границы релиза

Разметка и знак инвалидности на автомобиле пока возвращают `unknown`: подтверждённых моделей для них нет. Точность CV на независимой уличной выборке не установлена. Юридическое решение принимает ведомство. До публичного приёма реальных данных нужны проверка хранения, сроков удаления, доступа, злоупотреблений, лицензий весов и работы MAX на физических устройствах. Лицензии известных компонентов и контрольные суммы описаны в `docs/` и `models/`.
