# Model setup

Do not commit downloaded weights, caches, photos or .partial files. Run from the repository root with the project Python 3.12 virtual environment:

```powershell
.\.venv\Scripts\python.exe -m pip install -r backend/requirements.txt
.\.venv\Scripts\python.exe models/setup_models.py
.\.venv\Scripts\python.exe -m backend.verify_models
```

The setup fetches (1) YOLO-v9-t license plate detector ONNX from open-image-models official release, (2) Nomeroff Russian ShuffleNet OCR checkpoint/config from the author registry, (3) DL-teammm 146-class road-sign detector checkpoint from its README's Google Drive link, and (4) the matching class mapping. Paths are fixed under this folder. User requests never download or update models. The script checks exact sizes and SHA-256 against `checksums.reference.json` before accepting a download, then loads all three model components. It fails if loading fails. Run `python models/setup_models.py --verify-only` to audit existing files without network or ML imports. If an existing file fails validation, move that specific file aside and rerun setup after reviewing the pinned upstream source.

For macOS Monterey / Intel, use the Python 3.12 virtual environment from the repository root:

```sh
cd ~/apps/belike_hantaton-NotYourPlace
source .venv/bin/activate
python -m pip install -r backend/requirements.txt
python models/setup_models.py
python -m backend.verify_models
curl -fsS http://127.0.0.1:8000/api/health
```

`setup_models.py` verifies all files before importing PyTorch/ONNX/Ultralytics; the last two commands exercise inference and inspect the **currently running** app respectively. The already running server loads models once at startup, so its health will remain stale until the application process is restarted by its operator. Do not restart other services or the proxy. The pinned package set has not been validated on Monterey/Intel in this checkout; installation and inference there are the acceptance gate.

Nomeroff inference adapter is derived from GPL-3.0 code; full license is in `NOMEROFF_LICENSE.txt`. FastALPR is MIT. Ultralytics is AGPL-3.0 or commercial. DL-teammm repository and Drive weight files do not state a clear separate weight/data license; public/commercial distribution needs clarification from the authors. A public Drive link is not itself a license. The current local setup is for evaluation, not an assurance of redistribution rights.
