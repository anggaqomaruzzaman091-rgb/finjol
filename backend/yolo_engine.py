"""
YOLOv8 KTP field detector — ported from `yolov8_train_ktp_roboflow.ipynb`.

The trained model returns bounding boxes for each labeled KTP field
(NIK, nama, alamat, …). We then crop the source image at each box and
run the OCR engines (EasyOCR / Tesseract) on just that crop — much
higher precision than full-page OCR because the OCR engine only sees
one short line at a time, with no surrounding labels to confuse the
field parser.

Offline & graceful degradation
------------------------------
* `is_available()` returns True only if `ultralytics` is importable AND
  a model file is present at one of:
    - the path in the `KTP_YOLO_MODEL` env var
    - `backend/models/ktp_yolo.pt`
* Loading is lazy and one-shot per process.
* If the model is missing, ocr_service falls back to the current
  full-page dual-engine path — no errors raised.

Class label → field key mapping
-------------------------------
Roboflow's KTP dataset uses several naming conventions across versions
(`ttl`, `tempat_tgl_lahir`, `tempat_lahir`, …). We accept all common
aliases below; unknown labels are returned with the empty key so they
can still be inspected in the response.
"""

from __future__ import annotations

import os
from typing import Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Model discovery
# ---------------------------------------------------------------------------

_MODELS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models")

# Field detector — 17 KTP field classes. Override path with KTP_YOLO_MODEL.
_DEFAULT_MODEL_PATH = os.path.join(_MODELS_DIR, "ktp_yolo.pt")
# Card detector — single class, locates the KTP card itself in a wider photo
# so the field detector runs on a tight crop instead of the full scene.
# Override with KTP_CARD_MODEL. When this file is absent the pipeline
# transparently falls back to single-stage field detection on the input.
_DEFAULT_CARD_MODEL_PATH = os.path.join(_MODELS_DIR, "ktp_card.pt")


def _resolve_model_path() -> Optional[str]:
    env_path = os.getenv("KTP_YOLO_MODEL")
    if env_path and os.path.exists(env_path):
        return env_path
    if os.path.exists(_DEFAULT_MODEL_PATH):
        return _DEFAULT_MODEL_PATH
    return None


def _resolve_card_model_path() -> Optional[str]:
    env_path = os.getenv("KTP_CARD_MODEL")
    if env_path and os.path.exists(env_path):
        return env_path
    if os.path.exists(_DEFAULT_CARD_MODEL_PATH):
        return _DEFAULT_CARD_MODEL_PATH
    return None


# ---------------------------------------------------------------------------
# Availability check — cached so we don't import ultralytics on every call
# ---------------------------------------------------------------------------

_CHECKED = False
_AVAILABLE = False
_MODEL = None
_MODEL_PATH: Optional[str] = None

_CARD_CHECKED = False
_CARD_AVAILABLE = False
_CARD_MODEL = None
_CARD_MODEL_PATH: Optional[str] = None


def is_available() -> bool:
    """True only if `ultralytics` is importable AND a KTP model file is found."""
    global _CHECKED, _AVAILABLE, _MODEL_PATH
    if _CHECKED:
        return _AVAILABLE
    _CHECKED = True
    path = _resolve_model_path()
    if not path:
        _AVAILABLE = False
        return False
    try:
        import ultralytics  # noqa: F401
        _MODEL_PATH = path
        _AVAILABLE = True
    except ImportError:
        _AVAILABLE = False
    return _AVAILABLE


def is_card_available() -> bool:
    """True if the optional card-cropper model (ktp_card.pt) is installed.

    Two-stage flow when this is True: detect the KTP outline in the full
    scene, crop, then run field detection on the crop — significantly
    more robust when the photo includes background clutter.
    """
    global _CARD_CHECKED, _CARD_AVAILABLE, _CARD_MODEL_PATH
    if _CARD_CHECKED:
        return _CARD_AVAILABLE
    _CARD_CHECKED = True
    path = _resolve_card_model_path()
    if not path:
        _CARD_AVAILABLE = False
        return False
    try:
        import ultralytics  # noqa: F401
        _CARD_MODEL_PATH = path
        _CARD_AVAILABLE = True
    except ImportError:
        _CARD_AVAILABLE = False
    return _CARD_AVAILABLE


