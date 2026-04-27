"""
KTP (Kartu Tanda Penduduk) OCR Service
Uses EasyOCR (PyTorch CRAFT + CRNN) with enhanced preprocessing and
a label-aware parser tuned to the standard Indonesian KTP layout.
"""

import asyncio
import re
import io
from typing import List, Tuple, Dict, Optional

# ---------------------------------------------------------------------------
# EasyOCR reader — lazy-loaded once, shared across requests
# ---------------------------------------------------------------------------

_reader = None

def get_reader():
    global _reader
    if _reader is None:
        import easyocr
        _reader = easyocr.Reader(
            ['id', 'en'],
            gpu=False,
            # Larger recognition batch for better accuracy on dense document text
            recog_network='standard',
        )
    return _reader


# ---------------------------------------------------------------------------
# Image preprocessing — improves OCR accuracy on low-quality KTP scans
# ---------------------------------------------------------------------------

def preprocess_image(image_bytes: bytes):
    import numpy as np
    import cv2
    from PIL import Image

    img = Image.open(io.BytesIO(image_bytes)).convert('RGB')
    img_np = np.array(img)

    # 1. Convert to grayscale
    gray = cv2.cvtColor(img_np, cv2.COLOR_RGB2GRAY)

    # 2. Scale up small images (OCR accuracy improves above 1000px wide)
    h, w = gray.shape
    if w < 1000:
        scale = 1000 / w
        gray = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)

    # 3. CLAHE — adaptive contrast enhancement for uneven lighting
    clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8))
    gray = clahe.apply(gray)

    # 4. Gentle denoise
    gray = cv2.fastNlMeansDenoising(gray, h=10)

    # 5. Adaptive threshold — handles shadow / gradient backgrounds
    thresh = cv2.adaptiveThreshold(
        gray, 255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY, 31, 10
    )

    # 6. Deskew — correct slight rotation
    coords = np.column_stack(np.where(thresh < 128))
    if len(coords) > 100:
        angle = cv2.minAreaRect(coords)[-1]
        if angle < -45:
            angle += 90
        if abs(angle) > 0.5:
            (ch, cw) = thresh.shape
            M = cv2.getRotationMatrix2D((cw // 2, ch // 2), angle, 1.0)
            thresh = cv2.warpAffine(
                thresh, M, (cw, ch),
                flags=cv2.INTER_CUBIC,
                borderMode=cv2.BORDER_REPLICATE,
            )

    # Return as RGB (EasyOCR expects 3-channel or grayscale numpy array)
    return cv2.cvtColor(thresh, cv2.COLOR_GRAY2RGB)


# ---------------------------------------------------------------------------
# Line grouper — sorts OCR results into logical text lines by Y position
# ---------------------------------------------------------------------------

def group_into_lines(ocr_results: list, y_tolerance: int = 18) -> List[List[str]]:
    """
    ocr_results: list of (bbox, text, confidence) from EasyOCR
    Returns a list of lines, each line is a list of words sorted left→right.
    """
    if not ocr_results:
        return []

    # Sort top→bottom by the midpoint Y of each bbox
    def mid_y(bbox):
        ys = [pt[1] for pt in bbox]
        return (min(ys) + max(ys)) / 2

    def mid_x(bbox):
        xs = [pt[0] for pt in bbox]
        return (min(xs) + max(xs)) / 2

    sorted_results = sorted(ocr_results, key=lambda r: mid_y(r[0]))

    lines: List[List[Tuple]] = []
    current_line: List[Tuple] = [sorted_results[0]]
    current_y = mid_y(sorted_results[0][0])

    for item in sorted_results[1:]:
        y = mid_y(item[0])
        if abs(y - current_y) <= y_tolerance:
            current_line.append(item)
        else:
            lines.append(sorted(current_line, key=lambda r: mid_x(r[0])))
            current_line = [item]
            current_y = y

    if current_line:
        lines.append(sorted(current_line, key=lambda r: mid_x(r[0])))

    return [[text for _, text, _ in line] for line in lines]


# ---------------------------------------------------------------------------
# KTP field label patterns
# ---------------------------------------------------------------------------

# Each entry: (field_name, [label_variants…])
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

AGAMA_VALUES    = ['ISLAM', 'KRISTEN', 'KATOLIK', 'HINDU', 'BUDDHA',
                   'BUDHA', 'KONGHUCU', 'KHONGHUCU']
STATUS_VALUES   = ['BELUM KAWIN', 'KAWIN', 'CERAI HIDUP', 'CERAI MATI']
GOL_DARAH_VALUES = ['AB', 'A', 'B', 'O', '-']


def clean_value(text: str) -> str:
    """Remove leading colon/dash/space artifacts from OCR value text."""
    return re.sub(r'^[\s:;\-|]+', '', text).strip()


def _match_label(line_text: str, variants: List[str]) -> bool:
    line_upper = line_text.upper().replace(' ', '')
    for v in variants:
        if v.replace(' ', '') in line_upper:
            return True
    return False


def extract_value_from_line(line_text: str, label_variants: List[str]) -> str:
    """
    Given a line like 'Nama : BUDI SANTOSO', strip the label part and return the value.
    """
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

def parse_nik(full_text: str) -> str:
    m = re.search(r'\b(\d{16})\b', full_text.replace(' ', ''))
    return m.group(1) if m else ''


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
    """Returns (tempat_lahir, tanggal_lahir) tuple."""
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
# Main KTP parser — works line by line
# ---------------------------------------------------------------------------

def parse_ktp_fields(lines: List[List[str]], full_text: str) -> Dict[str, str]:
    fields: Dict[str, str] = {
        'nik': '', 'nama': '', 'tempat_lahir': '', 'tanggal_lahir': '',
        'jenis_kelamin': '', 'gol_darah': '', 'alamat': '', 'rt_rw': '',
        'kelurahan': '', 'kecamatan': '', 'agama': '', 'status_perkawinan': '',
        'pekerjaan': '', 'kewarganegaraan': '', 'berlaku_hingga': '',
    }

    # NIK: reliable 16-digit extraction from raw text
    fields['nik'] = parse_nik(full_text)

    flat_lines = [' '.join(words) for words in lines]

    # Golongan darah often appears inline on the Jenis Kelamin line
    # e.g. "LAKI-LAKI        GOL DARAH : A"
    for line in flat_lines:
        upper = line.upper()
        if 'GOL' in upper and ('DARAH' in upper or 'DARAJ' in upper):
            val = extract_value_from_line(line, ['GOL. DARAH', 'GOL DARAH',
                                                  'GOLONGAN DARAH', 'GOL.DARAH'])
            # If on the same line as jenis kelamin, split them
            for gv in ['AB', 'A', 'B', 'O', '-']:
                if re.search(rf'\b{gv}\b', upper):
                    fields['gol_darah'] = gv
                    break
            if not fields['gol_darah'] and val:
                fields['gol_darah'] = parse_gol_darah(val)

    i = 0
    while i < len(flat_lines):
        line = flat_lines[i]
        line_upper = line.upper()

        matched = False
        for field_key, label_variants in KTP_LABELS:
            if not _match_label(line, label_variants):
                continue
            matched = True

            # Value is either on same line (after the label) or the next line
            inline_value = extract_value_from_line(line, label_variants)

            # If inline value is too short, try next line
            if len(inline_value) < 2 and i + 1 < len(flat_lines):
                value = clean_value(flat_lines[i + 1])
                i += 1
            else:
                value = inline_value

            if field_key == 'tempat_tgl_lahir':
                t, d = parse_tempat_tgl_lahir(value)
                if t:
                    fields['tempat_lahir'] = t
                if d:
                    fields['tanggal_lahir'] = d

            elif field_key == 'jenis_kelamin':
                # Gol darah is often on same line — strip it before storing
                jk_part = re.split(r'GOL', value, flags=re.IGNORECASE)[0]
                fields['jenis_kelamin'] = parse_jenis_kelamin(jk_part, full_text)

            elif field_key == 'gol_darah':
                if not fields['gol_darah']:  # don't overwrite if already found
                    fields['gol_darah'] = parse_gol_darah(value)

            elif field_key == 'rt_rw':
                fields['rt_rw'] = parse_rt_rw(value)

            elif field_key == 'agama':
                fields['agama'] = parse_agama(value)

            elif field_key == 'status_perkawinan':
                fields['status_perkawinan'] = parse_status_perkawinan(value)

            elif field_key == 'berlaku_hingga':
                v = value.upper()
                if 'SEUMUR' in v or 'HIDUP' in v:
                    fields['berlaku_hingga'] = 'SEUMUR HIDUP'
                else:
                    fields['berlaku_hingga'] = value

            elif field_key in fields:
                fields[field_key] = value

            break  # found matching label for this line

        i += 1

    # Fallback: if nama still empty, try to find it from raw text heuristics
    if not fields['nama']:
        for line in flat_lines:
            # Name lines are typically ALL CAPS with no digits, 2–5 words
            words = line.strip().split()
            if (2 <= len(words) <= 6 and
                    all(re.match(r'^[A-Z\s\'\-\.]+$', w) for w in words) and
                    not any(kw in line.upper() for kw in
                            ['PROVINSI', 'KOTA', 'KABUPATEN', 'REPUBLIK',
                             'INDONESIA', 'KEPENDUDUKAN', 'IDENTITAS'])):
                fields['nama'] = line.strip()
                break

    # Clean up empty values
    return {k: (v.strip() if v else '') for k, v in fields.items()}


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

async def process_document_image(image_bytes: bytes, filename: str) -> dict:
    loop = asyncio.get_running_loop()

    def process_sync():
        reader = get_reader()
        img_np = preprocess_image(image_bytes)

        # EasyOCR parameters tuned for dense KTP text
        results = reader.readtext(
            img_np,
            detail=1,           # return bboxes + confidence
            paragraph=False,    # keep individual text blocks for better parsing
            min_size=10,        # ignore tiny artifacts
            text_threshold=0.6,
            low_text=0.3,
            link_threshold=0.4,
            width_ths=0.7,
            height_ths=0.7,
        )
        return results

    results = await loop.run_in_executor(None, process_sync)

    # Build full text for regex fallbacks
    full_text = ' '.join(t for _, t, _ in results).upper()

    # Group OCR output into document lines
    lines = group_into_lines(results, y_tolerance=18)

    # Parse all KTP fields
    fields = parse_ktp_fields(lines, full_text)

    return {
        "document_type": "KTP",
        "nik":                fields['nik'],
        "full_name":          fields['nama'],
        "tempat_lahir":       fields['tempat_lahir'],
        "date_of_birth":      fields['tanggal_lahir'],
        "jenis_kelamin":      fields['jenis_kelamin'],
        "gol_darah":          fields['gol_darah'],
        "alamat":             fields['alamat'],
        "rt_rw":              fields['rt_rw'],
        "kelurahan":          fields['kelurahan'],
        "kecamatan":          fields['kecamatan'],
        "agama":              fields['agama'],
        "status_perkawinan":  fields['status_perkawinan'],
        "pekerjaan":          fields['pekerjaan'],
        "kewarganegaraan":    fields['kewarganegaraan'],
        "berlaku_hingga":     fields['berlaku_hingga'],
    }
