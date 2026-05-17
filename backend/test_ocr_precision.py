"""
Tests for the precision-scoring (precissioning-data) formula:

    precision = label_match_quality * mean(token_confidence)

and the aggregate `precision_score` that process_document_image surfaces.
"""

import asyncio
import ocr_service as ocr


def _line(*tokens):
    """Helper: build a logical line as a list of (text, confidence) tuples."""
    return list(tokens)


# ---------------------------------------------------------------------------
# parse_ktp_fields returns (fields, precision) — every key in [0, 1]
# ---------------------------------------------------------------------------

class TestParseKtpFieldsPrecisionShape:
    def test_returns_two_dicts(self):
        fields, precision = ocr.parse_ktp_fields([], "")
        assert isinstance(fields, dict)
        assert isinstance(precision, dict)

    def test_all_field_keys_have_precision(self):
        fields, precision = ocr.parse_ktp_fields([], "")
        # Every populated field key must also have a precision entry
        for k in fields:
            assert k in precision, f"missing precision for {k}"

    def test_precision_values_in_unit_interval(self):
        lines = [
            _line(("NIK", 0.95), ("3201234567891234", 0.92)),
            _line(("NAMA", 0.93), ("BUDI SANTOSO", 0.88)),
            _line(("AGAMA", 0.91), ("ISLAM", 0.90)),
        ]
        full_text = "NIK 3201234567891234 NAMA BUDI SANTOSO AGAMA ISLAM"
        _, precision = ocr.parse_ktp_fields(lines, full_text)
        for k, v in precision.items():
            assert 0.0 <= v <= 1.0, f"{k} precision {v} not in [0,1]"


# ---------------------------------------------------------------------------
# parse_ktp_fields — actual parsing behaviour
# ---------------------------------------------------------------------------

class TestParseKtpFieldsExtraction:
    def test_extracts_nik_from_full_text(self):
        lines = [_line(("NIK", 0.95), ("3201234567891234", 0.90))]
        fields, precision = ocr.parse_ktp_fields(lines, "NIK 3201234567891234")
        assert fields["nik"] == "3201234567891234"
        assert precision["nik"] > 0

    def test_higher_token_conf_yields_higher_precision(self):
        # Same label, different OCR confidence — higher conf → higher precision
        hi = ocr.parse_ktp_fields(
            [_line(("AGAMA", 0.99), ("ISLAM", 0.99))],
            "AGAMA ISLAM",
        )[1]["agama"]
        lo = ocr.parse_ktp_fields(
            [_line(("AGAMA", 0.50), ("ISLAM", 0.50))],
            "AGAMA ISLAM",
        )[1]["agama"]
        assert hi > lo

    def test_extracts_inline_value_after_label(self):
        # "NAMA BUDI" on one line — value comes after the label
        lines = [_line(("NAMA", 0.95), ("BUDI", 0.90))]
        fields, _ = ocr.parse_ktp_fields(lines, "NAMA BUDI")
        assert fields["nama"] == "BUDI"

    def test_extracts_value_from_next_line_when_inline_short(self):
        # Label-only line, value on next line
        lines = [
            _line(("AGAMA", 0.95)),
            _line(("ISLAM", 0.92)),
        ]
        fields, _ = ocr.parse_ktp_fields(lines, "AGAMA ISLAM")
        assert fields["agama"] == "Islam"

    def test_nama_fallback_from_heuristic(self):
        # No NAMA label, but a line of ALL-CAPS words should be picked up
        lines = [
            _line(("BUDI", 0.93), ("SANTOSO", 0.93)),
        ]
        fields, precision = ocr.parse_ktp_fields(
            lines, "BUDI SANTOSO"
        )
        assert fields["nama"] == "BUDI SANTOSO"
        # Heuristic source → precision uses LABEL_QUALITY_HEURISTIC (0.70)
        assert precision["nama"] > 0
        assert precision["nama"] <= ocr.LABEL_QUALITY_HEURISTIC * 0.93 + 1e-9


# ---------------------------------------------------------------------------
# process_document_image — full pipeline with mocked OCR + preprocessing
# ---------------------------------------------------------------------------

class _FakeReader:
    """A stand-in for easyocr.Reader that returns canned output."""

    def __init__(self, results):
        self._results = results

    def readtext(self, _img, **_kwargs):
        return self._results


def test_process_document_image_returns_precision_score(monkeypatch):
    """End-to-end (mocked OCR) — the response carries precision_score
    and field_precision dictionaries."""

    fake_results = [
        # bbox, text, confidence
        ([[0, 0], [200, 0], [200, 20], [0, 20]],     "NIK",  0.95),
        ([[210, 0], [600, 0], [600, 20], [210, 20]], "3201234567891234", 0.92),
        ([[0, 60], [120, 60], [120, 80], [0, 80]],   "NAMA", 0.94),
        ([[130, 60], [380, 60], [380, 80], [130, 80]], "BUDI SANTOSO", 0.90),
        ([[0, 120], [140, 120], [140, 140], [0, 140]], "AGAMA", 0.93),
        ([[150, 120], [260, 120], [260, 140], [150, 140]], "ISLAM", 0.91),
    ]

    monkeypatch.setattr(ocr, "get_reader", lambda: _FakeReader(fake_results))
    # Bypass actual image decoding/CV preprocessing
    monkeypatch.setattr(ocr, "preprocess_image_pair", lambda _bytes: (b"", b""))

    result = asyncio.run(ocr.process_document_image(b"fake", "x.png"))

    # Shape
    assert result["document_type"] == "KTP"
    assert result["nik"] == "3201234567891234"
    assert result["full_name"] == "BUDI SANTOSO"
    assert result["agama"] == "Islam"

    # Precision data
    assert "precision_score" in result
    assert 0.0 <= result["precision_score"] <= 1.0
    assert "field_precision" in result
    assert result["field_precision"]["nik"] > 0
    assert result["field_precision"]["nama"] > 0
    assert result["field_precision"]["agama"] > 0

    # Aggregate score is roughly the mean of populated fields' confidences
    populated = [v for v in result["field_precision"].values() if v > 0]
    expected = sum(populated) / len(populated)
    assert abs(result["precision_score"] - expected) < 1e-3