def _load_model():
    """Lazy-load the YOLO model. Called only after is_available() has
    confirmed both `ultralytics` and the .pt file exist."""
    global _MODEL
    if _MODEL is None:
        from ultralytics import YOLO
        _MODEL = YOLO(_MODEL_PATH)
    return _MODEL


def _load_card_model():
    """Lazy-load the card detector. Called only after is_card_available()."""
    global _CARD_MODEL
    if _CARD_MODEL is None:
        from ultralytics import YOLO
        _CARD_MODEL = YOLO(_CARD_MODEL_PATH)
    return _CARD_MODEL


# ---------------------------------------------------------------------------
# Class label → field key mapping
# ---------------------------------------------------------------------------

# Maps raw YOLO class labels (lowercased, snake-cased) to our canonical
# field keys. Order: more specific first; whichever matches first wins.
CLASS_ALIASES: Dict[str, str] = {
    # Header (province / kabupaten) — not auto-filled but kept for inspection
    "prov_kab": "prov_kab",
    "provinsi": "prov_kab",
    "kabupaten": "prov_kab",
    "kota_kabupaten": "prov_kab",
    # Whole-card outline (used by some datasets to crop the KTP itself)
    "ktp": "ktp",
    "card": "ktp",

    # Core identity
    "nik": "nik",
    "nama": "nama",
    "name": "nama",
    "full_name": "nama",

    # Date / place of birth — KTP may use a single combined field or two separate fields
    "tempat_tgl_lahir": "tempat_tgl_lahir",
    "tempat_tanggal_lahir": "tempat_tgl_lahir",
    "ttl": "tempat_tgl_lahir",
    "tempat_lahir": "tempat_lahir",
    "tanggal_lahir": "tanggal_lahir",
    "date_of_birth": "tanggal_lahir",
    "dob": "tanggal_lahir",

    "jenis_kelamin": "jenis_kelamin",
    "gender": "jenis_kelamin",

    "gol_darah": "gol_darah",
    "golongan_darah": "gol_darah",
    "blood_type": "gol_darah",

    "alamat": "alamat",
    "address": "alamat",

    "rt_rw": "rt_rw",
    "rtrw": "rt_rw",

    "kel_desa": "kelurahan",
    "kelurahan_desa": "kelurahan",
    "kelurahan": "kelurahan",
    "desa": "kelurahan",

    "kecamatan": "kecamatan",

    "agama": "agama",
    "religion": "agama",

    "status_perkawinan": "status_perkawinan",
    "status_kawin": "status_perkawinan",
    "status": "status_perkawinan",

    "pekerjaan": "pekerjaan",
    "occupation": "pekerjaan",

    "kewarganegaraan": "kewarganegaraan",
    "nationality": "kewarganegaraan",

    "berlaku_hingga": "berlaku_hingga",
    "masa_berlaku": "berlaku_hingga",

    # Visual elements (not OCR'd, but kept for inspection)
    "foto": "foto",
    "photo": "foto",
    "ttd": "ttd",
    "signature": "ttd",
}


def normalize_class(raw_label: str) -> str:
    """YOLO labels can be 'JenisKelamin' / 'jenis-kelamin' / 'JENIS_KELAMIN'.
    Normalize to lower snake-case before alias lookup."""
    return (
        raw_label.strip()
        .lower()
        .replace("-", "_")
        .replace(" ", "_")
        .replace(".", "_")
    )


def map_class_to_field(raw_label: str) -> str:
    """Map a YOLO class label to a canonical KTP field key.
    Returns '' for unknown labels."""
    return CLASS_ALIASES.get(normalize_class(raw_label), "")


# ---------------------------------------------------------------------------
# Detection — returns a list of (field_key, bbox_xyxy, confidence, raw_class)
# ---------------------------------------------------------------------------

# (field_key, [x1, y1, x2, y2], confidence in [0,1], raw_class_label)
Detection = Tuple[str, List[int], float, str]


