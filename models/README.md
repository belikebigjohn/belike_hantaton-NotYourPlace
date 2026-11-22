# Model setup

Do not commit downloaded weights, caches, photos or .partial files. Run from the repository root with the project Python 3.12 virtual environment:

```powershell
.\.venv\Scripts\python.exe -m pip install -r backend/requirements.txt
.\.venv\Scripts\python.exe models/setup_models.py
.\.venv\Scripts\python.exe -m backend.verify_models
```

The setup fetches (1) YOLO-v9-t license plate detector ONNX from open-image-models official release, (2) Nomeroff Russian ShuffleNet OCR checkpoint/config from the author registry, (3) DL-teammm 146-class road-sign detector checkpoint from its README's Google Drive link, and (4) the matching class mapping. Paths are fixed under this folder. User requests never download or update models. `checksums.local.json` records SHA-256 after setup; compare against the checked reference `checksums.reference.json` to detect changes.

Nomeroff inference adapter is derived from GPL-3.0 code; full license is in `NOMEROFF_LICENSE.txt`. FastALPR is MIT. Ultralytics is AGPL-3.0 or commercial. DL-teammm repository and Drive weight files do not state a clear separate weight/data license; public/commercial distribution needs clarification from the authors. A public Drive link is not itself a license. The current local setup is for evaluation, not an assurance of redistribution rights.
