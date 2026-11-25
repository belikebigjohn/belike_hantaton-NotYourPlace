from __future__ import annotations

import hashlib
import json
import logging
import os
import secrets
import sqlite3
import threading
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal
from uuid import UUID

import httpx
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field

from backend.cv import decode_image, engine, normalize_plate, RU_PATTERN
from backend.documents import build_export, statement_for
from backend.max_integration import owner_for_user, send_package, send_welcome, validate_init_data

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = Path(os.getenv("DATA_DIR", ROOT / "runtime-data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)
DATABASE = DATA_DIR / "reports.sqlite3"
MAX_UPLOAD = 15 * 1024 * 1024
COOKIE_NAME = "chuzhoe_session"
ALLOWED_ORIGINS = set(os.getenv("ALLOWED_ORIGINS", "http://127.0.0.1:5173,http://localhost:5173,http://127.0.0.1:8000,http://localhost:8000,https://test.agentsofcremlin.netcraze.pro").split(","))


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def connection():
    database = sqlite3.connect(DATABASE, timeout=20)
    database.row_factory = sqlite3.Row
    database.execute("PRAGMA foreign_keys=ON")
    return database


def initialize():
    with connection() as database:
        database.execute("CREATE TABLE IF NOT EXISTS reports (id TEXT PRIMARY KEY, owner TEXT NOT NULL, data TEXT NOT NULL, updated TEXT NOT NULL)")
        database.execute("CREATE INDEX IF NOT EXISTS reports_owner ON reports(owner)")
        database.execute("CREATE TABLE IF NOT EXISTS photos (id TEXT PRIMARY KEY, report_id TEXT NOT NULL REFERENCES reports(id) ON DELETE CASCADE, kind TEXT NOT NULL, path TEXT NOT NULL, metadata TEXT NOT NULL, active INTEGER NOT NULL DEFAULT 1)")
        database.execute("CREATE TABLE IF NOT EXISTS report_creation_keys (owner TEXT NOT NULL, request_key TEXT NOT NULL, report_id TEXT NOT NULL REFERENCES reports(id) ON DELETE CASCADE, PRIMARY KEY(owner,request_key))")


@asynccontextmanager
async def lifespan(app):
    initialize()
    # Models are loaded once, before readiness. No request-time download.
    import asyncio
    await asyncio.to_thread(engine.load)
    yield


app = FastAPI(title="ЧужоеМесто", version="0.2.0", lifespan=lifespan)
initialize()


@app.middleware("http")
async def session_and_security(request: Request, call_next):
    length = request.headers.get("content-length", "0")
    if length.isdigit() and int(length) > 32 * 1024 * 1024:
        return JSONResponse({"error": {"code": "upload_too_large", "message": "Общий размер фотографий должен быть меньше 30 МБ."}}, status_code=413)
    origin = request.headers.get("origin")
    if request.method in {"POST", "PATCH", "DELETE", "PUT"} and origin and origin not in ALLOWED_ORIGINS and origin != str(request.base_url).rstrip("/"):
        return JSONResponse({"error": {"code": "origin_not_allowed", "message": "Откройте приложение заново и повторите действие."}}, status_code=403)
    cookie = request.cookies.get(COOKIE_NAME)
    fresh = not cookie or len(cookie) < 40 or len(cookie) > 128
    cookie = secrets.token_urlsafe(32) if fresh else cookie
    request.state.max_user = None
    init_data = request.headers.get("x-max-init-data")
    if init_data:
        try:
            request.state.max_user = validate_init_data(init_data)
        except ValueError:
            return JSONResponse({"error": {"code": "invalid_max_identity", "message": "Сессия MAX истекла. Откройте приложение из чата ещё раз."}}, status_code=401)
    request.state.owner = owner_for_user(request.state.max_user) if request.state.max_user else hashlib.sha256(cookie.encode()).hexdigest()
    response = await call_next(request)
    if fresh:
        https_frontend = request.headers.get("x-forwarded-proto") == "https" or os.getenv("COOKIE_SECURE") == "1"
        response.set_cookie(COOKIE_NAME, cookie, max_age=60 * 60 * 24 * 30, httponly=True, samesite="none" if https_frontend else "strict", secure=https_frontend)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    if request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    return response


@app.exception_handler(HTTPException)
async def http_error(request, error):
    return JSONResponse({"error": {"code": str(error.status_code), "message": str(error.detail)}}, status_code=error.status_code)


@app.exception_handler(RequestValidationError)
async def validation_error(request, error):
    return JSONResponse({"error": {"code": "invalid_input", "message": "Проверьте заполненные поля и фотографии."}}, status_code=422)


class ReportInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    status: Literal["draft", "prepared", "exported", "sent"] = "draft"
    plate: str = Field("", max_length=40)
    address: str = Field("", max_length=2000)
    observed_at: str = Field("", max_length=80)
    latitude: float | None = Field(None, ge=-90, le=90)
    longitude: float | None = Field(None, ge=-180, le=180)
    accuracy: float | None = Field(None, ge=0, le=100000)
    location_source: str = Field("manual", max_length=80)
    designation: str = Field("", max_length=1000)
    observation: str = Field("", max_length=10000)
    applicant_name: str = Field("", max_length=500)
    applicant_address: str = Field("", max_length=2000)
    applicant_email: str = Field("", max_length=500)
    recipient: str = Field("", max_length=2000)
    statement: str = Field("", max_length=30000)
    confirmed: bool = False
    analysis: dict | None = None


class Coordinates(BaseModel):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    consent: bool = False
    provider: Literal["photon", "nominatim"] | None = None


def read_report(report_id, owner):
    with connection() as database:
        row = database.execute("SELECT data FROM reports WHERE id=? AND owner=?", (report_id, owner)).fetchone()
        if not row:
            raise HTTPException(404, "Запись не найдена.")
        report = json.loads(row["data"])
        photo_rows = database.execute("SELECT metadata FROM photos WHERE report_id=? AND active=1", (report_id,)).fetchall()
    report["photos"] = {}
    for row in photo_rows:
        metadata = json.loads(row["metadata"])
        report["photos"][metadata["kind"]] = {**metadata, "url": f"/api/reports/{report_id}/photos/{metadata['kind']}"}
    return report


def write_report(report, owner):
    data = {key: value for key, value in report.items() if key != "photos"}
    with connection() as database:
        database.execute("UPDATE reports SET data=?,updated=? WHERE id=? AND owner=?", (json.dumps(data, ensure_ascii=False), report["updated_at"], report["id"], owner))


@app.get("/api/health")
def health():
    models = engine.health()
    ready = models["plate_detector"] == "loaded" and models["plate_ocr"] == "loaded" and models["road_signs"]["status"] == "loaded"
    max_configured = all(os.getenv(name) for name in ("MAX_BOT_TOKEN", "MAX_BOT_USERNAME", "MAX_WEBHOOK_SECRET"))
    return {"status": "ok" if ready else "degraded", "models": models, "demo_mode": os.getenv("DEMO_MODE", "0") == "1", "integrations": {"max": {"configured": bool(max_configured)}}}


@app.get("/api/map-config")
def map_config():
    # Public browser SDK key. Restrict allowed HTTP Referers in Yandex Console.
    return {"yandex_js_key": os.getenv("YANDEX_MAPS_API_KEY", "")}


@app.post("/api/analyze")
async def analyze(scene_photo: UploadFile = File(...), plate_photo: UploadFile = File(...)):
    import asyncio
    try:
        scene, scene_quality = decode_image(await scene_photo.read(MAX_UPLOAD + 1))
        plate, plate_quality = decode_image(await plate_photo.read(MAX_UPLOAD + 1))
    except ValueError as error:
        raise HTTPException(422, str(error)) from error
    result = await asyncio.to_thread(engine.analyze, scene, plate)
    result["quality"] = {"scene": scene_quality, "plate": plate_quality}
    result["additional_evidence"] = {"marking": "unknown", "vehicle_disability_sign": "unknown"}
    return result


@app.post("/api/camera-preview")
async def camera_preview(kind: Literal["scene", "plate"] = Form(...), frame: UploadFile = File(...)):
    import asyncio
    data = await frame.read(2 * 1024 * 1024 + 1)
    if len(data) > 2 * 1024 * 1024:
        raise HTTPException(413, "Кадр для подсказок слишком большой.")
    try:
        image, _ = decode_image(data)
    except ValueError as error:
        raise HTTPException(422, str(error)) from error
    return await asyncio.to_thread(engine.preview, image, kind)


@app.post("/api/reports", status_code=201)
def create_report(request: Request, payload: ReportInput):
    if payload.status != "draft":
        raise HTTPException(422, "Сначала сохраните фотографии и проверьте сведения.")
    key = request.headers.get("idempotency-key")
    if key is not None:
        try:
            if len(key) > 128:
                raise ValueError("Too long")
            key = str(UUID(key))
        except ValueError as error:
            raise HTTPException(422, "Не удалось сохранить черновик. Обновите страницу и повторите действие.") from error
    report = payload.model_dump()
    report.update(id=secrets.token_hex(16), created_at=utc_now(), updated_at=utc_now(), photos={})
    with connection() as database:
        # A durable owner+key mapping and the report are committed together.
        # BEGIN IMMEDIATE serializes competing retry requests for the same key.
        database.execute("BEGIN IMMEDIATE")
        existing = database.execute("SELECT report_id FROM report_creation_keys WHERE owner=? AND request_key=?", (request.state.owner, key)).fetchone() if key else None
        if existing is None:
            database.execute("INSERT INTO reports VALUES(?,?,?,?)", (report["id"], request.state.owner, json.dumps(report, ensure_ascii=False), report["updated_at"]))
            if key:
                database.execute("INSERT INTO report_creation_keys VALUES(?,?,?)", (request.state.owner, key, report["id"]))
    if existing is not None:
        return read_report(existing["report_id"], request.state.owner)
    return report


@app.get("/api/reports")
def list_reports(request: Request):
    with connection() as database:
        ids = [row["id"] for row in database.execute("SELECT id FROM reports WHERE owner=? ORDER BY updated DESC LIMIT 200", (request.state.owner,))]
    return [read_report(report_id, request.state.owner) for report_id in ids]


@app.get("/api/reports/{report_id}")
def report_detail(report_id: str, request: Request):
    return read_report(report_id, request.state.owner)


def ensure_ready(report):
    if not all(report.get(field) for field in ("plate", "address", "observed_at", "confirmed", "designation", "applicant_name", "recipient")) or not (report.get("applicant_email") or report.get("applicant_address")) or not all(kind in report["photos"] for kind in ("scene", "plate")):
        raise HTTPException(422, "Добавьте два снимка, номер, адрес, время, получателя, данные заявителя и подтвердите сведения.")
    try:
        datetime.fromisoformat(report["observed_at"].replace("Z", "+00:00"))
    except ValueError as error:
        raise HTTPException(422, "Укажите корректные дату и время наблюдения.") from error
    analysis = report.get("analysis") or {}
    if "plates_by_photo" in analysis or "plate_review" in analysis:
        review = analysis.get("plate_review")
        if not isinstance(review, dict) or review.get("confirmed") is not True:
            raise HTTPException(422, "Сверьте номера на общем плане и крупном снимке и подтвердите проверку.")
        scene_number = normalize_plate(str(review.get("scene_value") or ""))
        plate_number = normalize_plate(str(review.get("plate_value") or ""))
        report_number = normalize_plate(str(report.get("plate") or ""))
        if not RU_PATTERN.fullmatch(scene_number) or scene_number != plate_number or plate_number != report_number:
            raise HTTPException(422, "Номера на двух снимках различаются. Уточните номер или замените фотографию.")


@app.patch("/api/reports/{report_id}")
def update_report(report_id: str, request: Request, payload: ReportInput):
    report = read_report(report_id, request.state.owner)
    changes = payload.model_dump(exclude_unset=True)
    factual_fields = {"plate", "address", "observed_at", "latitude", "longitude", "accuracy", "designation", "observation", "applicant_name", "applicant_address", "applicant_email", "recipient", "statement"}
    facts_changed = any(key in factual_fields and report.get(key) != value for key, value in changes.items())
    report.update(changes)
    if facts_changed and changes.get("confirmed") is not True:
        report["confirmed"] = False
        report["status"] = "draft"
        if "statement" not in changes:
            report["statement"] = ""
    if report["status"] != "draft":
        ensure_ready(report)
    report["updated_at"] = utc_now()
    write_report(report, request.state.owner)
    return report


@app.post("/api/reports/{report_id}/photos")
async def upload_photos(report_id: str, request: Request, scene_photo: UploadFile | None = File(None), plate_photo: UploadFile | None = File(None), scene_source: str = Form("upload"), plate_source: str = Form("upload"), scene_captured_at: str = Form(""), plate_captured_at: str = Form("")):
    report = read_report(report_id, request.state.owner)
    pending = []
    for kind, upload, source, captured_at in (("scene", scene_photo, scene_source, scene_captured_at), ("plate", plate_photo, plate_source, plate_captured_at)):
        if upload is None:
            continue
        if source not in {"camera", "upload"}:
            raise HTTPException(422, "Укажите способ получения фотографии.")
        if source == "camera" and captured_at:
            try:
                if len(captured_at) > 80:
                    raise ValueError("Too long")
                datetime.fromisoformat(captured_at.replace("Z", "+00:00"))
            except ValueError as error:
                raise HTTPException(422, "Не удалось прочитать время снимка. Сделайте фотографию ещё раз.") from error
        data = await upload.read(MAX_UPLOAD + 1)
        try:
            _, quality = decode_image(data)
        except ValueError as error:
            raise HTTPException(422, str(error)) from error
        photo_id = secrets.token_hex(16)
        mime = quality["mime_type"]
        extension = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}[mime]
        metadata = {"id": photo_id, "kind": kind, "original_name": Path(upload.filename or f"{kind}.{extension}").name[:500], "sha256": hashlib.sha256(data).hexdigest(), "size": len(data), "mime_type": mime, "source": source, "captured_at": (captured_at or None) if source == "camera" else None, "received_at": utc_now(), "quality": quality}
        pending.append((photo_id, kind, extension, data, metadata))
    if not pending:
        raise HTTPException(422, "Добавьте хотя бы одну фотографию.")
    directory = DATA_DIR / "photos" / report_id
    directory.mkdir(parents=True, exist_ok=True)
    written = []
    report["status"] = "draft"
    report["confirmed"] = False
    report["analysis"] = None
    report["statement"] = ""
    report["updated_at"] = utc_now()
    try:
        with connection() as database:
            for photo_id, kind, extension, data, metadata in pending:
                path = directory / f"{photo_id}.{extension}"
                # Exclusive creation and fresh random filenames preserve previous originals.
                with path.open("xb") as handle:
                    handle.write(data)
                written.append(path)
                database.execute("UPDATE photos SET active=0 WHERE report_id=? AND kind=?", (report_id, kind))
                database.execute("INSERT INTO photos VALUES(?,?,?,?,?,1)", (photo_id, report_id, kind, str(path), json.dumps(metadata, ensure_ascii=False)))
            record = {key: value for key, value in report.items() if key != "photos"}
            database.execute("UPDATE reports SET data=?,updated=? WHERE id=? AND owner=?", (json.dumps(record, ensure_ascii=False), report["updated_at"], report_id, request.state.owner))
    except Exception:
        for path in written:
            path.unlink(missing_ok=True)
        raise
    return read_report(report_id, request.state.owner)


@app.get("/api/reports/{report_id}/photos/{kind}")
def original_photo(report_id: str, kind: Literal["scene", "plate"], request: Request):
    read_report(report_id, request.state.owner)
    with connection() as database:
        row = database.execute("SELECT path,metadata FROM photos WHERE report_id=? AND kind=? AND active=1", (report_id, kind)).fetchone()
    if not row:
        raise HTTPException(404, "Снимок не найден.")
    return FileResponse(row["path"], media_type=json.loads(row["metadata"])["mime_type"], headers={"Cache-Control": "no-store"})


@app.get("/api/reports/{report_id}/export")
def export_report(report_id: str, request: Request):
    report = read_report(report_id, request.state.owner)
    ensure_ready(report)
    if not report["statement"]:
        report["statement"] = statement_for(report)
    with connection() as database:
        rows = database.execute("SELECT path,metadata,active FROM photos WHERE report_id=? ORDER BY active DESC,id", (report_id,)).fetchall()
    photo_files = []
    for row in rows:
        metadata = json.loads(row["metadata"])
        if not row["active"]:
            metadata["kind"] = f"previous-{metadata['kind']}-{metadata['id']}"
        photo_files.append({**metadata, "path": row["path"]})
    package = build_export(report, photo_files)
    if report["status"] != "sent":
        report["status"] = "exported"
    report["updated_at"] = utc_now()
    write_report(report, request.state.owner)
    return Response(package, media_type="application/zip", headers={"Content-Disposition": f'attachment; filename="chuzhoe-mesto-{report_id[:8]}.zip"'})


@app.post("/api/reports/{report_id}/send-max")
async def send_report_to_max(report_id: str, request: Request):
    if not request.state.max_user:
        raise HTTPException(403, "Откройте приложение из чата MAX, чтобы получить архив там.")
    if not os.getenv("MAX_BOT_TOKEN"):
        raise HTTPException(503, "Бот MAX ещё не настроен на сервере.")
    report = read_report(report_id, request.state.owner)
    ensure_ready(report)
    with connection() as database:
        rows = database.execute("SELECT path,metadata,active FROM photos WHERE report_id=? ORDER BY active DESC,id", (report_id,)).fetchall()
    photo_files = []
    for row in rows:
        metadata = json.loads(row["metadata"])
        if not row["active"]:
            metadata["kind"] = f"previous-{metadata['kind']}-{metadata['id']}"
        photo_files.append({**metadata, "path": row["path"]})
    if not report["statement"]:
        report["statement"] = statement_for(report)
    package = build_export(report, photo_files)
    try:
        await send_package(request.state.max_user, package, report_id)
    except (httpx.HTTPError, ValueError, KeyError, TypeError) as error:
        logging.exception("MAX archive delivery failed for report %s", report_id)
        raise HTTPException(502, "Не удалось отправить архив в MAX. Попробуйте ещё раз или нажмите «Скачать архив».") from error
    if report["status"] != "sent":
        report["status"] = "exported"
    report["updated_at"] = utc_now()
    write_report(report, request.state.owner)
    return {"delivered": True}


@app.post("/api/max/webhook")
async def max_webhook(request: Request):
    secret = os.getenv("MAX_WEBHOOK_SECRET", "")
    token = os.getenv("MAX_BOT_TOKEN", "")
    if not token or not secret or not secrets.compare_digest(request.headers.get("x-max-bot-api-secret", ""), secret):
        raise HTTPException(403, "Webhook unavailable")
    update = await request.json()
    update_type = update.get("update_type")
    user = update.get("user") if update_type == "bot_started" else (update.get("message") or {}).get("sender")
    command = ((update.get("message") or {}).get("body") or {}).get("text", "").strip()
    if update_type == "bot_started" or (update_type == "message_created" and command.startswith("/start")):
        user_id = (user or {}).get("user_id")
        if isinstance(user_id, int) and user_id > 0:
            await send_welcome(user_id)
    return {"ok": True}


@app.delete("/api/reports/{report_id}")
def delete_report(report_id: str, request: Request):
    read_report(report_id, request.state.owner)
    with connection() as database:
        paths = [Path(row["path"]) for row in database.execute("SELECT path FROM photos WHERE report_id=?", (report_id,))]
        database.execute("DELETE FROM reports WHERE id=? AND owner=?", (report_id, request.state.owner))
    for path in paths:
        path.unlink(missing_ok=True)
    return {"ok": True}


geocoder_lock = threading.Lock()
geocoder_last = 0.0
geocoder_cache = {}


@app.post("/api/geocode/reverse")
def reverse_geocode(payload: Coordinates):
    global geocoder_last
    fallback = {"address": None, "source": "manual", "needs_manual": True}
    provider = os.getenv("GEOCODER_PROVIDER", "nominatim")
    geocoder_url = os.getenv("GEOCODER_URL", "")
    # Public service is available only after the person explicitly opts in to
    # the named destination in the location screen. No implicit transmission.
    if not payload.consent:
        return fallback
    if payload.provider == "photon":
        provider = "photon"
        geocoder_url = os.getenv("PHOTON_URL", "https://photon.komoot.io/reverse")
    elif payload.provider == "nominatim":
        provider = "nominatim"
        geocoder_url = os.getenv("NOMINATIM_URL", "https://nominatim.openstreetmap.org/reverse")
    elif os.getenv("GEOCODER_ENABLED", "0") != "1" or not geocoder_url:
        return fallback
    key = (provider, round(payload.latitude, 5), round(payload.longitude, 5))
    with geocoder_lock:
        if key in geocoder_cache:
            return geocoder_cache[key]
        time.sleep(max(0, 1.1 - (time.monotonic() - geocoder_last)))
        geocoder_last = time.monotonic()
        try:
            params = {"lat": payload.latitude, "lon": payload.longitude, "lang": "ru", "limit": 1} if provider == "photon" else {"lat": payload.latitude, "lon": payload.longitude, "format": "jsonv2", "accept-language": "ru", "zoom": 18}
            user_agent = os.getenv("GEOCODER_USER_AGENT", "ChuzhoeMesto/0.2")
            if "github.com/belikebigjohn/belike_hantaton-NotYourPlace" not in user_agent:
                user_agent += " (+https://github.com/belikebigjohn/belike_hantaton-NotYourPlace)"
            response = httpx.get(geocoder_url, params=params, headers={"User-Agent": user_agent, "Accept": "application/json"}, timeout=12)
            response.raise_for_status()
            data = response.json()
            if provider == "photon":
                features = data.get("features", [])
                properties = features[0].get("properties", {}) if features else {}
                components = [properties.get(field) for field in ("country", "state", "city", "district", "street", "housenumber", "name")]
                address = ", ".join(dict.fromkeys(str(value) for value in components if value))
                source = "Photon / komoot · © OpenStreetMap contributors"
            else:
                parts = data.get("address", {})
                city = next((parts.get(field) for field in ("city", "town", "village", "municipality", "hamlet") if parts.get(field)), None)
                road = next((parts.get(field) for field in ("road", "pedestrian", "residential", "footway") if parts.get(field)), None)
                components = [parts.get("country"), parts.get("state"), city, road, parts.get("house_number")]
                address = ", ".join(dict.fromkeys(str(value) for value in components if value)) or data.get("display_name")
                source = "Nominatim · © OpenStreetMap contributors"
            if not address:
                return {**fallback, "reason": "not_found"}
            result = {"address": address, "source": source, "needs_manual": False}
            geocoder_cache[key] = result
            return result
        except (httpx.HTTPError, ValueError, KeyError):
            return {**fallback, "reason": "unavailable"}


frontend_dist = ROOT / "frontend" / "dist"
if frontend_dist.exists():
    app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="frontend")