def _predict_boxes(model, img_np, conf_threshold: float):
    """Run a YOLO detect model and return [(cls_id, conf, [x1,y1,x2,y2]), ...]
    along with the model's class-id → name mapping."""
    results = model.predict(img_np, conf=conf_threshold, verbose=False)
    if not results:
        return [], {}
    result = results[0]
    names = getattr(result, "names", {}) or {}
    out = []
    for box in getattr(result, "boxes", []) or []:
        try:
            cls_id = int(box.cls[0].item())
            conf = float(box.conf[0].item())
            xyxy = box.xyxy[0].tolist()
        except (AttributeError, IndexError, TypeError):
            continue
        if conf < conf_threshold:
            continue
        out.append((cls_id, conf, [int(round(v)) for v in xyxy]))
    return out, names


def detect_card_bbox(img_np, conf_threshold: float = 0.25) -> Optional[Tuple[List[int], float]]:
    """Run the card detector and return the highest-confidence KTP-card
    bbox (xyxy in original-image coords) + its confidence, or None if no
    card was found or the model isn't installed."""
    if not is_card_available():
        return None
    model = _load_card_model()
    boxes, _ = _predict_boxes(model, img_np, conf_threshold)
    if not boxes:
        return None
    # The card detector is single-class; pick the most confident box.
    _, best_conf, best_bbox = max(boxes, key=lambda b: b[1])
    return best_bbox, best_conf


def detect_fields(img_np, conf_threshold: float = 0.25) -> List[Detection]:
    """Run the YOLO field detector on `img_np` and return per-field detections.

    Two-stage when `ktp_card.pt` is installed: first locate the KTP card
    in the wider photo, crop to it (with a small pad so glyph edges
    aren't shaved off), then run the field detector on the crop. Field
    bboxes are translated back to original-image coordinates so callers
    don't need to know which path ran.

    Returns [] if the field model isn't available."""
    if not is_available():
        return []

    # Stage 1 (optional): find the card. Pad the bbox slightly so the
    # field detector sees a bit of breathing room at the card edges.
    crop_origin = (0, 0)
    work_img = img_np
    card = detect_card_bbox(img_np, conf_threshold=0.25)
    if card is not None:
        h, w = img_np.shape[:2]
        cx1, cy1, cx2, cy2 = card[0]
        pad = max(4, int(0.02 * max(w, h)))
        cx1 = max(0, cx1 - pad)
        cy1 = max(0, cy1 - pad)
        cx2 = min(w, cx2 + pad)
        cy2 = min(h, cy2 + pad)
        if cx2 > cx1 and cy2 > cy1:
            work_img = img_np[cy1:cy2, cx1:cx2]
            crop_origin = (cx1, cy1)

    # Stage 2: field detector on the crop (or the full image if no card).
    model = _load_model()
    boxes, names = _predict_boxes(model, work_img, conf_threshold)

    detections: List[Detection] = []
    ox, oy = crop_origin
    for cls_id, conf, bbox in boxes:
        raw_label = names.get(cls_id, str(cls_id))
        field_key = map_class_to_field(raw_label)
        # Translate crop-local bbox → original-image coords
        bbox_global = [bbox[0] + ox, bbox[1] + oy, bbox[2] + ox, bbox[3] + oy]
        detections.append((field_key, bbox_global, conf, raw_label))

    return detections


# ---------------------------------------------------------------------------
# Crop helper — pads slightly so we don't cut OCR off at glyph edges
# ---------------------------------------------------------------------------

def crop_region(img_np, bbox: List[int], pad: int = 4):
    """Return a copy of `img_np` cropped to bbox (xyxy) with `pad` pixels of
    breathing room on each side, clamped to the image bounds."""
    h, w = img_np.shape[:2]
    x1 = max(0, bbox[0] - pad)
    y1 = max(0, bbox[1] - pad)
    x2 = min(w, bbox[2] + pad)
    y2 = min(h, bbox[3] + pad)
    if x2 <= x1 or y2 <= y1:
        return None
    return img_np[y1:y2, x1:x2].copy()
