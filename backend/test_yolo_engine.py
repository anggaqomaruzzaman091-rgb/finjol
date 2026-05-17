"""
Tests for the YOLO engine module and its integration with the region-OCR
pipeline in ocr_service.process_document_image.

The real YOLO model is never loaded — we stub `detect_fields` and
`crop_region` so the tests stay fast (<1s) and don't require the
ultralytics binary or a trained .pt file.
"""

import asyncio
import os
import pytest

import yolo_engine
import ocr_service as ocr


# ---------------------------------------------------------------------------
# Class normalization & alias mapping
# ---------------------------------------------------------------------------

class TestNormalizeClass:
    def test_lowercases(self):
        assert yolo_engine.normalize_class("NIK") == "nik"

    def test_replaces_dash(self):
        assert yolo_engine.normalize_class("jenis-kelamin") == "jenis_kelamin"

    def test_replaces_space(self):
        assert yolo_engine.normalize_class("Jenis Kelamin") == "jenis_kelamin"

    def test_replaces_dot(self):
        assert yolo_engine.normalize_class("gol.darah") == "gol_darah"

    def test_strips_whitespace(self):
        assert yolo_engine.normalize_class("  alamat  ") == "alamat"


class TestMapClassToField:
    @pytest.mark.parametrize("raw, expected", [
        ("nik",              "nik"),
        ("nama",             "nama"),
        ("name",             "nama"),
        ("full_name",        "nama"),
        ("ttl",              "tempat_tgl_lahir"),
        ("tempat_tgl_lahir", "tempat_tgl_lahir"),
        ("tempat_lahir",     "tempat_lahir"),
        ("dob",              "tanggal_lahir"),
        ("gender",           "jenis_kelamin"),
        ("rtrw",             "rt_rw"),
        ("kel_desa",         "kelurahan"),
        ("religion",         "agama"),
        ("status_kawin",     "status_perkawinan"),
        ("occupation",       "pekerjaan"),
        ("nationality",      "kewarganegaraan"),
        ("masa_berlaku",     "berlaku_hingga"),
        ("foto",             "foto"),
        ("ttd",              "ttd"),
        ("prov_kab",         "prov_kab"),
        # Exact label names from the Roboflow `deteksi-ktp-indonesia` v9 dataset
        ("kota_kabupaten",       "prov_kab"),
        ("kelurahan_desa",       "kelurahan"),
        ("golongan_darah",       "gol_darah"),
        ("tempat_tanggal_lahir", "tempat_tgl_lahir"),
        ("ktp",                  "ktp"),
    ])
    def test_known_aliases(self, raw, expected):
        assert yolo_engine.map_class_to_field(raw) == expected

    def test_unknown_class_returns_empty(self):
        assert yolo_engine.map_class_to_field("xyz_unknown") == ""

    def test_case_insensitive(self):
        assert yolo_engine.map_class_to_field("NIK") == "nik"
        assert yolo_engine.map_class_to_field("Nama") == "nama"


# ---------------------------------------------------------------------------
# Availability check — must never raise when model file is absent
# ---------------------------------------------------------------------------

class TestAvailability:
    def test_resolve_model_path_missing_returns_none(self, monkeypatch, tmp_path):
        # Point default path at a non-existent file, clear env var
        monkeypatch.setattr(yolo_engine, "_DEFAULT_MODEL_PATH",
                            str(tmp_path / "nope.pt"))
        monkeypatch.delenv("KTP_YOLO_MODEL", raising=False)
        assert yolo_engine._resolve_model_path() is None

    def test_resolve_model_path_picks_env_var_when_set(self, monkeypatch, tmp_path):
        fake = tmp_path / "weights.pt"
        fake.write_bytes(b"")
        monkeypatch.setenv("KTP_YOLO_MODEL", str(fake))
        assert yolo_engine._resolve_model_path() == str(fake)

    def test_is_available_false_when_no_model(self, monkeypatch):
        # Reset cache so the check actually runs
        monkeypatch.setattr(yolo_engine, "_CHECKED", False)
        monkeypatch.setattr(yolo_engine, "_AVAILABLE", False)
        monkeypatch.setattr(yolo_engine, "_resolve_model_path", lambda: None)
        assert yolo_engine.is_available() is False

    def test_detect_fields_returns_empty_when_unavailable(self, monkeypatch):
        monkeypatch.setattr(yolo_engine, "is_available", lambda: False)
        assert yolo_engine.detect_fields(b"unused") == []


