import cv2
import numpy as np
import pytest
from types import SimpleNamespace

from backend.cv import CVEngine, decode_image, normalize_plate, spatial_pair


def test_normalization_does_not_invent_digits_or_confidence():
    assert normalize_plate(" A 123 BC 186 ") == "А123ВС186"
    assert normalize_plate("A?12OB") == "А12ОВ"


def test_spatial_relation_requires_aligned_pair():
    signs = [{"class_code": "6.4", "bbox": [100, 100, 60, 80]}, {"class_code": "8.17", "bbox": [104, 190, 50, 30]}]
    assert spatial_pair(signs)
    signs[1]["bbox"] = [700, 190, 50, 30]
    assert not spatial_pair(signs)
    signs[1]["bbox"] = [104, 190, 50, 30]
    signs[0]["photo_id"] = "scene"
    signs[1]["photo_id"] = "different-photo"
    assert not spatial_pair(signs)


def test_missing_models_and_no_detection_are_not_success(monkeypatch):
    engine = CVEngine()
    monkeypatch.setenv("CV_DISABLED", "1")
    image = np.full((480, 640, 3), 120, dtype=np.uint8)
    result = engine.analyze(image, image)
    assert result["plate"]["value"] == ""
    assert result["plate"]["confidence"] is None
    assert result["plate"]["needs_review"]
    assert result["parking_accessibility_evidence"] == "unknown"
    assert result["analysis_status"] == "partial_model_unavailable"
    health = engine.health()
    assert health["plate_detector"] == "disabled"
    assert health["plate_ocr"] == "disabled"
    assert health["road_signs"]["status"] == "disabled"


def test_health_distinguishes_missing_artifacts_without_public_paths(monkeypatch, tmp_path):
    import backend.cv as cv
    monkeypatch.delenv("CV_DISABLED", raising=False)
    monkeypatch.setattr(cv, "MODEL_DIR", tmp_path)
    engine = CVEngine()
    engine.load()
    health = engine.health()
    assert health["plate_detector"] == "missing"
    assert health["plate_ocr"] == "missing"
    assert health["road_signs"]["status"] == "missing"
    assert "setup_models.py" in health["repair"]
    assert str(tmp_path) not in str(health)


def test_bad_upload_and_dark_quality():
    with pytest.raises(ValueError):
        decode_image(b"not an image")
    dark = np.zeros((480, 640, 3), dtype=np.uint8)
    _, quality = decode_image(cv2.imencode(".png", dark)[1].tobytes())
    assert quality["brightness"] == 0
    assert len(quality["warnings"]) >= 2


def test_camera_preview_reports_quality_without_inventing_detections(monkeypatch):
    engine = CVEngine()
    monkeypatch.setenv("CV_DISABLED", "1")
    image = np.zeros((480, 640, 3), dtype=np.uint8)
    preview = engine.preview(image, "scene")
    assert preview["boxes"] == []
    assert preview["plate_available"] is False
    assert preview["sign_available"] is False
    assert any("тёмный" in warning for warning in preview["quality"]["warnings"])


@pytest.mark.parametrize("score,expected_review", [(0.97, False), (0.61, True)])
def test_model_score_controls_review_without_regexp_confidence(score, expected_review):
    engine = CVEngine()
    engine.loaded = True
    box = SimpleNamespace(x1=10, y1=10, x2=130, y2=40)
    prediction = SimpleNamespace(detection=SimpleNamespace(bounding_box=box, confidence=.8), ocr=SimpleNamespace(text="A123BC186", confidence=score))
    engine.alpr = SimpleNamespace(predict=lambda image: [prediction])
    image = np.zeros((480, 640, 3), dtype=np.uint8)
    result = engine.analyze(image, image)
    assert result["plate"]["value"] == "А123ВС186"
    assert result["plate"]["confidence"] == score
    assert result["plate"]["needs_review"] is expected_review
    assert result["parking_accessibility_evidence"] == "unknown"


def image_with_details():
    random = np.random.default_rng(0)
    return random.integers(30, 220, size=(480, 640, 3), dtype=np.uint8)


def sign_prediction(code, bbox):
    return SimpleNamespace(cls=np.array(code), conf=np.array(.8), xyxy=np.array([bbox]))


@pytest.mark.parametrize("boxes,expected", [
    ([], "not_detected"),
    ([sign_prediction(34, [100, 100, 160, 180])], "unknown"),
    ([sign_prediction(34, [100, 100, 160, 180]), sign_prediction(138, [104, 190, 154, 220])], "detected"),
    ([sign_prediction(34, [100, 100, 160, 180]), sign_prediction(138, [400, 190, 450, 220])], "unknown"),
])
def test_distinguishes_successful_empty_partial_unrelated_and_paired_inference(boxes, expected):
    engine = CVEngine()
    engine.loaded = True
    engine.sign_labels = {34: "6.4", 138: "8.17"}
    result = SimpleNamespace(boxes=boxes, names=engine.sign_labels)
    engine.sign_model = SimpleNamespace(predict=lambda *args, **kwargs: [result])
    image = image_with_details()
    assert engine.analyze(image, image)["parking_accessibility_evidence"] == expected


