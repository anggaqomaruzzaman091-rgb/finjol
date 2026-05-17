"""
Tests for the OCR-template port (NIK character-confusion fix) and the
dual-engine merge.

These tests intentionally avoid loading PyTorch / EasyOCR / Tesseract —
the merge function and the parser are pure Python, and the Tesseract
adapter is exercised via stubs.
"""

import asyncio
import pytest

import ocr_service as ocr
import tesseract_engine as tess


# ---------------------------------------------------------------------------
# coerce_nik_digits + parse_nik fallback (template port)
# ---------------------------------------------------------------------------

class TestCoerceNikDigits:
    def test_O_to_zero(self):
        assert ocr.coerce_nik_digits("32O1") == "3201"

    def test_L_to_one(self):
        assert ocr.coerce_nik_digits("L234") == "1234"

    def test_lowercase_l_to_one(self):
        assert ocr.coerce_nik_digits("l234") == "1234"

    def test_question_to_seven(self):
        assert ocr.coerce_nik_digits("?89") == "789"

    def test_S_to_five(self):
        assert ocr.coerce_nik_digits("S0") == "50"

    def test_passes_through_real_digits(self):
        assert ocr.coerce_nik_digits("3201234567891234") == "3201234567891234"

    def test_unknown_chars_unchanged(self):
        # `#` is not in the map → preserved
        assert ocr.coerce_nik_digits("3#2") == "3#2"


class TestParseNikFallback:
    def test_fast_path_clean_digits(self):
        """A clean 16-digit run still uses the fast path."""
        assert ocr.parse_nik("NIK 3201234567891234") == "3201234567891234"

    def test_fallback_with_O_confusion(self):
        """OCR returns O where 0 was — fallback maps it back."""
        # 'O' instead of '0' in two positions
        text = "NIK:32O1234S6789I234"   # O→0, S→5, I→1
        # Compact length of the candidate: 16 chars
        assert ocr.parse_nik(text) == "3201234567891234"

    def test_fallback_requires_nik_label_anchor(self):
        """Random letter-digit soup without NIK label is *not* corrected."""
        # No NIK anchor → don't treat 'SOMETHING' as a confused NIK
        assert ocr.parse_nik("BUKAN 32O1234S6789I234 IDENTITAS") == ""

    def test_fallback_case_insensitive_label(self):
        # `nik:` lowercase still works
        assert ocr.parse_nik("nik:32O1234S6789I234") == "3201234567891234"


# ---------------------------------------------------------------------------
# merge_field_results — picks the higher-precision answer per field
# ---------------------------------------------------------------------------

class TestMergeFieldResults:
    def test_empty_input(self):
        merged, prec, src = ocr.merge_field_results([])
        assert merged == {}
        assert prec == {}
        assert src == {}

    def test_single_engine_passthrough(self):
        f = {"nik": "3201234567891234", "nama": "BUDI"}
        p = {"nik": 0.9, "nama": 0.8}
        merged, prec, src = ocr.merge_field_results([(f, p, "easyocr")])
        assert merged == f
        assert prec == p
        assert src == {"nik": "easyocr", "nama": "easyocr"}

    def test_higher_precision_wins_per_field(self):
        easy = ({"nik": "AAA", "nama": "BUDI"}, {"nik": 0.6, "nama": 0.9}, "easyocr")
        tess = ({"nik": "BBB", "nama": "BUDY"}, {"nik": 0.95, "nama": 0.4}, "tesseract")
        merged, prec, src = ocr.merge_field_results([easy, tess])

        # NIK: tesseract wins (0.95 > 0.6)
        assert merged["nik"] == "BBB"
        assert prec["nik"] == 0.95
        assert src["nik"] == "tesseract"

        # NAMA: easyocr wins (0.9 > 0.4)
        assert merged["nama"] == "BUDI"
        assert prec["nama"] == 0.9
        assert src["nama"] == "easyocr"

    def test_non_empty_value_always_beats_empty(self):
        # Even with lower precision, a populated value should beat an empty one
        easy = ({"nik": ""},    {"nik": 0.0}, "easyocr")
        tess = ({"nik": "X"},   {"nik": 0.1}, "tesseract")
        merged, _, src = ocr.merge_field_results([easy, tess])
        assert merged["nik"] == "X"
        assert src["nik"] == "tesseract"

    def test_all_empty_yields_empty(self):
        easy = ({"nik": ""}, {"nik": 0.0}, "easyocr")
        tess = ({"nik": ""}, {"nik": 0.0}, "tesseract")
        merged, prec, src = ocr.merge_field_results([easy, tess])
        assert merged["nik"] == ""
        assert prec["nik"] == 0.0
        assert src["nik"] == ""


