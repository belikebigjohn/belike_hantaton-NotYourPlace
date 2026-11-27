"""Run real model smoke tests. Results are not independent street-scene metrics."""
from __future__ import annotations
import json
import platform
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import cv2
import numpy as np
from backend.cv import MODEL_DIR, ROOT, decode_image, engine


def main():
    validation = MODEL_DIR / "validation"
    validation.mkdir(parents=True, exist_ok=True)
    ru_path = validation / "ru.png"
    source = "https://raw.githubusercontent.com/ria-com/nomeroff-net/master/data/dataset/OptionsDetector/numberplate_options_example/test/img/ru.png"
    if not ru_path.exists():
        urllib.request.urlretrieve(source, ru_path)
    plate, _ = decode_image(ru_path.read_bytes())
    blank = np.full((720, 1280, 3), 180, dtype=np.uint8)
    engine.load()
    samples = [("upstream-russian-plate-crop", blank, plate, "Е300ЕУ763")]
    overview = ROOT / "demo/overview-demo.png"
    second_demo = ROOT / "demo/plate-demo.png"
    for name, path, expected in (("user-demo-first-car", overview, "А640МК198"), ("user-demo-second-car", second_demo, "А215МР198")):
        if path.exists():
            photo = decode_image(path.read_bytes())[0]
            samples.append((name, photo, photo, expected))
    results = []
    for name, scene, image, expected in samples:
        start = time.perf_counter()
        result = engine.analyze(scene, image)
        results.append({"name": name, "expected": expected, "exact_match": result["plate"]["value"] == expected, "duration_ms": round((time.perf_counter() - start) * 1000), "result": result})
    report = {"generated_at": datetime.now(timezone.utc).isoformat(), "device": platform.platform(), "processor": platform.processor(), "health": engine.health(), "samples": results, "source": source, "limits": "Upstream example may overlap training data; two user-provided demo photos show different vehicles and are checked separately. These samples do not estimate precision/recall or generalization. No independent road-sign or windshield/marking validation set is available."}
    output = ROOT / "docs/model-smoke-results.json"
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"health": report["health"], "results": [{key: sample[key] for key in ("name", "expected", "exact_match", "duration_ms")} for sample in results], "report": str(output)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
