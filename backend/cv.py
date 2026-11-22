"""Real local inference, with explicit unknown results when a model cannot run."""
from __future__ import annotations

import os
import io
import math
import re
import threading
import time
from types import SimpleNamespace
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, UnidentifiedImageError

ROOT = Path(__file__).resolve().parents[1]
MODEL_DIR = Path(os.getenv("MODEL_DIR", ROOT / "models"))
LATIN_TO_RU = str.maketrans("ABEKMHOPCTYX", "АВЕКМНОРСТУХ")
RU_PATTERN = re.compile(r"^[АВЕКМНОРСТУХ]\d{3}[АВЕКМНОРСТУХ]{2}\d{2,3}$")


def normalize_plate(value: str) -> str:
    return re.sub(r"[^A-ZА-Я0-9]", "", value.upper()).translate(LATIN_TO_RU)


def model_score(value) -> float | None:
    if value is None:
        return None
    if isinstance(value, (list, tuple, np.ndarray)):
        if not np.asarray(value).size:
            return None
        value = np.mean(value)
    score = float(value)
    return score if math.isfinite(score) and 0 <= score <= 1 else None


def compare_plates(scene: dict, plate: dict) -> dict:
    status = "needs_review"
    if not scene["needs_review"] and not plate["needs_review"]:
        status = "match" if scene["value"] == plate["value"] else "mismatch"
    return {"status": status, "scene_value": scene["value"], "plate_value": plate["value"]}


def spatial_pair(signs: list[dict]) -> bool:
    """8.17 must be below and horizontally aligned with the parking sign."""
    for parking in (s for s in signs if s["class_code"] == "6.4"):
        x, y, w, h = parking["bbox"]
        for tablet in (s for s in signs if s["class_code"] == "8.17"):
            if parking.get("photo_id", "scene") != tablet.get("photo_id", "scene"):
                continue
            tx, ty, tw, th = tablet["bbox"]
            horizontal_overlap = max(0, min(x + w, tx + tw) - max(x, tx))
            vertical_gap = ty - (y + h)
            if horizontal_overlap / max(1, min(w, tw)) >= .45 and -.2 * h <= vertical_gap <= 1.8 * h and ty > y:
                return True
    return False


def decode_image(data: bytes) -> tuple[np.ndarray, dict]:
    if not data or len(data) > 15 * 1024 * 1024:
        raise ValueError("Выберите фотографию размером до 15 МБ.")
    jpeg = data.startswith(b"\xff\xd8\xff")
    png = data.startswith(b"\x89PNG\r\n\x1a\n")
    webp = data.startswith(b"RIFF") and data[8:12] == b"WEBP"
    if not (jpeg or png or webp):
        raise ValueError("Выберите фотографию JPEG, PNG или WebP.")
    # Check declared dimensions before allocating the full decoded raster.
    try:
        with Image.open(io.BytesIO(data)) as header:
            header_width, header_height = header.size
            if header_width * header_height > 40_000_000 or max(header_width, header_height) > 10000:
                raise ValueError("Размер изображения превышает 40 Мп. Выберите меньший снимок.")
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as error:
        raise ValueError("Не удалось прочитать фотографию. Выберите другой снимок.") from error
    try:
        image = cv2.imdecode(np.frombuffer(data, dtype=np.uint8), cv2.IMREAD_COLOR)
    except cv2.error as error:
        raise ValueError("Не удалось прочитать фотографию. Выберите другой снимок.") from error
    if image is None or image.size == 0:
        raise ValueError("Не удалось прочитать фотографию. Выберите другой снимок.")
    height, width = image.shape[:2]
    if width * height > 40_000_000 or max(width, height) > 10000:
        raise ValueError("Размер изображения превышает 40 Мп. Выберите меньший снимок.")
    return image, {**image_quality(image), "mime_type": "image/jpeg" if jpeg else "image/png" if png else "image/webp"}


def image_quality(image: np.ndarray) -> dict:
    height, width = image.shape[:2]
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    sample = cv2.resize(gray, (min(width, 640), max(1, round(height * min(width, 640) / width))))
    blur = float(cv2.Laplacian(sample, cv2.CV_64F).var())
    brightness = float(sample.mean())
    warnings = []
    if min(width, height) < 480:
        warnings.append("Небольшое изображение: проверьте, читаются ли детали.")
    if blur < 30:
        warnings.append("Возможно, снимок смазан. Проверьте читаемость номера.")
    if brightness < 35:
        warnings.append("Снимок тёмный. При возможности сделайте ещё один кадр.")
    if brightness > 225:
        warnings.append("Снимок засвечен. Проверьте блики и детали.")
    return {"width": width, "height": height, "blur_score": round(blur, 2), "brightness": round(brightness, 2), "warnings": warnings}