# ---------------------------------------------------------------------------
# crop_region — clamps to image bounds and pads
# ---------------------------------------------------------------------------

class TestCropRegion:
    def test_pads_and_clamps(self):
        import numpy as np
        img = np.zeros((100, 200, 3), dtype=np.uint8)
        # bbox near the corner — padding should clamp at 0
        out = yolo_engine.crop_region(img, [0, 0, 50, 50], pad=10)
        assert out is not None
        # padded x1/y1 clamped to 0; x2/y2 → 60
        assert out.shape == (60, 60, 3)

    def test_zero_area_returns_none_when_no_padding(self):
        # With pad=0, a zero-area bbox stays zero-area → None.
        # (Default pad=4 deliberately expands tiny bboxes, which is desirable.)
        import numpy as np
        img = np.zeros((100, 100, 3), dtype=np.uint8)
        out = yolo_engine.crop_region(img, [50, 50, 50, 50], pad=0)
        assert out is None

    def test_inverted_bbox_returns_none(self):
        # x2 < x1 must always reject, regardless of padding
        import numpy as np
        img = np.zeros((100, 100, 3), dtype=np.uint8)
        out = yolo_engine.crop_region(img, [80, 80, 20, 20], pad=0)
        assert out is None


# ---------------------------------------------------------------------------
# Region-OCR pipeline — both engines stubbed
# ---------------------------------------------------------------------------

class _FakeReader:
    """Returns canned text for any crop — `text` is interpolated by the
    test based on the crop's id() so different regions return different
    text."""

    def __init__(self, text_for_crop):
        self._text_for_crop = text_for_crop

    def readtext(self, crop, **_kwargs):
        text = self._text_for_crop(crop)
        if not text:
            return []
        bbox = [[0, 0], [100, 0], [100, 20], [0, 20]]
        return [(bbox, text, 0.92)]


def test_run_yolo_region_pipeline_populates_fields(monkeypatch):
    """When YOLO detects regions, each crop's OCR result lands in the
    right field key with detection×OCR combined precision."""
    import numpy as np

    # Build a fake image
    img = np.zeros((400, 800, 3), dtype=np.uint8)

    # Stub YOLO detections — three fields with distinct bboxes
    detections = [
        # (field_key, bbox xyxy, det_conf, raw_class)
        ("nik",   [40,  10, 360,  40],  0.95, "nik"),
        ("nama",  [40,  60, 400,  90],  0.92, "nama"),
        ("agama", [40, 110, 200, 140],  0.88, "agama"),
    ]
    monkeypatch.setattr(yolo_engine, "detect_fields", lambda _img: detections)
    # crop_region is fine to leave real — but let's stub it to return a
    # tiny non-zero ndarray keyed by bbox so the fake reader can switch
    # text per region
    def fake_crop(_img, bbox, pad=4):
        marker = np.full((10, 10, 3), bbox[0], dtype=np.uint8)
        return marker
    monkeypatch.setattr(yolo_engine, "crop_region", fake_crop)

    def fake_text(crop):
        # crop[0][0][0] uniquely identifies the region (we set it to bbox[0])
        marker = int(crop[0][0][0])
        return {
            40:  "3201234567891234",   # NIK
        }.get(marker) or {
            40: "3201234567891234",
        }.get(marker, "")
    # Need to switch by all three markers — use a richer map
    text_map = {
        40:  "3201234567891234",        # first bbox starts at x=40, but so do the others. Distinguish by y.
    }

    # Switch to keying on (x1,y1) by using bbox[1] (y1) as the marker too.
    def fake_crop2(_img, bbox, pad=4):
        # encode (x1, y1) into a 2-pixel marker
        marker = np.zeros((10, 10, 3), dtype=np.uint8)
        marker[0, 0, 0] = bbox[0]
        marker[0, 0, 1] = bbox[1]
        return marker
    monkeypatch.setattr(yolo_engine, "crop_region", fake_crop2)

    def fake_text2(crop):
        x1 = int(crop[0][0][0])
        y1 = int(crop[0][0][1])
        return {
            (40, 10):  "3201234567891234",   # NIK
            (40, 60):  "BUDI SANTOSO",       # NAMA
            (40, 110): "ISLAM",              # AGAMA
        }.get((x1, y1), "")

    monkeypatch.setattr(ocr, "get_reader", lambda: _FakeReader(fake_text2))

    # Tesseract not used in this test — stub unavailable
    import tesseract_engine as te
    monkeypatch.setattr(te, "is_available", lambda: False)

    fields, precision, bboxes, raw = ocr._run_yolo_region_pipeline(
        img, yolo_engine, te,
    )

    # Values
    assert fields["nik"] == "3201234567891234"
    assert fields["nama"] == "BUDI SANTOSO"
    assert fields["agama"] == "Islam"

    # bboxes are tracked per field
    assert bboxes["nik"] == [40, 10, 360, 40]
    assert bboxes["nama"] == [40, 60, 400, 90]
    assert bboxes["agama"] == [40, 110, 200, 140]

    # Combined precision = det_conf * ocr_conf  (~0.95 * 0.92 = 0.874)
    assert 0.8 < precision["nik"] < 0.9
    assert 0.8 < precision["nama"] < 0.9
    assert 0.75 < precision["agama"] < 0.85

    # Raw detections list preserved with class metadata
    assert len(raw) == 3
    assert raw[0]["field"] == "nik"
    assert raw[0]["bbox"] == [40, 10, 360, 40]


