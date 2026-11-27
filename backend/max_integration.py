"""Verified MAX Mini App identity and bot transport."""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import ssl
import time
from pathlib import Path
from urllib.parse import parse_qsl, urlparse

import certifi
import httpx

API = "https://platform-api2.max.ru"


def _client(timeout: float) -> httpx.AsyncClient:
    # Keep the extra trust roots scoped to outbound MAX requests.
    ca_bundle = os.getenv("MAX_CA_BUNDLE")
    if not ca_bundle:
        project_bundle = Path(__file__).resolve().parents[1] / "runtime-data" / "certs" / "max-ca.pem"
        if project_bundle.is_file():
            ca_bundle = str(project_bundle)
    verify = ssl.create_default_context(cafile=certifi.where()) if ca_bundle else True
    if ca_bundle:
        verify.load_verify_locations(cafile=ca_bundle)
    return httpx.AsyncClient(timeout=timeout, verify=verify)


def _upload_host_allowed(url: str) -> bool:
    parsed = urlparse(url)
    host = parsed.hostname or ""
    return (
        parsed.scheme == "https"
        and parsed.port in (None, 443)
        and not parsed.username
        and not parsed.password
        and (host == "platform-api2.max.ru" or host.endswith(".okcdn.ru") or host.endswith(".oneme.ru"))
    )


def validate_init_data(raw: str) -> int:
    token = os.getenv("MAX_BOT_TOKEN", "")
    if not token or len(raw) > 8192:
        raise ValueError("MAX integration is unavailable")
    pairs = parse_qsl(raw, keep_blank_values=True, strict_parsing=True)
    values = dict(pairs)
    if len(values) != len(pairs) or not values.get("hash"):
        raise ValueError("Invalid MAX launch data")
    signature = values.pop("hash")
    payload = "\n".join(f"{key}={value}" for key, value in sorted(values.items()))
    secret = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
    expected = hmac.new(secret, payload.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, signature):
        raise ValueError("Invalid MAX launch data")
    try:
        auth_date = int(values["auth_date"])
        user_id = int(json.loads(values["user"])["id"])
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
        raise ValueError("Invalid MAX user") from error
    if user_id <= 0 or abs(time.time() - auth_date) > 86400:
        raise ValueError("Expired MAX launch data")
    return user_id


def owner_for_user(user_id: int) -> str:
    return hashlib.sha256(f"max:{user_id}:{os.environ['MAX_BOT_TOKEN']}".encode()).hexdigest()


def _headers() -> dict[str, str]:
    return {"Authorization": os.environ["MAX_BOT_TOKEN"]}


async def send_message(user_id: int, text: str, attachments: list | None = None) -> None:
    async with _client(30) as client:
        response = await client.post(f"{API}/messages", params={"user_id": user_id}, headers=_headers(), json={"text": text, "attachments": attachments or []})
        response.raise_for_status()


async def send_welcome(user_id: int) -> None:
    username = os.getenv("MAX_BOT_USERNAME", "").lstrip("@")
    if not username:
        raise ValueError("MAX_BOT_USERNAME is missing")
    await send_message(user_id, "ЧужоеМесто поможет собрать обращение о возможном нарушении на специальном парковочном месте. Сделайте два снимка, проверьте номер, укажите место и получите пакет. Обстоятельства проверяет Госавтоинспекция.", [{"type": "inline_keyboard", "payload": {"buttons": [[{"type": "open_app", "text": "Открыть приложение", "web_app": username}]]}}])


async def send_package(user_id: int, package: bytes, report_id: str) -> None:
    filename = f"chuzhoe-mesto-{report_id[:8]}.zip"
    async with _client(90) as client:
        response = await client.post(f"{API}/uploads", params={"type": "file"}, headers=_headers())
        response.raise_for_status()
        upload = response.json()
        upload_url = upload["url"]
        if not _upload_host_allowed(upload_url):
            raise ValueError("Invalid MAX upload URL")
        response = await client.post(upload_url, files={"data": (filename, package, "application/zip")})
        response.raise_for_status()
        # MAX can return XML (<retval>1</retval>) after multipart upload.
        # The attachment token normally comes from POST /uploads.
        try:
            uploaded = response.json()
        except ValueError:
            uploaded = {}
        token = uploaded.get("token") if isinstance(uploaded, dict) else None
        token = token or upload.get("token")
        if not token:
            raise ValueError("MAX file token missing")
        body = {"text": "Пакет обращения готов. Сохраните архив и подайте обращение самостоятельно через официальный сервис.", "attachments": [{"type": "file", "payload": {"token": token}}]}
        for attempt in range(4):
            response = await client.post(f"{API}/messages", params={"user_id": user_id}, headers=_headers(), json=body)
            if response.is_success:
                return
            if response.status_code != 400 or "attachment.not.ready" not in response.text or attempt == 3:
                response.raise_for_status()
            import asyncio
            await asyncio.sleep(2 * (attempt + 1))
