"""
KTP (Kartu Tanda Penduduk) OCR Service
Uses EasyOCR (PyTorch CRAFT + CRNN) with tuned preprocessing and a
label-aware parser tuned to the standard Indonesian KTP layout.

Performance notes
-----------------
* Reader is lazy-loaded once, shared across requests (avoid 2-4s warm-up).
* A single semaphore serializes PyTorch inference — running two
  EasyOCR.readtext() calls concurrently on CPU thrashes BLAS threads
  and is *slower* than running them sequentially.
* Preprocessing is intentionally light: EasyOCR's CRAFT detector
  prefers natural grayscale (not binarized) inputs. The previous
  pipeline (denoise + adaptive threshold) was the dominant cost.
* `torch.set_num_threads` is pinned to a sensible default to avoid the
  pathological default behavior of grabbing every logical core.

Precision scoring
-----------------
Each parsed field is returned with a `precision` value in [0, 1]
computed as:

    precision = label_match_quality * mean(token_confidence)

where `label_match_quality` is 1.0 for an exact label hit, 0.85 for a
fuzzy hit, and 0.70 for a regex/heuristic fallback. An aggregate
`precision_score` is the confidence-weighted mean across non-empty
fields, matching the "precissioning data" formula requested.
"""

import asyncio
import os
import re
import io
from typing import Any, List, Tuple, Dict, Optional

# ---------------------------------------------------------------------------
# Torch / EasyOCR — lazy-loaded once, shared across requests
# ---------------------------------------------------------------------------

_reader = None
# One inference at a time on CPU — concurrent PyTorch jobs thrash BLAS
_inference_lock = asyncio.Lock()