# ---------------------------------------------------------------------------
# End-to-end: process_document_image uses YOLO path when available
# ---------------------------------------------------------------------------

class _FakeReaderConst:
    def __init__(self, results):
        self._r = results

    def readtext(self, _img, **_kwargs):
        return self._r


def test_process_document_image_includes_yolo_engine_when_available(monkeypatch):
    """When YOLO is available, the response should include
    engines_used containing 'yolo+region_ocr' and a populated
    field_bbox map."""
    import numpy as np

    monkeypatch.setattr(
        ocr, "preprocess_image_pair",
        lambda _b: (np.zeros((400, 800, 3), dtype=np.uint8),
                    np.zeros((400, 800),    dtype=np.uint8)),
    )

    # Make YOLO "available" and return one nik detection
    monkeypatch.setattr(yolo_engine, "is_available", lambda: True)
    monkeypatch.setattr(yolo_engine, "detect_fields",
                        lambda _img: [("nik", [10, 10, 200, 40], 0.95, "nik")])
    monkeypatch.setattr(yolo_engine, "crop_region",
                        lambda _img, _bbox, pad=4: np.zeros((10, 10, 3), dtype=np.uint8))

    # EasyOCR's per-crop call returns the NIK text
    monkeypatch.setattr(ocr, "get_reader",
                        lambda: _FakeReaderConst([
                            ([[0, 0], [200, 0], [200, 20], [0, 20]],
                             "3201234567891234", 0.92),
                        ]))

    # Full-page Tesseract not available
    import tesseract_engine as te
    monkeypatch.setattr(te, "is_available", lambda: False)

    result = asyncio.run(ocr.process_document_image(b"fake", "x.png"))

    assert result["nik"] == "3201234567891234"
    assert "yolo+region_ocr" in result["engines_used"]
    assert "easyocr" in result["engines_used"]  # safety-net always runs
    assert result["field_bbox"].get("nik") == [10, 10, 200, 40]
    # One YOLO detection recorded
    assert len(result["yolo_detections"]) == 1
    assert result["yolo_detections"][0]["field"] == "nik"


def test_process_document_image_degrades_without_yolo(monkeypatch):
    """When YOLO is unavailable, engines_used must NOT include yolo and
    the pipeline still returns a valid response."""
    import numpy as np

    monkeypatch.setattr(
        ocr, "preprocess_image_pair",
        lambda _b: (np.zeros((400, 800, 3), dtype=np.uint8),
                    np.zeros((400, 800),    dtype=np.uint8)),
    )
    monkeypatch.setattr(yolo_engine, "is_available", lambda: False)

    monkeypatch.setattr(ocr, "get_reader",
                        lambda: _FakeReaderConst([
                            ([[0, 0], [200, 0], [200, 20], [0, 20]],
                             "NIK", 0.95),
                            ([[210, 0], [600, 0], [600, 20], [210, 20]],
                             "3201234567891234", 0.93),
                        ]))
    import tesseract_engine as te
    monkeypatch.setattr(te, "is_available", lambda: False)

    result = asyncio.run(ocr.process_document_image(b"fake", "x.png"))

    assert result["nik"] == "3201234567891234"
    assert "yolo+region_ocr" not in result["engines_used"]
    assert result["engines_used"] == ["easyocr"]
    # field_bbox absent because YOLO didn't run
    assert result["field_bbox"] == {}
    assert result["yolo_detections"] == []