def test_poor_photo_and_inference_failure_are_unknown():
    engine = CVEngine()
    engine.loaded = True
    engine.sign_model = SimpleNamespace(predict=lambda *args, **kwargs: [SimpleNamespace(boxes=[], names={})])
    image = np.zeros((480, 640, 3), dtype=np.uint8)
    assert engine.analyze(image, image)["parking_accessibility_evidence"] == "unknown"
    def failing(*args, **kwargs):
        raise RuntimeError("test model failure")
    engine.sign_model = SimpleNamespace(predict=failing)
    assert engine.analyze(image_with_details(), image)["parking_accessibility_evidence"] == "unknown"


def test_partial_ocr_failure_still_requires_manual_review():
    engine = CVEngine()
    engine.loaded = True
    box = SimpleNamespace(x1=10, y1=10, x2=130, y2=40)
    prediction = SimpleNamespace(detection=SimpleNamespace(bounding_box=box, confidence=.98), ocr=SimpleNamespace(text="A123BC186", confidence=.99))
    def partial(image):
        yield prediction
        raise RuntimeError("second candidate failed")
    engine.alpr = SimpleNamespace(predict=partial)
    image = image_with_details()
    assert engine.analyze(image, image)["plate"]["needs_review"] is True


def plate_prediction(text, score=.98, bounds=(10, 10, 130, 40)):
    x1, y1, x2, y2 = bounds
    return SimpleNamespace(detection=SimpleNamespace(bounding_box=SimpleNamespace(x1=x1, y1=y1, x2=x2, y2=y2), confidence=.95), ocr=SimpleNamespace(text=text, confidence=score))


@pytest.mark.parametrize("scene_candidates,close_candidates,expected", [
    ([plate_prediction("A123BC186")], [plate_prediction("А123ВС186")], "match"),
    ([plate_prediction("A123BC186")], [plate_prediction("B321AA186")], "mismatch"),
    ([], [plate_prediction("A123BC186")], "needs_review"),
    ([plate_prediction("A123BC186")], [], "needs_review"),
    ([plate_prediction("A123BC186", .65)], [plate_prediction("A123BC186")], "needs_review"),
    ([plate_prediction("A123BC186"), plate_prediction("B321AA186")], [plate_prediction("A123BC186")], "needs_review"),
    ([plate_prediction("A123BC186")], [plate_prediction("A123BC186"), plate_prediction("B321AA186")], "needs_review"),
])
def test_independent_ocr_of_both_photos_and_comparison(scene_candidates, close_candidates, expected):
    scene = image_with_details()
    close = image_with_details().copy()
    engine = CVEngine()
    engine.loaded = True
    calls = []
    def predict(image):
        calls.append(image)
        return scene_candidates if image is scene else close_candidates
    engine.alpr = SimpleNamespace(predict=predict)
    result = engine.analyze(scene, close)
    assert len(calls) == 2
    assert calls[0] is scene and calls[1] is close
    assert result["plate_comparison"]["status"] == expected
    assert result["plates_by_photo"]["scene"]["photo_id"] == "scene"
    assert result["plates_by_photo"]["plate"]["photo_id"] == "plate"
    assert len(result["plate"]["candidates"]) == len(scene_candidates) + len(close_candidates)
    assert all(candidate["photo_id"] == "scene" for candidate in result["plates_by_photo"]["scene"]["candidates"])
    assert all(candidate["photo_id"] == "plate" for candidate in result["plates_by_photo"]["plate"]["candidates"])
    assert result["plate"]["needs_review"] is (expected != "match")


def test_scene_fallback_never_attaches_scene_bbox_to_close_photo():
    scene, close = image_with_details(), image_with_details().copy()
    engine = CVEngine()
    engine.loaded = True
    engine.alpr = SimpleNamespace(predict=lambda image: [plate_prediction("A123BC186", bounds=(80, 100, 230, 150))] if image is scene else [])
    result = engine.analyze(scene, close)
    assert result["plate"]["value"] == "А123ВС186"
    assert result["plate"]["photo_id"] == "scene"
    assert result["plate"]["bbox"] == [80, 100, 150, 50]
    assert result["plates_by_photo"]["plate"]["bbox"] is None
    assert result["plate_comparison"]["status"] == "needs_review"


def test_comparison_score_cannot_be_nan_or_outside_model_range():
    image = image_with_details()
    engine = CVEngine()
    engine.loaded = True
    engine.alpr = SimpleNamespace(predict=lambda image: [plate_prediction("A123BC186", float("nan"))])
    result = engine.analyze(image, image)
    assert result["plate_comparison"]["status"] == "needs_review"
    assert result["plate"]["confidence"] is None


def test_region_fragment_is_never_a_complete_number_even_with_high_ocr_score():
    engine = CVEngine()
    engine.loaded = True
    engine.alpr = SimpleNamespace(predict=lambda image: [plate_prediction("A999AA199", .999, (110,10,140,40)), plate_prediction("A123BC77", .91, (10,10,140,40))])
    result = engine.analyze(image_with_details(), image_with_details())
    assert result["plate"]["value"] == "А123ВС77"
    assert len(result["plates_by_photo"]["plate"]["candidates"]) == 1