def _configure_torch_threads():
    """Pin torch thread count once. Defaults to half of logical cores,
    capped at 4 — empirically the sweet spot for EasyOCR on CPU."""
    try:
        import torch
        cpus = os.cpu_count() or 4
        target = max(1, min(4, cpus // 2))
        torch.set_num_threads(target)
        try:
            torch.set_num_interop_threads(1)
        except RuntimeError:
            # Already set — safe to ignore
            pass
    except Exception:
        pass


def get_reader():
    global _reader
    if _reader is None:
        _configure_torch_threads()

        # Monkeypatch for python-bidi < 0.6.0 compatibility with new easyocr
        import sys
        import bidi
        try:
            import bidi.algorithm
            bidi.get_display = bidi.algorithm.get_display  # type: ignore
            sys.modules['bidi'].get_display = bidi.algorithm.get_display  # type: ignore
        except Exception:
            pass

        import easyocr
        _reader = easyocr.Reader(
            ['id', 'en'],
            gpu=False,
            recog_network='standard',
            verbose=False,
        )
    return _reader


async def warmup_reader():
    """Call at FastAPI startup so the first /scan request isn't slow."""
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, get_reader)


# ---------------------------------------------------------------------------
# Image preprocessing — light pipeline; EasyOCR prefers natural grayscale
# ---------------------------------------------------------------------------

# OCR accuracy plateaus around 1100-1300px wide for a KTP photo.
# Going larger just inflates the PyTorch tensor with no precision gain.
TARGET_WIDTH = 1200
MAX_WIDTH = 1600

def detect_and_crop_ktp(img_np):
    import cv2
    import numpy as np

    # KTP physical aspect ratio: 8.56 cm x 5.398 cm ≈ 1.5857
    TARGET_RATIO = 8.56 / 5.398
    
    # Resize for faster and more reliable contour detection
    height, width = img_np.shape[:2]
    max_dim = 800
    scale = max_dim / max(height, width)
    if scale < 1:
        resized = cv2.resize(img_np, (int(width * scale), int(height * scale)))
    else:
        resized = img_np.copy()
        scale = 1.0

    gray = cv2.cvtColor(resized, cv2.COLOR_RGB2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    edged = cv2.Canny(blurred, 50, 150)
    
    # Dilation can help connect fragmented edges
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    edged = cv2.dilate(edged, kernel, iterations=1)

    # Find contours
    contours, _ = cv2.findContours(edged, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    contours = sorted(contours, key=cv2.contourArea, reverse=True)[:5]
    
    card_contour = None
    for c in contours:
        peri = cv2.arcLength(c, True)
        approx = cv2.approxPolyDP(c, 0.02 * peri, True)
        
        if len(approx) == 4:
            # Check aspect ratio
            x, y, w, h = cv2.boundingRect(approx)
            ratio = max(w, h) / min(w, h)
            # KTP ratio is ~1.58. Allow a wide range for perspective distortion
            if 1.3 < ratio < 1.8:
                # Check if it's large enough (e.g., > 10% of image area)
                if cv2.contourArea(approx) > (resized.shape[0] * resized.shape[1] * 0.1):
                    card_contour = approx
                    break

    if card_contour is not None:
        # Scale contour back to original image size
        card_contour = (card_contour / scale).astype(np.float32)
        
        pts = card_contour.reshape(4, 2)
        rect = np.zeros((4, 2), dtype="float32")
        
        s = pts.sum(axis=1)
        rect[0] = pts[np.argmin(s)]
        rect[2] = pts[np.argmax(s)]
        
        diff = np.diff(pts, axis=1)
        rect[1] = pts[np.argmin(diff)]
        rect[3] = pts[np.argmax(diff)]
        
        (tl, tr, br, bl) = rect
        
        # Compute dimensions of new image
        widthA = np.sqrt(((br[0] - bl[0]) ** 2) + ((br[1] - bl[1]) ** 2))
        widthB = np.sqrt(((tr[0] - tl[0]) ** 2) + ((tr[1] - tl[1]) ** 2))
        maxWidth = max(int(widthA), int(widthB))
        
        heightA = np.sqrt(((tr[0] - br[0]) ** 2) + ((tr[1] - br[1]) ** 2))
        heightB = np.sqrt(((tl[0] - bl[0]) ** 2) + ((tl[1] - bl[1]) ** 2))
        maxHeight = max(int(heightA), int(heightB))
        
        # Force the exact physical aspect ratio
        if maxHeight > maxWidth:
            maxWidth = int(maxHeight * TARGET_RATIO)
        else:
            maxHeight = int(maxWidth / TARGET_RATIO)
            
        dst = np.array([
            [0, 0],
            [maxWidth - 1, 0],
            [maxWidth - 1, maxHeight - 1],
            [0, maxHeight - 1]
        ], dtype="float32")
        
        M = cv2.getPerspectiveTransform(rect, dst)
        warped = cv2.warpPerspective(img_np, M, (maxWidth, maxHeight))
        
        # Ensure it's in landscape mode
        if warped.shape[0] > warped.shape[1]:
            warped = cv2.rotate(warped, cv2.ROTATE_90_CLOCKWISE)
            
        return warped
        
    return img_np


def preprocess_image(image_bytes: bytes):
    """Backward-compatible entry point. Returns the grayscale OCR variant
    so existing callers (and tests) keep working."""
    _, gray = preprocess_image_pair(image_bytes)
    return gray


def preprocess_image_pair(image_bytes: bytes):
    """Returns `(rgb_for_yolo, gray_for_ocr)`.

    The two pipelines use independent preprocessing because their needs
    diverge: YOLO was trained on natural RGB photos and is robust to
    small tilts on its own, while EasyOCR/Tesseract benefit a lot from
    grayscale + CLAHE + bilateral denoise + deskew.

    Both start from the detect-and-crop step so their pixel coordinates
    refer to the same physical card, but the OCR variant then applies
    its own deskew (which YOLO does *not* see, because rotating the
    image moves it away from YOLO's training distribution).
    """
    import numpy as np
    import cv2
    from PIL import Image

    img = Image.open(io.BytesIO(image_bytes)).convert('RGB')
    img_np = np.asarray(img)

    # 1. Detect physical ID card boundaries and crop (perspective transform).
    img_np = detect_and_crop_ktp(img_np)

    # 2. Resize so both pipelines see the same canvas (~1200 px wide).
    h, w = img_np.shape[:2]
    if w > MAX_WIDTH:
        scale = MAX_WIDTH / w
        img_np = cv2.resize(img_np, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    elif w < TARGET_WIDTH:
        scale = TARGET_WIDTH / w
        img_np = cv2.resize(img_np, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)

    # 3. Make the RGB copy contiguous and freeze it — YOLO needs a pristine
    #    natural image. NO CLAHE / bilateral / deskew here.
    rgb = np.ascontiguousarray(img_np)

    # 4. Grayscale + contrast + denoise + deskew, *only* for OCR engines.
    gray = cv2.cvtColor(img_np, cv2.COLOR_RGB2GRAY)
    clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8))
    gray = clahe.apply(gray)
    gray = cv2.bilateralFilter(gray, d=5, sigmaColor=35, sigmaSpace=35)

    _, bw = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    coords = np.column_stack(np.where(bw > 0))
    if len(coords) > 200:
        angle = cv2.minAreaRect(coords)[-1]
        if angle < -45:
            angle += 90
        if abs(angle) > 0.5:
            (ch, cw) = gray.shape
            M = cv2.getRotationMatrix2D((cw // 2, ch // 2), angle, 1.0)
            gray = cv2.warpAffine(
                gray, M, (cw, ch),
                flags=cv2.INTER_CUBIC,
                borderMode=cv2.BORDER_REPLICATE,
            )
            # YOLO's `rgb` intentionally stays unrotated.

    return rgb, gray


# ---------------------------------------------------------------------------
# Line grouper — sorts OCR results into logical text lines by Y position
# ---------------------------------------------------------------------------

def _mid_y(bbox):
    ys = [pt[1] for pt in bbox]
    return (min(ys) + max(ys)) / 2


def _mid_x(bbox):
    xs = [pt[0] for pt in bbox]
    return (min(xs) + max(xs)) / 2


def group_into_lines(ocr_results: list, y_tolerance: int = 18) -> List[List[Tuple[str, float]]]:
    """
    ocr_results: list of (bbox, text, confidence) from EasyOCR
    Returns: list of lines; each line is a list of (text, confidence) tuples
             sorted left-to-right.
    """
    if not ocr_results:
        return []

    sorted_results = sorted(ocr_results, key=lambda r: _mid_y(r[0]))

    lines: List[list] = []
    current_line = [sorted_results[0]]
    current_y = _mid_y(sorted_results[0][0])

    for item in sorted_results[1:]:
        y = _mid_y(item[0])
        if abs(y - current_y) <= y_tolerance:
            current_line.append(item)
        else:
            lines.append(sorted(current_line, key=lambda r: _mid_x(r[0])))
            current_line = [item]
            current_y = y

    if current_line:
        lines.append(sorted(current_line, key=lambda r: _mid_x(r[0])))

    # Strip bbox; keep (text, conf) per token
    return [[(text, float(conf)) for _, text, conf in line] for line in lines]


# ---------------------------------------------------------------------------
# KTP field label patterns
# ---------------------------------------------------------------------------

KTP_LABELS = [
    ('nik',               ['NIK', 'N1K', 'NIX', 'NlK']),
    ('nama',              ['NAMA']),
    ('tempat_tgl_lahir',  ['TEMPAT/TGL LAHIR', 'TEMPAT / TGL LAHIR',
                           'TEMPAT/TANGGAL LAHIR', 'TEMPATTGL LAHIR',
                           'TEMPAT TGL LAHIR']),
    ('jenis_kelamin',     ['JENIS KELAMIN', 'JENISKELAMIN']),
    ('gol_darah',         ['GOL. DARAH', 'GOL DARAH', 'GOLONGAN DARAH',
                           'GOL.DARAH', 'GOLO DARAH']),
    ('alamat',            ['ALAMAT']),
    ('rt_rw',             ['RT/RW', 'RT / RW', 'RTRW', 'RT/RW :']),
    ('kelurahan',         ['KEL/DESA', 'KEL / DESA', 'KELURAHAN',
                           'DESA/KELURAHAN', 'DESA / KELURAHAN']),
    ('kecamatan',         ['KECAMATAN']),
    ('agama',             ['AGAMA']),
    ('status_perkawinan', ['STATUS PERKAWINAN', 'STATUS PERKAWIN',
                           'STATUS PERNIKAHAN']),
    ('pekerjaan',         ['PEKERJAAN']),
    ('kewarganegaraan',   ['KEWARGANEGARAAN', 'KEWARGANE GARAAN']),
    ('berlaku_hingga',    ['BERLAKU HINGGA', 'MASA BERLAKU', 'BERLAKUHINGGA']),
]

AGAMA_VALUES = ['ISLAM', 'KRISTEN', 'KATOLIK', 'HINDU', 'BUDDHA',
                'BUDHA', 'KONGHUCU', 'KHONGHUCU']
STATUS_VALUES = ['BELUM KAWIN', 'KAWIN', 'CERAI HIDUP', 'CERAI MATI']
GOL_DARAH_VALUES = ['AB', 'A', 'B', 'O', '-']


# Quality of the label-text match — used in the precision formula.
LABEL_QUALITY_EXACT = 1.00
LABEL_QUALITY_FUZZY = 0.85
LABEL_QUALITY_HEURISTIC = 0.70


def clean_value(text: str) -> str:
    return re.sub(r'^[\s:;\-|]+', '', text).strip()


def _normalize(s: str) -> str:
    return s.upper().replace(' ', '')


def _label_match_quality(line_text: str, variants: List[str]) -> float:
    """Returns 1.0 if any variant matches exactly (case-insensitive,
    whitespace-insensitive), 0.85 if a substring match exists, else 0."""
    n_line = _normalize(line_text)
    best = 0.0
    for v in variants:
        nv = _normalize(v)
        if nv == n_line[:len(nv)]:
            return LABEL_QUALITY_EXACT
        if nv in n_line:
            best = max(best, LABEL_QUALITY_FUZZY)
    return best


def _match_label(line_text: str, variants: List[str]) -> bool:
    return _label_match_quality(line_text, variants) > 0


def extract_value_from_line(line_text: str, label_variants: List[str]) -> str:
    upper = line_text.upper()
    for v in label_variants:
        idx = upper.find(v.upper())
        if idx != -1:
            after = line_text[idx + len(v):]
            return clean_value(after)
    return clean_value(line_text)


# ---------------------------------------------------------------------------
# Field-specific parsers
# ---------------------------------------------------------------------------

# Ported from yt_ocr.ipynb's `word_to_number_converter`. OCR commonly
# confuses these glyph pairs on low-contrast KTP prints; applied only to
# the NIK candidate, never to free-form text.
NIK_DIGIT_CONFUSIONS = {
    'O': '0', 'o': '0', 'D': '0', 'Q': '0',
    'I': '1', 'l': '1', 'L': '1', '|': '1',
    'Z': '2', 'z': '2',
    'A': '4',
    'S': '5', 's': '5',
    'b': '6', 'G': '6',
    '?': '7', 'T': '7',
    'B': '8',
    'g': '9', 'q': '9',
}

_NIK_CHARSET = '0-9' + ''.join(re.escape(c) for c in NIK_DIGIT_CONFUSIONS)


def coerce_nik_digits(text: str) -> str:
    """Map digit-confusable letters to digits. Non-mapped chars pass through."""
    return ''.join(NIK_DIGIT_CONFUSIONS.get(c, c) for c in text)


def _pick_nik_window(digits: str) -> str:
    """Given a digit string with len >= 16, return the 16-digit slice
    whose KTP-encoded date (day, month) is valid. Falls back to the first
    16 digits if no window validates.

    KTP NIK layout: PPRRSSDDMMYYNNNN
        DD (pos 7-8)  = day; 01-31 for male, 41-71 for female
        MM (pos 9-10) = month 01-12
    Using both gives a strong filter without needing a full checksum.
    """
    if len(digits) < 16:
        return ''
    if len(digits) == 16:
        return digits
    best_fallback = digits[:16]
    for i in range(len(digits) - 15):
        window = digits[i:i + 16]
        try:
            day = int(window[6:8])
            month = int(window[8:10])
        except ValueError:
            continue
        if 1 <= month <= 12 and (1 <= day <= 31 or 41 <= day <= 71):
            return window
    return best_fallback


def parse_nik(full_text: str) -> str:
    # Strip whitespace so "3201 2345 6789 1234" reads as a contiguous run,
    # then use digit-boundary lookaround. `\b` doesn't work here because
    # adjacent label letters ("NIK3201…") are word chars and produce no
    # word boundary against the digits.
    compact = re.sub(r'\s+', '', full_text)
    m = re.search(r'(?<!\d)(\d{16})(?!\d)', compact)
    if m:
        return m.group(1)
    # Fallback: a 16-char run of digit-confusable glyphs near a "NIK" label.
    # We only apply the char-confusion map here (not to free text), so we
    # don't corrupt place names or addresses.
    m = re.search(
        r'NIK[:\-]?([' + _NIK_CHARSET + r']{16})',
        compact,
        re.IGNORECASE,
    )
    if m:
        candidate = coerce_nik_digits(m.group(1))
        if len(candidate) == 16 and candidate.isdigit():
            return candidate
    return ''


def parse_date(text: str) -> str:
    m = re.search(r'(\d{1,2}[-/\s]\d{1,2}[-/\s]\d{4})', text)
    if m:
        return re.sub(r'[\s]', '-', m.group(1))
    m = re.search(r'(\d{8})', text)
    if m:
        d = m.group(1)
        return f"{d[:2]}-{d[2:4]}-{d[4:]}"
    return ''


def parse_tempat_tgl_lahir(value: str):
    date = parse_date(value)
    tempat = re.split(r'\d{1,2}[-/\s]\d{1,2}[-/\s]\d{4}', value)[0]
    tempat = re.sub(r'[,;]', '', tempat).strip()
    return tempat, date


def parse_gol_darah(value: str) -> str:
    upper = value.upper().strip()
    for g in GOL_DARAH_VALUES:
        if upper == g or upper.startswith(g + ' '):
            return g
    m = re.search(r'\b(AB|A|B|O)\b', upper)
    return m.group(1) if m else value


def parse_rt_rw(value: str) -> str:
    m = re.search(r'(\d{1,3})[/\\](\d{1,3})', value)
    if m:
        return f"{m.group(1).zfill(3)}/{m.group(2).zfill(3)}"
    return value


def parse_agama(value: str) -> str:
    upper = value.upper()
    for a in AGAMA_VALUES:
        if a in upper:
            return a.title()
    return value.title()


def parse_status_perkawinan(value: str) -> str:
    upper = value.upper()
    for s in STATUS_VALUES:
        if s in upper:
            return s.title()
    return value.title()


def parse_jenis_kelamin(value: str, full_text: str) -> str:
    combined = (value + ' ' + full_text).upper()
    if 'PEREMPUAN' in combined:
        return 'Perempuan'
    if 'LAKI' in combined:
        return 'Laki-laki'
    return 'Laki-laki'


# ---------------------------------------------------------------------------
# Main KTP parser
# ---------------------------------------------------------------------------

EMPTY_FIELDS = lambda: {
    'nik': '', 'nama': '', 'tempat_lahir': '', 'tanggal_lahir': '',
    'jenis_kelamin': '', 'gol_darah': '', 'alamat': '', 'rt_rw': '',
    'kelurahan': '', 'kecamatan': '', 'agama': '', 'status_perkawinan': '',
    'pekerjaan': '', 'kewarganegaraan': '', 'berlaku_hingga': '',
}


def _mean_conf(tokens: List[Tuple[str, float]]) -> float:
    if not tokens:
        return 0.0
    return sum(c for _, c in tokens) / len(tokens)


def parse_ktp_fields(
    lines: List[List[Tuple[str, float]]],
    full_text: str,
) -> Tuple[Dict[str, str], Dict[str, float]]:
    """
    Parses field values and returns (fields, precision) where
    precision[field] in [0, 1] is the label-quality-weighted mean OCR
    confidence of the tokens that contributed to that field.
    """
    fields: Dict[str, str] = EMPTY_FIELDS()
    precision: Dict[str, float] = {k: 0.0 for k in fields}

    # Plain-text and (text, conf)-aware views of each line
    flat_lines: List[str] = [' '.join(t for t, _ in line) for line in lines]

    # NIK: regex over full text — high-confidence numeric extraction
    nik = parse_nik(full_text)
    if nik:
        fields['nik'] = nik
        # Find the line containing the NIK to source its confidence
        for line in lines:
            joined = ''.join(t for t, _ in line).replace(' ', '')
            if nik in joined:
                precision['nik'] = LABEL_QUALITY_HEURISTIC * _mean_conf(line)
                break
        if precision['nik'] == 0.0:
            precision['nik'] = LABEL_QUALITY_HEURISTIC * 0.85  # synthetic floor

    # Pre-scan: golongan darah often shares a line with jenis kelamin
    for line, flat in zip(lines, flat_lines):
        upper = flat.upper()
        if 'GOL' in upper and ('DARAH' in upper or 'DARAJ' in upper):
            for gv in ['AB', 'A', 'B', 'O', '-']:
                if re.search(rf'\b{gv}\b', upper):
                    fields['gol_darah'] = gv
                    precision['gol_darah'] = LABEL_QUALITY_FUZZY * _mean_conf(line)
                    break

    i = 0
    while i < len(flat_lines):
        flat = flat_lines[i]
        line = lines[i]

        for field_key, label_variants in KTP_LABELS:
            quality = _label_match_quality(flat, label_variants)
            if quality == 0:
                continue

            inline_value = extract_value_from_line(flat, label_variants)

            # Value on next line if inline is too short
            value_line = line
            if len(inline_value) < 2 and i + 1 < len(flat_lines):
                value = clean_value(flat_lines[i + 1])
                value_line = lines[i + 1]
                i += 1
            else:
                value = inline_value

            field_conf = quality * _mean_conf(value_line)

            if field_key == 'tempat_tgl_lahir':
                t, d = parse_tempat_tgl_lahir(value)
                if t:
                    fields['tempat_lahir'] = t
                    precision['tempat_lahir'] = field_conf
                if d:
                    fields['tanggal_lahir'] = d
                    precision['tanggal_lahir'] = field_conf

            elif field_key == 'jenis_kelamin':
                jk_part = re.split(r'GOL', value, flags=re.IGNORECASE)[0]
                fields['jenis_kelamin'] = parse_jenis_kelamin(jk_part, full_text)
                precision['jenis_kelamin'] = field_conf

            elif field_key == 'gol_darah':
                if not fields['gol_darah']:
                    fields['gol_darah'] = parse_gol_darah(value)
                    precision['gol_darah'] = field_conf

            elif field_key == 'rt_rw':
                fields['rt_rw'] = parse_rt_rw(value)
                precision['rt_rw'] = field_conf

            elif field_key == 'agama':
                fields['agama'] = parse_agama(value)
                precision['agama'] = field_conf

            elif field_key == 'status_perkawinan':
                fields['status_perkawinan'] = parse_status_perkawinan(value)
                precision['status_perkawinan'] = field_conf

            elif field_key == 'berlaku_hingga':
                v = value.upper()
                if 'SEUMUR' in v or 'HIDUP' in v:
                    fields['berlaku_hingga'] = 'SEUMUR HIDUP'
                else:
                    fields['berlaku_hingga'] = value
                precision['berlaku_hingga'] = field_conf

            elif field_key == 'nik':
                # parse_nik(full_text) already ran above; only overwrite if
                # this line gives us a clean 16-digit answer too — never
                # accept the raw "8 3512..." string the label heuristic
                # produces, since NIK is digits-only by definition.
                nik_clean = parse_nik(value)
                if not nik_clean:
                    digits = re.sub(r'\D', '', value)
                    if len(digits) >= 16:
                        nik_clean = _pick_nik_window(digits)
                if nik_clean and field_conf > precision['nik']:
                    fields['nik'] = nik_clean
                    precision['nik'] = field_conf

            elif field_key in fields:
                fields[field_key] = value
                precision[field_key] = field_conf

            break

        i += 1

    # Fallback: derive nama from raw text if label-based parsing missed it
    if not fields['nama']:
        for line, flat in zip(lines, flat_lines):
            words = flat.strip().split()
            if (2 <= len(words) <= 6 and
                    all(re.match(r'^[A-Z\s\'\-\.]+$', w) for w in words) and
                    not any(kw in flat.upper() for kw in
                            ['PROVINSI', 'KOTA', 'KABUPATEN', 'REPUBLIK',
                             'INDONESIA', 'KEPENDUDUKAN', 'IDENTITAS'])):
                fields['nama'] = flat.strip()
                precision['nama'] = LABEL_QUALITY_HEURISTIC * _mean_conf(line)
                break

    fields = {k: (v.strip() if v else '') for k, v in fields.items()}
    # Clamp precision to [0, 1]
    precision = {k: max(0.0, min(1.0, v)) for k, v in precision.items()}
    return fields, precision


# ---------------------------------------------------------------------------
# Dual-engine merge — pick the higher-precision value per field
# ---------------------------------------------------------------------------

EngineResult = Tuple[Dict[str, str], Dict[str, float], str]  # fields, precision, engine_name


def merge_field_results(results: List[EngineResult]) -> Tuple[
    Dict[str, str], Dict[str, float], Dict[str, str]
]:
    """For each KTP field, pick the (value, precision) coming from whichever
    engine has the highest precision. Returns (merged_fields, merged_precision,
    field_source) where field_source[k] is the name of the winning engine.

    A field with precision 0 (or empty value) loses to any engine with a
    populated, non-zero-precision answer.
    """
    if not results:
        return {}, {}, {}

    all_keys = set()
    for fields, _, _ in results:
        all_keys.update(fields.keys())

    merged_fields: Dict[str, str] = {}
    merged_precision: Dict[str, float] = {}
    field_source: Dict[str, str] = {}

    for k in all_keys:
        best_value = ""
        best_p = -1.0
        best_engine = ""
        for fields, precision, name in results:
            value = fields.get(k, "")
            p = precision.get(k, 0.0)
            # Empty value can't win over a non-empty value, regardless of precision
            if not value and best_value:
                continue
            if value and not best_value:
                best_value, best_p, best_engine = value, p, name
                continue
            if p > best_p:
                best_value, best_p, best_engine = value, p, name
        merged_fields[k] = best_value
        merged_precision[k] = max(0.0, best_p) if best_value else 0.0
        field_source[k] = best_engine if best_value else ""
    return merged_fields, merged_precision, field_source


def _run_engine_parse(
    engine_results: list,
) -> Tuple[Dict[str, str], Dict[str, float]]:
    """Common path: group OCR tuples into lines and parse KTP fields."""
    if not engine_results:
        empty = EMPTY_FIELDS()
        return empty, {k: 0.0 for k in empty}
    full_text = ' '.join(t for _, t, _ in engine_results).upper()
    lines = group_into_lines(engine_results, y_tolerance=18)
    return parse_ktp_fields(lines, full_text)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Region-level OCR — used when YOLO has detected per-field bounding boxes.
# Running OCR on a single short crop is dramatically more accurate than
# full-page OCR because there are no neighboring labels to confuse the
# parser and the model sees the field's text in isolation.
# ---------------------------------------------------------------------------

# Per-field char restrictions. Empty entries (or fields absent) get no
# restriction — useful for free-text fields like nama/alamat where any
# whitelist would do more harm than good.
_DIGITS = "0123456789"
_DATE_CHARS = _DIGITS + "-/. "
_RTRW_CHARS = _DIGITS + "/\\ "
_ALPHA_UP_LOWER = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
_TESS_WHITELIST: Dict[str, str] = {
    "nik": _DIGITS,
    "tanggal_lahir": _DATE_CHARS,
    "rt_rw": _RTRW_CHARS,
    "jenis_kelamin": _ALPHA_UP_LOWER + "- ",
    "gol_darah": "ABO- ",
    "kewarganegaraan": _ALPHA_UP_LOWER + " ",
    "agama": _ALPHA_UP_LOWER + " ",
    "status_perkawinan": _ALPHA_UP_LOWER + " ",
    "berlaku_hingga": _ALPHA_UP_LOWER + _DIGITS + "-/ ",
}
# EasyOCR uses `allowlist` (a contiguous string, no spaces needed — its
# tokenizer handles whitespace separately).
_EASY_ALLOWLIST: Dict[str, str] = {
    "nik": _DIGITS,
    "tanggal_lahir": _DIGITS + "-/.",
    "rt_rw": _DIGITS + "/\\",
    "gol_darah": "ABO-",
}

# Tesseract Page Segmentation Modes:
#  7 = treat the image as a single text line
#  8 = single word
# Default 3 (auto) is intended for full pages and over-fragments crops.
_TESS_PSM_DEFAULT = 7


def _upscale_crop(crop_np, target_h: int = 64):
    """Upscale a crop so the shorter dimension reaches ~target_h pixels.
    Both EasyOCR and Tesseract perform notably better on 50-100 px text
    than on the 15-30 px crops YOLO emits at imgsz=640. Cubic preserves
    edges better than linear for upscales of small text.
    """
    import cv2
    if crop_np is None or crop_np.size == 0:
        return crop_np
    h, w = crop_np.shape[:2]
    if h <= 0 or w <= 0:
        return crop_np
    if h >= target_h:
        return crop_np
    scale = target_h / float(h)
    new_w = max(1, int(round(w * scale)))
    return cv2.resize(crop_np, (new_w, target_h), interpolation=cv2.INTER_CUBIC)


def _ocr_region_text(crop_np, tesseract_engine, field_key: str = '') -> Tuple[str, float]:
    """Run both OCR engines on a single cropped region and return
    (best_text, best_confidence). Confidence is the mean per-token
    confidence reported by whichever engine wins.

    Field-aware: when `field_key` is one of the restricted fields (NIK,
    dates, rt_rw, etc), both engines are given a char allow/whitelist so
    they can't hallucinate letters into a digit field and vice-versa.
    """
    crop_up = _upscale_crop(crop_np, target_h=64)
    reader = get_reader()
    easy_kwargs: Dict[str, Any] = {
        "detail": 1,
        "paragraph": False,
        "min_size": 8,
        "text_threshold": 0.55,
        "low_text": 0.3,
    }
    allowlist = _EASY_ALLOWLIST.get(field_key)
    if allowlist:
        easy_kwargs["allowlist"] = allowlist
    easy_out = reader.readtext(crop_up, **easy_kwargs)
    candidates: List[Tuple[str, float]] = []
    if easy_out:
        text = ' '.join(t for _, t, _ in easy_out).strip()
        conf = sum(c for _, _, c in easy_out) / len(easy_out)
        candidates.append((text, conf))

    if tesseract_engine.is_available():
        try:
            binarized = tesseract_engine.preprocess_region_for_tesseract(crop_up)
            tess_out = tesseract_engine.readtext(
                binarized,
                psm=_TESS_PSM_DEFAULT,
                whitelist=_TESS_WHITELIST.get(field_key),
            )
            if tess_out:
                text = ' '.join(t for _, t, _ in tess_out).strip()
                conf = sum(c for _, _, c in tess_out) / len(tess_out)
                candidates.append((text, conf))
        except Exception:
            pass

    if not candidates:
        return '', 0.0
    return max(candidates, key=lambda c: c[1])


# Field-specific post-processing for region OCR — apply the same parsers
# used in the full-page path so the output shape matches.
def _postprocess_region_value(field_key: str, raw_text: str) -> str:
    if field_key == 'nik':
        # Strict parser first (full text + label heuristics)
        parsed = parse_nik(raw_text)
        if parsed:
            return parsed
        # Region context: YOLO has already isolated the NIK box, so any
        # 16+ contiguous digits is the answer. Walk every 16-char window
        # and prefer the one whose embedded KTP structure validates:
        #   positions 7-8  = day  (01-31 male, 41-71 female)
        #   positions 9-10 = month (01-12)
        # This rescues "8 3512084102000002" → take last 16, not first 16,
        # because the first 16 yields month "20" (invalid).
        digits = re.sub(r'\D', '', raw_text)
        if len(digits) >= 16:
            return _pick_nik_window(digits)
        # Last resort: map confusable letters to digits, then retry.
        mapped = re.sub(r'\D', '', coerce_nik_digits(raw_text))
        return _pick_nik_window(mapped) if len(mapped) >= 16 else ''
    if field_key == 'tanggal_lahir':
        return parse_date(raw_text)
    if field_key == 'rt_rw':
        return parse_rt_rw(raw_text)
    if field_key == 'gol_darah':
        return parse_gol_darah(raw_text)
    if field_key == 'agama':
        return parse_agama(raw_text)
    if field_key == 'status_perkawinan':
        return parse_status_perkawinan(raw_text)
    if field_key == 'jenis_kelamin':
        return parse_jenis_kelamin(raw_text, raw_text)
    if field_key == 'tempat_tgl_lahir':
        # The caller splits this into tempat_lahir + tanggal_lahir
        return raw_text
    if field_key == 'kewarganegaraan':
        # YOLO has isolated the kewarganegaraan box: only WNI / WNA are legal
        # KTP values. OCR commonly garbles the leading 'W' ("nI", "Vni",
        # "wNi"), so trust the trailing letter (I = Indonesia, A = Asing)
        # rather than the prefix.
        letters = re.sub(r'[^A-Za-z]', '', raw_text).upper()
        if letters.endswith('I'):
            return 'WNI'
        if letters.endswith('A'):
            return 'WNA'
        return clean_value(raw_text) if letters else ''
    if field_key == 'berlaku_hingga':
        up = raw_text.upper()
        return 'SEUMUR HIDUP' if ('SEUMUR' in up or 'HIDUP' in up) else clean_value(raw_text)
    return clean_value(raw_text)


def _run_yolo_region_pipeline(img_np, yolo_engine, tesseract_engine) -> Tuple[
    Dict[str, str], Dict[str, float], Dict[str, List[int]], List[Dict[str, object]]
]:
    """Detect per-field bounding boxes with YOLO, crop each, and OCR the
    crop. Returns (fields, precision, field_bbox, detections)."""
    detections_raw = yolo_engine.detect_fields(img_np)

    fields = EMPTY_FIELDS()
    precision: Dict[str, float] = {k: 0.0 for k in fields}
    field_bbox: Dict[str, List[int]] = {}
    detections_out: List[Dict[str, object]] = []

    for field_key, bbox, det_conf, raw_class in detections_raw:
        detections_out.append({
            "class": raw_class,
            "field": field_key,
            "bbox": bbox,
            "confidence": round(det_conf, 4),
        })
        if not field_key:
            continue

        crop = yolo_engine.crop_region(img_np, bbox, pad=8)
        if crop is None or crop.size == 0:
            continue

        raw_text, ocr_conf = _ocr_region_text(crop, tesseract_engine, field_key)
        if not raw_text:
            continue

        # Combined detection confidence × OCR confidence — both must be
        # high for us to trust the field.
        combined = det_conf * ocr_conf

        if field_key == 'tempat_tgl_lahir':
            t, d = parse_tempat_tgl_lahir(raw_text)
            if t and combined > precision.get('tempat_lahir', 0.0):
                fields['tempat_lahir'] = t
                precision['tempat_lahir'] = combined
                field_bbox['tempat_lahir'] = bbox
            if d and combined > precision.get('tanggal_lahir', 0.0):
                fields['tanggal_lahir'] = d
                precision['tanggal_lahir'] = combined
                field_bbox['tanggal_lahir'] = bbox
            continue

        if field_key in ('prov_kab', 'foto', 'ttd'):
            # Inspected but not auto-filled — keep the bbox for the response
            field_bbox[field_key] = bbox
            continue

        value = _postprocess_region_value(field_key, raw_text)
        if not value:
            continue
        # If two detections claim the same field, the higher-combined-conf wins
        if combined <= precision.get(field_key, 0.0) and fields.get(field_key):
            continue

        # Re-map field_key 'nama' → also 'nama' (our internal key); the
        # response layer maps it to 'full_name'.
        target = 'nama' if field_key == 'nama' else field_key
        if target not in fields:
            continue
        fields[target] = value
        precision[target] = combined
        field_bbox[target] = bbox

    precision = {k: max(0.0, min(1.0, v)) for k, v in precision.items()}
    return fields, precision, field_bbox, detections_out


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

async def process_document_image(image_bytes: bytes, filename: str) -> dict:
    """Pipeline:
      1. Decode + crop the KTP card (preprocess_image).
      2. If a YOLO model is loaded, detect per-field bounding boxes and
         OCR each crop in isolation. Region-OCR is significantly more
         precise because there are no neighboring labels to confuse the
         parser.
      3. Always also run the full-page EasyOCR (+ Tesseract if installed)
         path as a safety net.
      4. Merge: per field, take the answer with the highest combined
         (detection × OCR) confidence. Empty values lose to populated.
    """
    import tesseract_engine
    import yolo_engine

    loop = asyncio.get_running_loop()

    def run_easyocr(img_np):
        reader = get_reader()
        return reader.readtext(
            img_np,
            detail=1,
            paragraph=False,
            min_size=10,
            text_threshold=0.6,
            low_text=0.3,
            link_threshold=0.4,
            width_ths=0.7,
            height_ths=0.7,
        )

    def run_tesseract(img_np):
        binarized = tesseract_engine.preprocess_for_tesseract(img_np)
        return tesseract_engine.readtext(binarized)

    # 1. Preprocess once: RGB for YOLO (it was trained on natural RGB),
    #    grayscale + CLAHE + bilateral for the full-page OCR engines.
    rgb_np, gray_np = await loop.run_in_executor(None, preprocess_image_pair, image_bytes)

    engines_used: List[str] = []
    engine_buckets: List[EngineResult] = []
    field_bbox: Dict[str, List[int]] = {}
    yolo_detections: List[Dict[str, object]] = []

    # 2. YOLO region-OCR path (most accurate when available)
    if yolo_engine.is_available():
        try:
            async with _inference_lock:
                yolo_fields, yolo_precision, field_bbox, yolo_detections = \
                    await loop.run_in_executor(
                        None,
                        _run_yolo_region_pipeline,
                        rgb_np, yolo_engine, tesseract_engine,
                    )
            engines_used.append("yolo+region_ocr")
            engine_buckets.append((yolo_fields, yolo_precision, "yolo+region_ocr"))
        except Exception:
            # YOLO failure must not break the request — fall through to full-page
            pass

    # 3. Full-page EasyOCR — always run as a safety net
    async with _inference_lock:
        easy_results = await loop.run_in_executor(None, run_easyocr, gray_np)
    easy_fields, easy_precision = _run_engine_parse(easy_results)
    engines_used.append("easyocr")
    engine_buckets.append((easy_fields, easy_precision, "easyocr"))

    # 4. Full-page Tesseract — optional
    if tesseract_engine.is_available():
        try:
            tess_results = await loop.run_in_executor(None, run_tesseract, gray_np)
            tess_fields, tess_precision = _run_engine_parse(tess_results)
            if any(tess_fields.values()):
                engines_used.append("tesseract")
                engine_buckets.append((tess_fields, tess_precision, "tesseract"))
        except Exception:
            pass

    # 5. Merge per field by highest precision across all engine buckets
    fields, precision, sources = merge_field_results(engine_buckets)

    # Aggregate precision score: weighted mean across populated fields
    populated = [p for k, p in precision.items() if fields.get(k) and p > 0]
    precision_score = (sum(populated) / len(populated)) if populated else 0.0

    return {
        "document_type": "KTP",
        "nik":                fields.get('nik', ''),
        "full_name":          fields.get('nama', ''),
        "tempat_lahir":       fields.get('tempat_lahir', ''),
        "date_of_birth":      fields.get('tanggal_lahir', ''),
        "jenis_kelamin":      fields.get('jenis_kelamin', ''),
        "gol_darah":          fields.get('gol_darah', ''),
        "alamat":             fields.get('alamat', ''),
        "rt_rw":              fields.get('rt_rw', ''),
        "kelurahan":          fields.get('kelurahan', ''),
        "kecamatan":          fields.get('kecamatan', ''),
        "agama":              fields.get('agama', ''),
        "status_perkawinan":  fields.get('status_perkawinan', ''),
        "pekerjaan":          fields.get('pekerjaan', ''),
        "kewarganegaraan":    fields.get('kewarganegaraan', ''),
        "berlaku_hingga":     fields.get('berlaku_hingga', ''),
        "precision_score":    round(precision_score, 4),
        "field_precision":    {k: round(v, 4) for k, v in precision.items()},
        "engines_used":       engines_used,
        "field_source":       sources,
        "field_bbox":         field_bbox,
        "yolo_detections":    yolo_detections,
    }
