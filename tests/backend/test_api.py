import hashlib
import io
import json
from zipfile import ZipFile
from uuid import uuid4
from concurrent.futures import ThreadPoolExecutor

import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient

from backend import main


@pytest.fixture
def clients(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "DATA_DIR", tmp_path)
    monkeypatch.setattr(main, "DATABASE", tmp_path / "reports.sqlite3")
    monkeypatch.setattr(main.engine, "load", lambda: None)
    with TestClient(main.app) as first, TestClient(main.app) as second:
        yield first, second


@pytest.fixture
def picture():
    image = np.full((720, 1280, 3), 150, dtype=np.uint8)
    cv2.putText(image, "TEST", (150, 350), cv2.FONT_HERSHEY_SIMPLEX, 3, (255, 255, 255), 5)
    return cv2.imencode(".png", image)[1].tobytes()


def create(first):
    response = first.post("/api/reports", json={})
    assert response.status_code == 201
    return response.json()["id"]


def attach(first, report_id, picture):
    return first.post(f"/api/reports/{report_id}/photos", files={"scene_photo": ("scene.png", picture, "image/png"), "plate_photo": ("plate.png", picture, "image/png")}, data={"scene_source": "camera", "scene_captured_at": "2026-11-21T12:00:00+05:00"})


def test_full_report_export_and_cross_session_isolation(clients, picture):
    first, second = clients
    report_id = create(first)
    attached = attach(first, report_id, picture)
    assert attached.status_code == 200
    metadata = attached.json()["photos"]["scene"]
    assert metadata["sha256"] == hashlib.sha256(picture).hexdigest()
    assert metadata["source"] == "camera"
    assert first.get(metadata["url"]).content == picture
    assert second.get(f"/api/reports/{report_id}").status_code == 404
    assert second.get(metadata["url"]).status_code == 404
    payload = {"plate": "А123ВС186", "address": "Тестовый адрес", "observed_at": "2026-11-21T12:00:00+05:00", "designation": "Знак и табличка", "confirmed": True, "status": "prepared", "applicant_name": "Тестовый Заявитель", "applicant_email": "test@example.invalid", "recipient": "Госавтоинспекция"}
    prepared = first.patch(f"/api/reports/{report_id}", json=payload)
    assert prepared.status_code == 200
    exported = first.get(f"/api/reports/{report_id}/export")
    assert exported.status_code == 200
    with ZipFile(io.BytesIO(exported.content)) as archive:
        assert "statement.docx" in archive.namelist()
        manifest = json.loads(archive.read("manifest.json"))
        for entry in manifest["files"]:
            assert hashlib.sha256(archive.read(entry["path"])).hexdigest() == entry["sha256"]
    assert len(first.get("/api/reports").json()) == 1
    assert second.delete(f"/api/reports/{report_id}").status_code == 404
    assert first.delete(f"/api/reports/{report_id}").status_code == 200
    assert first.get(metadata["url"]).status_code == 404


def test_invalid_second_photo_does_not_leave_partial_upload(clients, picture):
    first, _ = clients
    report_id = create(first)
    response = first.post(f"/api/reports/{report_id}/photos", files={"scene_photo": ("good.png", picture), "plate_photo": ("bad.png", b"not a photo")})
    assert response.status_code == 422
    assert first.get(f"/api/reports/{report_id}").json()["photos"] == {}
    assert list(main.DATA_DIR.rglob("*.png")) == []


def test_retake_invalidates_confirmation_and_keeps_original(clients, picture):
    first, _ = clients
    report_id = create(first)
    assert attach(first, report_id, picture).status_code == 200
    assert first.patch(f"/api/reports/{report_id}", json={"confirmed": True, "analysis": {"test": True}}).status_code == 200
    response = first.post(f"/api/reports/{report_id}/photos", files={"plate_photo": ("replacement.png", picture)})
    assert response.status_code == 200
    assert response.json()["confirmed"] is False
    assert response.json()["analysis"] is None
    assert len(list(main.DATA_DIR.rglob("*.png"))) == 3
    assert first.get(f"/api/reports/{report_id}/export").status_code == 422


