"""Fetch official upstream weights into this ignored model directory.

Run with Python 3.11/3.12 after backend requirements installation.
"""
from __future__ import annotations
import hashlib
import json
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DOWNLOADS = {
    "plate-detector/yolo-v9-t-384-license-plate-end2end/yolo-v9-t-384-license-plates-end2end.onnx": "https://github.com/ankandrew/open-image-models/releases/download/assets/yolo-v9-t-384-license-plates-end2end.onnx",
    "nomeroff-ru-config.json": "https://models.vsp.net.ua/config_model/nomeroff-net-ocr-ru/model-shufflenet_v2_x2_0-2.json",
    "nomeroff-ru.ckpt": "https://nomeroff.net.ua/models/ocr/ru/torch/model_v3.3/shufflenet_v2_x2_0/anpr_ocr_ru_2022_11_22_shufflenet_v2_x2_0.ckpt",
    "road_sign_labels.yaml": "https://raw.githubusercontent.com/DL-teammm/web_service/main/model_info/class_labels.yaml",
    "NOMEROFF_LICENSE.txt": "https://raw.githubusercontent.com/ria-com/nomeroff-net/master/LICENSE",
}


def main():
    for name, url in DOWNLOADS.items():
        destination = ROOT / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        if not destination.exists():
            temporary = destination.with_suffix(destination.suffix + ".partial")
            urllib.request.urlretrieve(url, temporary)
            temporary.replace(destination)
        print(name, destination.stat().st_size)
    sign_destination = ROOT / "road_signs/best.pt"
    if not sign_destination.exists():
        import gdown
        sign_destination.parent.mkdir(exist_ok=True)
        gdown.download(id="1sbs04XXtNblH_YIhk-1DlO5hlhjtlmhn", output=str(sign_destination), quiet=False)
    files = [ROOT / name for name in DOWNLOADS if Path(name).suffix in {".onnx", ".ckpt", ".yaml", ".json"}] + [sign_destination]
    checksums = {str(path.relative_to(ROOT)).replace("\\", "/"): hashlib.sha256(path.read_bytes()).hexdigest() for path in files}
    reference_path = ROOT / "checksums.reference.json"
    if reference_path.exists():
        reference = json.loads(reference_path.read_text(encoding="utf-8"))
        for name, expected in reference.items():
            if checksums.get(name) != expected:
                raise RuntimeError(f"Model checksum changed: {name}. Review the upstream source before using these weights.")
    (ROOT / "checksums.local.json").write_text(json.dumps(checksums, indent=2), encoding="utf-8")
    print("Models downloaded; checksums.local.json written. Run python -m backend.verify_models to check class coverage.")


if __name__ == "__main__":
    main()
