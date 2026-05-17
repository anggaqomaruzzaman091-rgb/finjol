"""
Tesseract KTP engine — ported from the `yt_ocr.ipynb` template.

The notebook uses `pytesseract` with `lang="ind"` against a THRESH_TRUNC
preprocessed image. Here we reuse the same idea but expose the output in
the same `(bbox, text, confidence)` shape as EasyOCR, so the rest of the
ocr_service pipeline (line grouping + field parsing) is engine-agnostic.

Offline notes
-------------
Tesseract is fully offline once the binary and the Indonesian language
data are installed locally. On Windows the recommended path is the
UB Mannheim build:

    1. https://github.com/UB-Mannheim/tesseract/wiki  → install the
       latest tesseract-ocr-w64-setup-X.X.X.exe
    2. During setup, tick "Indonesian" in the additional language data
       (or drop `ind.traineddata` into `C:/Program Files/Tesseract-OCR/tessdata/`).

If Tesseract isn't found at runtime, `is_available()` returns False and
the dual-engine merge in ocr_service silently falls back to EasyOCR only.
"""

from __future__ import annotations

import os
import shutil
from typing import List, Tuple, Optional


# ---------------------------------------------------------------------------
# Tesseract binary discovery — done once, cached
# ---------------------------------------------------------------------------

_CHECKED = False
_AVAILABLE = False
_TESSERACT_PATH: Optional[str] = None


# Common Windows install paths — checked in order if `tesseract` isn't on PATH.
_WIN_DEFAULTS = (
    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
    r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
)


def _find_tesseract() -> Optional[str]:
    found = shutil.which("tesseract")
    if found:
        return found
    for path in _WIN_DEFAULTS:
        if os.path.exists(path):
            return path
    return None


def is_available() -> bool:
    """True if both `tesseract.exe` and `pytesseract` are importable."""
    global _CHECKED, _AVAILABLE, _TESSERACT_PATH
    if _CHECKED:
        return _AVAILABLE

    _CHECKED = True
    path = _find_tesseract()
    if not path:
        _AVAILABLE = False
        return False
    try:
        import pytesseract  # noqa: F401
        pytesseract.pytesseract.tesseract_cmd = path
        _TESSERACT_PATH = path
        _AVAILABLE = True
    except ImportError:
        _AVAILABLE = False
    return _AVAILABLE


# ---------------------------------------------------------------------------
# Image preprocessing — matches the notebook's THRESH_TRUNC pipeline
# ---------------------------------------------------------------------------

def preprocess_for_tesseract(img_np):
    """Notebook's recipe: grayscale + THRESH_TRUNC. Cheap and gives Tesseract
    the high-contrast input it prefers for KTP photos."""
    import cv2
    if img_np.ndim == 3:
        gray = cv2.cvtColor(img_np, cv2.COLOR_RGB2GRAY)
    else:
        gray = img_np
    _, threshed = cv2.threshold(gray, 127, 255, cv2.THRESH_TRUNC)
    return threshed


def preprocess_region_for_tesseract(img_np):
    """Region-OCR preprocessing for a small YOLO crop. THRESH_TRUNC tends to
    leave grey halos that confuse PSM 7; Otsu picks a per-crop threshold that
    works better on isolated text lines.

    Why: a region crop has uniform-ish background and one short text line —
    different statistics than a full KTP card, where TRUNC's clamping wins.
    """
    import cv2
    if img_np.ndim == 3:
        gray = cv2.cvtColor(img_np, cv2.COLOR_RGB2GRAY)
    else:
        gray = img_np
    # Otsu + binary; add a light blur to smooth JPEG noise without eating glyph thickness.
    blur = cv2.GaussianBlur(gray, (3, 3), 0)
    _, threshed = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return threshed


# ---------------------------------------------------------------------------
# OCR adapter — returns EasyOCR-compatible (bbox, text, conf) tuples
# ---------------------------------------------------------------------------

def readtext(img_np, *, psm: int = 3, whitelist: Optional[str] = None) -> List[Tuple[List[List[int]], str, float]]:
    """Run Tesseract on `img_np` and return EasyOCR-shaped results.

    Tesseract's `image_to_data` gives per-word bbox + confidence (0-100);
    we normalize confidence to [0, 1] and drop tokens with conf < 0
    (Tesseract's sentinel for "no text") or whitespace-only strings.

    Optional knobs for region-OCR callers:
      psm        — Page Segmentation Mode (3=auto/default, 7=single line,
                   8=single word). Use 7 for YOLO field crops.
      whitelist  — Restrict recognized chars (e.g. "0123456789" for NIK).
    """
    if not is_available():
        return []

    import pytesseract
    from pytesseract import Output

    config_parts = [f"--psm {psm}"]
    if whitelist:
        # Escape spaces in whitelist values; Tesseract takes the literal string.
        config_parts.append(f"-c tessedit_char_whitelist={whitelist}")
    config = " ".join(config_parts)

    data = pytesseract.image_to_data(
        img_np,
        lang="ind",
        config=config,
        output_type=Output.DICT,
    )

    results: List[Tuple[List[List[int]], str, float]] = []
    n = len(data.get("text", []))
    for i in range(n):
        text = (data["text"][i] or "").strip()
        if not text:
            continue
        try:
            conf = float(data["conf"][i])
        except (TypeError, ValueError):
            continue
        if conf < 0:
            continue  # Tesseract sentinel — no text in this region

        x = int(data["left"][i])
        y = int(data["top"][i])
        w = int(data["width"][i])
        h = int(data["height"][i])
        bbox = [[x, y], [x + w, y], [x + w, y + h], [x, y + h]]
        results.append((bbox, text, conf / 100.0))
    return results