def test_foreign_origin_rejected(clients):
    first, _ = clients
    response = first.post("/api/reports", json={}, headers={"Origin": "https://foreign.example"})
    assert response.status_code == 403


def test_geocoder_failure_manual_fallback(clients, monkeypatch):
    first, _ = clients
    monkeypatch.setenv("GEOCODER_ENABLED", "0")
    response = first.post("/api/geocode/reverse", json={"latitude": 56.8, "longitude": 60.6})
    assert response.json() == {"address": None, "source": "manual", "needs_manual": True}


def test_photon_reverse_success_when_explicitly_configured(clients, monkeypatch):
    from types import SimpleNamespace
    first, _ = clients
    monkeypatch.setenv("GEOCODER_ENABLED", "1")
    monkeypatch.setenv("GEOCODER_PROVIDER", "photon")
    monkeypatch.setenv("GEOCODER_URL", "https://geocoder.example.invalid/reverse")
    main.geocoder_cache.clear()
    monkeypatch.setattr(main.httpx, "get", lambda *args, **kwargs: SimpleNamespace(raise_for_status=lambda: None, json=lambda: {"features": [{"properties": {"country": "Россия", "city": "Екатеринбург", "street": "улица Малышева", "housenumber": "1"}}]}))
    response = first.post("/api/geocode/reverse", json={"latitude": 56.8, "longitude": 60.6, "consent": True})
    assert response.status_code == 200
    assert response.json()["address"] == "Россия, Екатеринбург, улица Малышева, 1"
    assert response.json()["needs_manual"] is False
    assert "OpenStreetMap" in response.json()["source"]


def test_geocoder_never_sends_coordinates_without_user_consent(clients, monkeypatch):
    first, _ = clients
    monkeypatch.setenv("GEOCODER_ENABLED", "1")
    monkeypatch.setenv("GEOCODER_URL", "https://geocoder.example.invalid/reverse")
    def forbidden(*args, **kwargs):
        raise AssertionError("External request must not happen without consent")
    monkeypatch.setattr(main.httpx, "get", forbidden)
    response = first.post("/api/geocode/reverse", json={"latitude": 56.8, "longitude": 60.6})
    assert response.json()["needs_manual"] is True


def test_report_creation_key_is_durable_and_owner_scoped(clients):
    first, second = clients
    key = str(uuid4())
    headers = {"Idempotency-Key": key}
    report = first.post("/api/reports", json={"plate": "А123ВС186"}, headers=headers).json()
    replay = first.post("/api/reports", json={"plate": "В321АА186"}, headers=headers).json()
    assert replay["id"] == report["id"]
    assert replay["plate"] == "А123ВС186"
    assert len(first.get("/api/reports").json()) == 1
    other = second.post("/api/reports", json={}, headers=headers).json()
    assert other["id"] != report["id"]
    assert first.delete(f"/api/reports/{report['id']}").status_code == 200
    with main.connection() as database:
        assert database.execute("SELECT COUNT(*) FROM report_creation_keys WHERE report_id=?", (report["id"],)).fetchone()[0] == 0
    recreated = first.post("/api/reports", json={}, headers=headers).json()
    assert recreated["id"] != report["id"]


def test_report_creation_key_invalid_rejected(clients):
    first, _ = clients
    assert first.post("/api/reports", json={}, headers={"Idempotency-Key": "invalid"}).status_code == 422
    assert first.get("/api/reports").json() == []


def test_concurrent_creation_retry_produces_one_record(clients):
    first, _ = clients
    first.get("/api/health")  # Establish the same owner before retrying creation.
    key = str(uuid4())
    def create_once(_):
        response = first.post("/api/reports", json={}, headers={"Idempotency-Key": key})
        assert response.status_code == 201
        return response.json()["id"]
    with ThreadPoolExecutor(max_workers=2) as pool:
        identifiers = list(pool.map(create_once, range(2)))
    assert len(set(identifiers)) == 1
    assert len(first.get("/api/reports").json()) == 1


