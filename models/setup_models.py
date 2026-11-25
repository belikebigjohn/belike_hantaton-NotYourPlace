"""Fetch official upstream weights into this ignored model directory.

Run with Python 3.11/3.12 after backend requirements installation.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DOWNLOADS = {
    "plate-detector/yolo-v9-t-384-license-plate-end2end/yolo-v9-t-384-license-plates-end2end.onnx": "https://github.com/ankandrew/open-image-models/releases/download/assets/yolo-v9-t-384-license-plates-end2end.onnx",
    "nomeroff-ru-config.json": "https://models.vsp.net.ua/config_model/nomeroff-net-ocr-ru/model-shufflenet_v2_x2_0-2.json",
    "nomeroff-ru.ckpt": "https://nomeroff.net.ua/models/ocr/ru/torch/model_v3.3/shufflenet_v2_x2_0/anpr_ocr_ru_2022_11_22_shufflenet_v2_x2_0.ckpt",
    "road_sign_labels.yaml": "https://raw.githubusercontent.com/DL-teammm/web_service/main/model_info/class_labels.yaml",
}

SIGN_WEIGHT = "road_signs/best.pt"
SIZES = {
    "plate-detector/yolo-v9-t-384-license-plate-end2end/yolo-v9-t-384-license-plates-end2end.onnx": 7_771_218,
    "nomeroff-ru-config.json": 849,
    "nomeroff-ru.ckpt": 18_757_865,
    "road_sign_labels.yaml": 1_980,
    SIGN_WEIGHT: 208_131_839,
}


def validate(path: Path, expected_hash: str, expected_size: int) -> None:
    if not path.is_file():
        raise FileNotFoundError(f"Missing model artifact: {path.relative_to(ROOT)}")
    if path.stat().st_size != expected_size:
        raise RuntimeError(f"Unexpected model size: {path.relative_to(ROOT)}")
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    if digest.hexdigest() != expected_hash:
        raise RuntimeError(f"Model checksum changed: {path.relative_to(ROOT)}. Review upstream before using it.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify-only", action="store_true", help="Check local artifacts without network or model loading")
    args = parser.parse_args()
    reference = json.loads((ROOT / "checksums.reference.json").read_text(encoding="utf-8"))
    if set(reference) != set(SIZES):
        raise RuntimeError("Reference manifest and artifact list disagree")
    for name, expected_hash in reference.items():
        destination = ROOT / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        if not destination.exists() and not args.verify_only:
            temporary = destination.with_suffix(destination.suffix + ".partial")
            try:
                if name == SIGN_WEIGHT:
                    import gdown
                    if not gdown.download(id="1sbs04XXtNblH_YIhk-1DlO5hlhjtlmhn", output=str(temporary), quiet=False):
                        raise RuntimeError("Road-sign weight download failed")
                else:
                    urllib.request.urlretrieve(DOWNLOADS[name], temporary)
                validate(temporary, expected_hash, SIZES[name])
                temporary.replace(destination)
            finally:
                temporary.unlink(missing_ok=True)
        validate(destination, expected_hash, SIZES[name])
        print(f"verified {name}: {SIZES[name]} bytes")
    (ROOT / "checksums.local.json").write_text(json.dumps(reference, indent=2), encoding="utf-8")
    if not args.verify_only:
        sys.path.insert(0, str(ROOT.parent))
        from backend.cv import engine
        engine.load()
        status = engine.health()
        if any(status[name] != "loaded" for name in ("plate_detector", "plate_ocr")) or status["road_signs"]["status"] != "loaded":
            raise RuntimeError("Artifacts verified but a model failed to load. Check dependencies and run python -m backend.verify_models.")
        print("All models loaded. Run python -m backend.verify_models for inference smoke tests.")


if __name__ == "__main__":
    main()