# ---------------------------------------------------------------------------
# Tesseract availability check — must not crash when tesseract.exe missing
# ---------------------------------------------------------------------------

class TestTesseractAvailability:
    def test_is_available_is_boolean(self):
        # Whether or not Tesseract is installed, this must return a bool
        # and never raise.
        assert isinstance(tess.is_available(), bool)

    def test_readtext_returns_empty_when_unavailable(self, monkeypatch):
        # Force the unavailable path: pretend tesseract.exe isn't found
        monkeypatch.setattr(tess, "_CHECKED", True)
        monkeypatch.setattr(tess, "_AVAILABLE", False)
        # Any input — should yield empty list without raising
        assert tess.readtext(b"unused") == []


# ---------------------------------------------------------------------------
# process_document_image — dual-engine path with both engines mocked
# ---------------------------------------------------------------------------

class _FakeReader:
    def __init__(self, results):
        self._r = results

    def readtext(self, _img, **_kwargs):
        return self._r


def test_process_document_image_merges_engines(monkeypatch):
    """When both engines return data, merge picks higher precision per field
    and reports `engines_used == ['easyocr', 'tesseract']`."""

    easy_results = [
        ([[0, 0], [200, 0], [200, 20], [0, 20]], "NIK", 0.95),
        ([[210, 0], [600, 0], [600, 20], [210, 20]], "3201234567891234", 0.60),  # low conf
        ([[0, 60], [120, 60], [120, 80], [0, 80]], "NAMA", 0.94),
        ([[130, 60], [380, 60], [380, 80], [130, 80]], "BUDI SANTOSO", 0.95),    # high conf
    ]
    tess_results = [
        ([[0, 0], [200, 0], [200, 20], [0, 20]], "NIK", 0.98),
        ([[210, 0], [600, 0], [600, 20], [210, 20]], "3201234567891234", 0.92), # higher conf
        ([[0, 60], [120, 60], [120, 80], [0, 80]], "NAMA", 0.70),
        ([[130, 60], [380, 60], [380, 80], [130, 80]], "BUDI SANTOSO", 0.55),   # lower conf
    ]

    # Stub EasyOCR reader
    monkeypatch.setattr(ocr, "get_reader", lambda: _FakeReader(easy_results))
    # Bypass cv2/PIL preprocessing
    monkeypatch.setattr(ocr, "preprocess_image_pair", lambda _bytes: (b"", b""))

    # Stub Tesseract engine
    import tesseract_engine as te
    monkeypatch.setattr(te, "is_available", lambda: True)
    monkeypatch.setattr(te, "preprocess_for_tesseract", lambda x: x)
    monkeypatch.setattr(te, "readtext", lambda _img: tess_results)

    result = asyncio.run(ocr.process_document_image(b"fake", "x.png"))

    assert result["nik"] == "3201234567891234"
    assert result["full_name"] == "BUDI SANTOSO"
    assert result["engines_used"] == ["easyocr", "tesseract"]

    # NIK: tesseract had the higher token confidence — should be the source
    assert result["field_source"]["nik"] == "tesseract"
    # NAMA: easyocr had the higher token confidence — should be the source
    assert result["field_source"]["nama"] == "easyocr"


def test_process_document_image_degrades_when_tesseract_missing(monkeypatch):
    """If Tesseract isn't installed, the response still works and uses
    EasyOCR only."""

    easy_results = [
        ([[0, 0], [200, 0], [200, 20], [0, 20]], "NIK", 0.95),
        ([[210, 0], [600, 0], [600, 20], [210, 20]], "3201234567891234", 0.92),
    ]
    monkeypatch.setattr(ocr, "get_reader", lambda: _FakeReader(easy_results))
    monkeypatch.setattr(ocr, "preprocess_image_pair", lambda _bytes: (b"", b""))

    import tesseract_engine as te
    monkeypatch.setattr(te, "is_available", lambda: False)

    result = asyncio.run(ocr.process_document_image(b"fake", "x.png"))

    assert result["nik"] == "3201234567891234"
    assert result["engines_used"] == ["easyocr"]
    assert result["field_source"]["nik"] == "easyocr"