def test_import_never_claims_capture_time_and_camera_timestamp_validated(clients, picture):
    first, _ = clients
    report_id = create(first)
    imported = first.post(f"/api/reports/{report_id}/photos", files={"scene_photo": ("scene.png", picture)}, data={"scene_source": "upload", "scene_captured_at": "2026-11-21T12:00:00+05:00"})
    assert imported.status_code == 200
    assert imported.json()["photos"]["scene"]["captured_at"] is None
    invalid = first.post(f"/api/reports/{report_id}/photos", files={"plate_photo": ("plate.png", picture)}, data={"plate_source": "camera", "plate_captured_at": "not-a-date"})
    assert invalid.status_code == 422
    assert "plate" not in first.get(f"/api/reports/{report_id}").json()["photos"]


def test_changed_facts_require_fresh_confirmation_even_after_an_export(clients, picture):
    first, _ = clients
    report_id = create(first)
    assert attach(first, report_id, picture).status_code == 200
    payload = {"plate": "А123ВС186", "address": "Тестовый адрес", "observed_at": "2026-11-21T12:00:00+05:00", "designation": "Знак и табличка", "confirmed": True, "status": "prepared", "applicant_name": "Тестовый Заявитель", "applicant_email": "test@example.invalid", "recipient": "Госавтоинспекция"}
    assert first.patch(f"/api/reports/{report_id}", json=payload).status_code == 200
    assert first.get(f"/api/reports/{report_id}/export").status_code == 200
    changed = first.patch(f"/api/reports/{report_id}", json={"plate": "В321АА186"})
    assert changed.status_code == 200
    assert changed.json()["status"] == "draft"
    assert changed.json()["confirmed"] is False
    assert first.get(f"/api/reports/{report_id}/export").status_code == 422
    assert first.patch(f"/api/reports/{report_id}", json={"status": "prepared", "confirmed": True}).status_code == 200
    assert first.get(f"/api/reports/{report_id}/export").status_code == 200


def test_two_photo_numbers_must_agree_before_package_preparation(clients, picture):
    first, _ = clients
    report_id = create(first)
    assert attach(first, report_id, picture).status_code == 200
    payload = {"plate": "А123ВС186", "address": "Тестовый адрес", "observed_at": "2026-11-21T12:00:00+05:00", "designation": "Знак и табличка", "confirmed": True, "status": "prepared", "applicant_name": "Тестовый Заявитель", "applicant_email": "test@example.invalid", "recipient": "Госавтоинспекция"}
    analysis = {"plates_by_photo": {"scene": {"value": "А123ВС186"}, "plate": {"value": "М456НО199"}}}
    missing = first.patch(f"/api/reports/{report_id}", json={**payload, "analysis": analysis})
    assert missing.status_code == 422
    analysis["plate_review"] = {"scene_value": "А123ВС186", "plate_value": "М456НО199", "confirmed": True}
    mismatch = first.patch(f"/api/reports/{report_id}", json={**payload, "analysis": analysis})
    assert mismatch.status_code == 422
    assert first.get(f"/api/reports/{report_id}/export").status_code == 422
    analysis["plate_review"] = {"scene_value": "A 123 BC 186", "plate_value": "А123ВС186", "confirmed": False}
    assert first.patch(f"/api/reports/{report_id}", json={**payload, "analysis": analysis}).status_code == 422
    analysis["plate_review"]["confirmed"] = True
    matched = first.patch(f"/api/reports/{report_id}", json={**payload, "analysis": analysis})
    assert matched.status_code == 200
    assert first.get(f"/api/reports/{report_id}/export").status_code == 200
    different_final = first.patch(f"/api/reports/{report_id}", json={**payload, "plate": "В321АА186", "analysis": analysis})
    assert different_final.status_code == 422

def test_map_config_exposes_only_public_browser_key(clients,monkeypatch):
    first,_=clients
    monkeypatch.delenv('YANDEX_MAPS_API_KEY',raising=False)
    assert first.get('/api/map-config').json()=={'yandex_js_key':''}
    monkeypatch.setenv('YANDEX_MAPS_API_KEY','public-browser-test-key')
    monkeypatch.setenv('PRIVATE_EXAMPLE_SECRET','must-not-be-exposed')
    assert first.get('/api/map-config').json()=={'yandex_js_key':'public-browser-test-key'}