def test_invalid_ocr_is_not_prefilled_or_ranked_above_complete_plate():
    engine = CVEngine()
    engine.loaded = True
    engine.alpr = SimpleNamespace(predict=lambda image: [plate_prediction("186", .999), plate_prediction("A123BC77", .91, (200,10,330,40))])
    result = engine.analyze(image_with_details(), image_with_details())
    assert result["plate"]["value"] == "А123ВС77"
    bad = result["plates_by_photo"]["plate"]["candidates"][1]
    assert bad["value"] == "" and bad["raw_value"] == "186"


def test_geometry_and_nested_boxes_are_filtered_before_ocr():
    engine = CVEngine()
    predictions=[plate_prediction("", bounds=b).detection for b in [(0,0,200,45),(140,1,190,44),(3,2,190,42)]]
    crops=[]
    def ocr(crop):
        crops.append(crop.shape)
        return SimpleNamespace(text="A123BC77",confidence=.95)
    engine.alpr=SimpleNamespace(detector=SimpleNamespace(predict=lambda image: predictions),ocr=SimpleNamespace(predict=ocr))
    result,_=engine._read_plate(image_with_details(),"scene")
    assert result["value"] == "А123ВС77"
    assert crops == [(45,200,3)]


def test_whole_plate_crop_can_be_read_when_scene_detector_misses_it():
    engine=CVEngine()
    engine.alpr=SimpleNamespace(detector=SimpleNamespace(predict=lambda image: []),ocr=SimpleNamespace(predict=lambda image: SimpleNamespace(text='A123BC77',confidence=.99)))
    image=np.full((50,240,3),180,dtype=np.uint8)
    result,complete=engine._read_plate(image,'plate')
    assert complete and result['value']=='А123ВС77'
    assert result['needs_review'] is True
    assert result['candidates'][0]['detection_confidence'] is None
    assert result['candidates'][0]['source']=='whole_plate_crop'
    assert engine._read_plate(image,'scene')[0]['value']==''
    # Ordinary 16:9 photos cannot enter this fallback.
    assert engine._read_plate(np.zeros((720,1280,3),dtype=np.uint8),'plate')[0]['value']==''


@pytest.mark.parametrize('readings,expected', [
    ([('A123BC77',.99),('A123BC77',.98)],'А123ВС77'),
    ([('A123BC77',.99),('A123BC99',.99)],''),
    ([('A123BC77',.99),('A123BC77',.6)],''),
    ([('77',.99),('77',.99)],''),
])
def test_tiled_region_anchor_requires_two_agreeing_full_ocr_readings(readings,expected):
    engine=CVEngine()
    calls=[]
    def detect(image):
        calls.append(image.shape)
        # Main image first, then a region fragment in the first search tile.
        return [plate_prediction('',bounds=(220,100,250,125)).detection] if len(calls)==2 else []
    values=iter(readings)
    def ocr(image):
        text,score=next(values)
        return SimpleNamespace(text=text,confidence=score)
    engine.alpr=SimpleNamespace(detector=SimpleNamespace(predict=detect),ocr=SimpleNamespace(predict=ocr))
    result,_=engine._read_plate(np.zeros((800,1000,3),dtype=np.uint8),'scene')
    assert result['value']==expected
    assert len(calls)==10
    if expected:
        assert result['bbox']==[138,98,114,29]
        assert result['needs_review'] is True
        assert result['candidates'][0]['source']=='small_plate_recovery'
        assert result['candidates'][0]['detection_confidence'] is None


@pytest.mark.parametrize('count,expected',[(1,''),(2,''),(3,'А123ВС77')])
def test_border_recovery_requires_consensus_across_three_regions(monkeypatch,count,expected):
    import backend.plate_geometry as geometry
    engine=CVEngine()
    monkeypatch.setattr(geometry,'plate_border_proposals',lambda image:[(10+i,10,200,60) for i in range(count)])
    engine.alpr=SimpleNamespace(ocr=SimpleNamespace(predict=lambda crop:SimpleNamespace(text='A123BC77',confidence=.99)))
    result=engine._large_plate_predictions(np.zeros((100,240,3),dtype=np.uint8))
    assert (normalize_plate(result[0].ocr.text) if result else '')==expected
    if result: assert result[0].detection.confidence is None


def test_border_proposals_are_bounded_and_blank_images_have_no_proposals():
    from backend.plate_geometry import plate_border_proposals
    assert plate_border_proposals(np.zeros((200,400,3),dtype=np.uint8))==[]
    image=np.zeros((300,600,3),dtype=np.uint8)
    cv2.rectangle(image,(50,100),(550,200),(255,255,255),2)
    boxes=plate_border_proposals(image)
    assert boxes and len(boxes)<=24
    assert all(0<=x1<x2<=600 and 0<=y1<y2<=300 for x1,y1,x2,y2 in boxes)