class CVEngine:
    def __init__(self):
        self.alpr = None
        self.sign_model = None
        self.sign_labels = {}
        self.errors = {}
        self.loaded = False
        self.lock = threading.Lock()

    def load(self):
        if self.loaded:
            return
        with self.lock:
            if self.loaded:
                return
            if os.getenv("CV_DISABLED") == "1":
                self.errors["disabled"] = "disabled by configuration"
                self.loaded = True
                return
            try:
                import open_image_models.detection.core.hub as detector_hub
                from fast_alpr import ALPR
                # No network downloads during user requests. setup_models.py owns downloads.
                detector_hub.MODEL_CACHE_DIR = MODEL_DIR / "plate-detector"
                detector = MODEL_DIR / "plate-detector/yolo-v9-t-384-license-plate-end2end/yolo-v9-t-384-license-plates-end2end.onnx"
                ocr = MODEL_DIR / "nomeroff-ru.ckpt"
                config = MODEL_DIR / "nomeroff-ru-config.json"
                if not all(p.is_file() for p in (detector, ocr, config)):
                    raise FileNotFoundError("Run python models/setup_models.py")
                from backend.nomeroff_ru import NomeroffRussianOCR
                self.alpr = ALPR(detector_conf_thresh=.3, detector_providers=["CPUExecutionProvider"], ocr=NomeroffRussianOCR(ocr, config))
            except Exception as error:
                self.errors["plate"] = type(error).__name__
            try:
                sign_path = MODEL_DIR / "road_signs/weights.verified.onnx"
                if not sign_path.exists():
                    sign_path = MODEL_DIR / "road_signs/best.pt"
                if not sign_path.exists():
                    raise FileNotFoundError("No road-sign weights")
                os.environ.setdefault("YOLO_CONFIG_DIR", str(MODEL_DIR / ".ultralytics"))
                from ultralytics import YOLO
                import yaml
                self.sign_model = YOLO(str(sign_path), task="detect")
                labels_path = MODEL_DIR / "road_sign_labels.yaml"
                if labels_path.exists():
                    self.sign_labels = yaml.safe_load(labels_path.read_text(encoding="utf-8"))["names"]
                if len(self.sign_model.names) != len(self.sign_labels):
                    raise ValueError("Weights class count differs from verified label mapping")
                for key, label in self.sign_labels.items():
                    if str(self.sign_model.names[int(key)]).replace(".", "") != str(label).replace(".", ""):
                        raise ValueError("Weights class order differs from label mapping")
            except Exception as error:
                self.sign_model = None
                self.errors["signs"] = type(error).__name__
            self.loaded = True

    def health(self):
        return {"opencv": cv2.__version__, "plate": {"ready": self.alpr is not None, "detector": "yolo-v9-t-384", "ocr": "nomeroff-ru-shufflenet-v3.3"}, "road_signs": {"ready": self.sign_model is not None, "classes": len(self.sign_labels), "supports": ["6.4", "8.17"] if self.sign_model else []}, "marking": {"ready": False}, "vehicle_disability_sign": {"ready": False}, "errors": self.errors}

    def _read_plate(self, image: np.ndarray, photo_id: str, recover: bool = True) -> tuple[dict, bool]:
        """Independent inference result; every box stays in its source image."""
        candidates = []
        complete = False
        crop_fallback = False
        if self.alpr is not None:
            try:
                for item in self._plate_predictions(image, recover=recover):
                    bbox = item.detection.bounding_box
                    image_h, image_w = image.shape[:2]
                    x1, y1 = max(0, int(bbox.x1)), max(0, int(bbox.y1))
                    x2, y2 = min(image_w, int(bbox.x2)), min(image_h, int(bbox.y2))
                    if x2 <= x1 or y2 <= y1:
                        continue
                    # A region panel is almost square; it must never be OCR'd as
                    # a complete single-line Russian registration plate.
                    if not 2.0 <= (x2 - x1) / (y2 - y1) <= 7.0:
                        continue
                    value = normalize_plate(item.ocr.text) if item.ocr else ""
                    score = model_score(item.ocr.confidence) if item.ocr else None
                    valid = bool(RU_PATTERN.fullmatch(value))
                    candidates.append({"value": value if valid else "", "raw_value": item.ocr.text if item.ocr else "", "confidence": score, "detection_confidence": model_score(item.detection.confidence), "bbox": [x1, y1, x2 - x1, y2 - y1], "photo_id": photo_id, "format_matches": valid, "source": getattr(item,"source","detector")})
                complete = True
            except Exception:
                # Keep partial results visible but never use them for confident comparison.
                complete = False
            # A supplied crop can already be the whole plate. The detector was
            # trained on scenes and may miss such tightly cropped inputs. Read
            # it directly only on the dedicated close-up input, with a plate-like
            # aspect ratio; never apply whole-scene OCR or invent a detection score.
            image_h, image_w = image.shape[:2]
            if (photo_id == "plate" and complete and hasattr(self.alpr, "ocr")
                    and not any(candidate["format_matches"] for candidate in candidates)
                    and image_h >= 20 and 2.5 <= image_w / image_h <= 6.5):
                try:
                    reading = self.alpr.ocr.predict(image)
                    value = normalize_plate(reading.text) if reading else ""
                    if RU_PATTERN.fullmatch(value):
                        candidates.append({"value": value, "raw_value": reading.text,
                            "confidence": model_score(reading.confidence), "detection_confidence": None,
                            "bbox": [0,0,image_w,image_h], "photo_id": photo_id,
                            "format_matches": True, "source": "whole_plate_crop"})
                        crop_fallback = True
                except Exception:
                    complete = False
        candidates.sort(key=lambda item: (item["format_matches"], item["confidence"] or 0), reverse=True)
        best = candidates[0] if candidates else {"value": "", "confidence": None, "bbox": None}
        needs_review = crop_fallback or best.get("source") == "small_plate_recovery" or not complete or not best["value"] or not RU_PATTERN.fullmatch(best["value"]) or (best["confidence"] or 0) < .9 or len(candidates) != 1
        return {"value": best["value"], "confidence": best["confidence"], "bbox": best["bbox"], "needs_review": bool(needs_review), "candidates": candidates, "photo_id": photo_id}, complete

    def _plate_predictions(self, image, recover=True):
        """Filter geometry before OCR and suppress nested region detections.

        Keep the published OCR's unconstrained reading: never fill missing
        characters or force a region fragment into the Russian plate grammar.
        """
        if not hasattr(self.alpr, "detector"):
            return self.alpr.predict(image)  # lightweight inference adapters
        height, width = image.shape[:2]
        detections = []
        for detection in self.alpr.detector.predict(image):
            box = detection.bounding_box
            x1, y1 = max(0, int(box.x1)), max(0, int(box.y1))
            x2, y2 = min(width, int(box.x2)), min(height, int(box.y2))
            if y2 > y1 and 2 <= (x2-x1)/(y2-y1) <= 7:
                detections.append((detection, (x1,y1,x2,y2)))
        results = []
        for detection, (x1,y1,x2,y2) in detections:
            area = (x2-x1)*(y2-y1)
            if any((ox2-ox1)*(oy2-oy1) > area*1.1 and
                   max(0,min(x2,ox2)-max(x1,ox1))*max(0,min(y2,oy2)-max(y1,oy1)) / area > .9
                   for _, (ox1,oy1,ox2,oy2) in detections):
                continue
            results.append(SimpleNamespace(detection=detection, ocr=self.alpr.ocr.predict(image[y1:y2,x1:x2])))
        if recover and not any(item.ocr and RU_PATTERN.fullmatch(normalize_plate(item.ocr.text)) for item in results):
            results.extend(self._small_plate_predictions(image))
        return results

    def _small_plate_predictions(self, image):
        """Bounded overlapping search, including region-panel anchors.

        Two independently cropped OCR readings must agree. The expanded box has
        no full-plate detector confidence, and always requires human review.
        """
        height,width=image.shape[:2]
        if min(height,width)<48: return []
        tile_w,tile_h=max(1,width//2),max(1,height//2)
        proposals=[]
        for y in [0,(height-tile_h)//2,height-tile_h]:
            for x in [0,(width-tile_w)//2,width-tile_w]:
                for detection in self.alpr.detector.predict(image[y:y+tile_h,x:x+tile_w]):
                    box=detection.bounding_box
                    x1,y1=max(0,x+int(box.x1)),max(0,y+int(box.y1))
                    x2,y2=min(width,x+int(box.x2)),min(height,y+int(box.y2))
                    h=y2-y1
                    if h<10 or x2<=x1: continue
                    ratio=(x2-x1)/h
                    if .65<=ratio<2.5:
                        # The visible region panel supplies location/height only;
                        # every letter and digit is read from the expanded crop.
                        first=(max(0,x2-round(4.5*h)),max(0,y1-round(.08*h)),min(width,x2+round(.08*h)),min(height,y2+round(.08*h)))
                        second=(max(0,x2-round(4.8*h)),first[1],first[2],first[3])
                    elif 2.5<=ratio<=7:
                        first=(x1,y1,x2,y2)
                        second=(max(0,x1-round(.04*(x2-x1))),max(0,y1-round(.08*h)),min(width,x2+round(.04*(x2-x1))),min(height,y2+round(.08*h)))
                    else: continue
                    if first==second: continue
                    if any(sum(abs(a-b) for a,b in zip(first,old[0]))<max(8,h*.5) for old in proposals): continue
                    proposals.append((first,second))
        results=[]
        for first,second in proposals[:12]:
            reads=[]
            for left,top,right,bottom in (first,second):
                reads.append(self.alpr.ocr.predict(image[top:bottom,left:right]))
            if not all(read and (model_score(read.confidence) or 0)>=.9 for read in reads): continue
            value=normalize_plate(reads[0].text)
            if not RU_PATTERN.fullmatch(value) or value!=normalize_plate(reads[1].text): continue
            left,top,right,bottom=first
            duplicate=False
            for old in results:
                b=old.detection.bounding_box
                overlap=max(0,min(right,b.x2)-max(left,b.x1))*max(0,min(bottom,b.y2)-max(top,b.y1))
                if normalize_plate(old.ocr.text)==value and overlap/max(1,min((right-left)*(bottom-top),(b.x2-b.x1)*(b.y2-b.y1)))>.6:
                    duplicate=True;break
            if not duplicate:
                results.append(SimpleNamespace(detection=SimpleNamespace(bounding_box=SimpleNamespace(x1=left,y1=top,x2=right,y2=bottom),confidence=None),ocr=reads[0],source="small_plate_recovery"))
        return results

    def analyze(self, scene: np.ndarray, plate: np.ndarray) -> dict:
        self.load()
        started = time.perf_counter()
        explanations, signs = [], []
        scene_quality = image_quality(scene)
        # Ultralytics predictor is stateful; serialize per process.
        with self.lock:
            scene_plate, scene_complete = self._read_plate(scene, "scene")
            close_plate, close_complete = self._read_plate(plate, "plate")
            plates_by_photo = {"scene": scene_plate, "plate": close_plate}
            comparison = compare_plates(scene_plate, close_plate)
            if not scene_complete or not close_complete or comparison["status"] == "needs_review":
                explanations.append("Сверьте номер на каждом снимке и исправьте его при необходимости.")
            elif comparison["status"] == "mismatch":
                explanations.append("На снимках прочитаны разные номера. Проверьте, что оба кадра относятся к одному автомобилю.")
            if self.sign_model is not None:
                try:
                    result = self.sign_model.predict(scene, conf=.35, verbose=False, device="cpu", imgsz=960)[0]
                    for box in result.boxes:
                        cls = int(box.cls.item())
                        code = str(self.sign_labels.get(cls, result.names.get(cls, cls)))
                        if code not in ("6.4", "8.17"):
                            continue
                        x1, y1, x2, y2 = box.xyxy[0].tolist()
                        image_h, image_w = scene.shape[:2]
                        x1, y1 = max(0, round(x1)), max(0, round(y1))
                        x2, y2 = min(image_w, round(x2)), min(image_h, round(y2))
                        if x2 <= x1 or y2 <= y1:
                            continue
                        signs.append({"class_code": code, "confidence": float(box.conf.item()), "bbox": [x1, y1, x2 - x1, y2 - y1], "photo_id": "scene"})
                    evidence = "detected" if spatial_pair(signs) else "not_detected" if not signs and not scene_quality["warnings"] else "unknown"
                    if evidence != "detected":
                        explanations.append("Проверьте, видно ли обозначение специального места и относится ли оно к автомобилю.")
                except Exception:
                    evidence = "unknown"
                    explanations.append("Проверьте обозначение места на общем снимке.")
            else:
                evidence = "unknown"
                explanations.append("Проверьте обозначение места на общем снимке.")
        selected = close_plate if close_plate["value"] else scene_plate if scene_plate["value"] else close_plate
        combined = close_plate["candidates"] + scene_plate["candidates"]
        top_plate = {**selected, "candidates": combined, "needs_review": selected["needs_review"] or comparison["status"] != "match"}
        return {"plate": top_plate, "plates_by_photo": plates_by_photo, "plate_comparison": comparison, "signs": signs, "parking_accessibility_evidence": evidence, "explanations": explanations, "model_versions": {"plate_detector": "yolo-v9-t-384-license-plate-end2end" if self.alpr else None, "plate_ocr": "nomeroff-ru-shufflenet-v3.3" if self.alpr else None, "road_signs": "DL-teammm-yolov8-146" if self.sign_model else None, "marking": None, "vehicle_disability_sign": None}, "elapsed_ms": round((time.perf_counter() - started) * 1000), "scope": "Only the supplied images; detection is not a legal finding."}


engine = CVEngine()
