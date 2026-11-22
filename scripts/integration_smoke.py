"""Exercise the running application using only clearly synthetic local fixtures.

No official submission, external geocoder call or real personal data is used.
Run: .venv/Scripts/python.exe scripts/integration_smoke.py
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4
from zipfile import ZipFile

import httpx

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--base-url', default='http://127.0.0.1:8000')
    args = parser.parse_args()
    if not args.base_url.startswith(('http://127.0.0.1:', 'http://localhost:')):
        raise SystemExit('Use a local test server. This script creates and deletes its own synthetic record.')
    result = {}
    started = time.perf_counter()
    with httpx.Client(base_url=args.base_url, timeout=90) as client:
        health = None
        ready_deadline = time.monotonic() + 25
        while time.monotonic() < ready_deadline:
            try:
                health = client.get('/api/health')
                break
            except httpx.ConnectError:
                time.sleep(.25)
        if health is None:
            raise RuntimeError('Local server did not become ready within 25 seconds.')
        health.raise_for_status()
        result['models'] = health.json()['models']
        key = str(uuid4())
        headers = {'Idempotency-Key': key}
        report = client.post('/api/reports', json={}, headers=headers)
        report.raise_for_status()
        report_id = report.json()['id']
        created_ids = {report_id}
        try:
            retried = client.post('/api/reports', json={}, headers=headers)
            retried.raise_for_status()
            created_ids.add(retried.json()['id'])
            assert retried.json()['id'] == report_id, 'Retry created a duplicate report'
            result['idempotent_create'] = True
            scene = (ROOT / 'demo/overview-demo.png').read_bytes()
            plate = (ROOT / 'demo/plate-demo.png').read_bytes()
            files = {'scene_photo': ('scene.png', scene, 'image/png'), 'plate_photo': ('plate.png', plate, 'image/png')}
            uploaded = client.post(f'/api/reports/{report_id}/photos', files=files, data={'scene_source': 'upload', 'plate_source': 'upload'})
            uploaded.raise_for_status()
            analyzed = client.post('/api/analyze', files=files)
            analyzed.raise_for_status()
            analysis = analyzed.json()
            assert 'needs_review' in analysis['plate']
            assert set(analysis['plates_by_photo']) == {'scene', 'plate'}
            assert all(candidate['photo_id'] == kind for kind, per_photo in analysis['plates_by_photo'].items() for candidate in per_photo['candidates'])
            result['analysis_ran'] = True
            result['both_photos_analyzed_with_scoped_boxes'] = True
            result['synthetic_ocr_requires_review'] = analysis['plate']['needs_review']
            analysis['plate_review'] = {'scene_value': 'А001АА86', 'plate_value': 'А001АА86', 'confirmed': True}
            data = {
                'status': 'prepared', 'plate': 'А001АА86', 'address': 'СИНТЕТИЧЕСКИЕ МАТЕРИАЛЫ. Реального события нет.',
                'observed_at': datetime.now(timezone(timedelta(hours=5))).isoformat(), 'designation': 'Обозначение требует проверки',
                'observation': 'Только проверка приложения на программно нарисованных кадрах.',
                'recipient': 'Демонстрационное подразделение', 'applicant_name': 'Демонстрационный заявитель',
                'applicant_email': 'demo@example.invalid', 'confirmed': True, 'analysis': analysis,
            }
            different_review = {'scene_value': 'А001АА86', 'plate_value': 'М456НО199', 'confirmed': True}
            rejected = client.patch(f'/api/reports/{report_id}', json={**data, 'analysis': {**analysis, 'plate_review': different_review}})
            assert rejected.status_code == 422, 'Different photo numbers must block package preparation'
            result['different_photo_numbers_block_package'] = True
            saved = client.patch(f'/api/reports/{report_id}', json=data)
            saved.raise_for_status()
            first = client.get(f'/api/reports/{report_id}/export')
            first.raise_for_status()
            second = client.get(f'/api/reports/{report_id}/export')
            second.raise_for_status()
            for package in (first, second):
                with ZipFile(io.BytesIO(package.content)) as archive:
                    manifest = json.loads(archive.read('manifest.json'))
                    assert archive.read('photos/scene.png') == scene
                    assert archive.read('photos/plate.png') == plate
                    assert all(hashlib.sha256(archive.read(entry['path'])).hexdigest() == entry['sha256'] for entry in manifest['files'])
                    assert {'statement.docx', 'statement.html', 'statement.txt'}.issubset(archive.namelist())
            result['repeat_export_originals_and_hashes'] = True
            listed = client.get('/api/reports')
            listed.raise_for_status()
            assert sum(item['id'] == report_id for item in listed.json()) == 1
            result['single_history_record'] = True
            with httpx.Client(base_url=args.base_url) as other:
                assert other.get(f'/api/reports/{report_id}').status_code == 404
                assert other.get(f'/api/reports/{report_id}/photos/scene').status_code == 404
                assert other.get(f'/api/reports/{report_id}/export').status_code == 404
            result['cross_session_isolation'] = True
            location = client.post('/api/geocode/reverse', json={'latitude': 52.52, 'longitude': 13.4})
            location.raise_for_status()
            assert location.json()['needs_manual'] is True
            result['geocoding_requires_consent'] = True
        finally:
            for own_id in created_ids:
                deleted = client.delete(f'/api/reports/{own_id}')
                deleted.raise_for_status()
                assert client.get(f'/api/reports/{own_id}').status_code == 404
            result['synthetic_record_deleted'] = True
    result['duration_seconds'] = round(time.perf_counter() - started, 2)
    result['scope'] = 'Local API integration with synthetic fixtures; not street CV validation or human completion-time measurement.'
    print(json.dumps(result, ensure_ascii=False, indent=2))
    (ROOT / 'docs/integration-smoke-results.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
