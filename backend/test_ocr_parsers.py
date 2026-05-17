"""
Unit tests for the pure-Python parsers in ocr_service.

These tests do *not* load PyTorch or EasyOCR — they exercise the parser
functions directly with synthetic OCR-style input.
"""

import ocr_service as ocr


# ---------------------------------------------------------------------------
# clean_value
# ---------------------------------------------------------------------------

class TestCleanValue:
    def test_strips_leading_colon(self):
        assert ocr.clean_value(": BUDI SANTOSO") == "BUDI SANTOSO"

    def test_strips_leading_dash(self):
        assert ocr.clean_value("- BUDI") == "BUDI"

    def test_strips_mixed_artifacts(self):
        assert ocr.clean_value(" :;-| value") == "value"

    def test_preserves_internal_punctuation(self):
        assert ocr.clean_value("JL. MERDEKA NO. 12") == "JL. MERDEKA NO. 12"

    def test_empty_input(self):
        assert ocr.clean_value("") == ""


# ---------------------------------------------------------------------------
# parse_nik — must find the 16-digit number anywhere in the text
# ---------------------------------------------------------------------------

class TestParseNik:
    def test_extracts_16_digit_run(self):
        assert ocr.parse_nik("NIK 3201234567891234 NAMA BUDI") == "3201234567891234"

    def test_ignores_shorter_numbers(self):
        # 15 digits should not match
        assert ocr.parse_nik("ID 123456789012345 X") == ""

    def test_extracts_when_spaces_inside(self):
        # The parser strips spaces before regex
        assert ocr.parse_nik("3201 2345 6789 1234") == "3201234567891234"

    def test_returns_empty_when_absent(self):
        assert ocr.parse_nik("no digits here at all") == ""


# ---------------------------------------------------------------------------
# parse_date
# ---------------------------------------------------------------------------

class TestParseDate:
    def test_dash_separated(self):
        assert ocr.parse_date("LAHIR 15-08-1995") == "15-08-1995"

    def test_slash_separated(self):
        assert ocr.parse_date("LAHIR 15/08/1995") == "15/08/1995"

    def test_8_digit_compact(self):
        assert ocr.parse_date("LAHIR 15081995 END") == "15-08-1995"

    def test_returns_empty_when_no_date(self):
        assert ocr.parse_date("no date here") == ""


# ---------------------------------------------------------------------------
# parse_tempat_tgl_lahir
# ---------------------------------------------------------------------------

class TestParseTempatTglLahir:
    def test_splits_city_and_date(self):
        tempat, date = ocr.parse_tempat_tgl_lahir("JAKARTA, 15-08-1995")
        assert tempat == "JAKARTA"
        assert date == "15-08-1995"

    def test_no_separator(self):
        tempat, date = ocr.parse_tempat_tgl_lahir("BANDUNG 01-01-2000")
        assert tempat == "BANDUNG"
        assert date == "01-01-2000"


# ---------------------------------------------------------------------------
# parse_gol_darah
# ---------------------------------------------------------------------------

class TestParseGolDarah:
    def test_exact_a(self):
        assert ocr.parse_gol_darah("A") == "A"

    def test_exact_ab(self):
        # AB must win over A — the parser checks AB first in GOL_DARAH_VALUES
        assert ocr.parse_gol_darah("AB") == "AB"

    def test_value_with_trailing_text(self):
        assert ocr.parse_gol_darah("B Positif") == "B"

    def test_dash_for_unknown(self):
        assert ocr.parse_gol_darah("-") == "-"


# ---------------------------------------------------------------------------
# parse_rt_rw
# ---------------------------------------------------------------------------

class TestParseRtRw:
    def test_zero_pads(self):
        assert ocr.parse_rt_rw("1/2") == "001/002"

    def test_three_digits_unchanged(self):
        assert ocr.parse_rt_rw("012/034") == "012/034"

    def test_backslash_accepted(self):
        assert ocr.parse_rt_rw("5\\6") == "005/006"

    def test_returns_input_when_no_match(self):
        assert ocr.parse_rt_rw("unknown") == "unknown"


# ---------------------------------------------------------------------------
# parse_agama, parse_status_perkawinan, parse_jenis_kelamin
# ---------------------------------------------------------------------------

class TestParseEnums:
    def test_agama_islam(self):
        assert ocr.parse_agama("ISLAM") == "Islam"

    def test_agama_buddha_alias(self):
        # BUDHA is in the value list — case-insensitive title-cased
        assert ocr.parse_agama("BUDHA") == "Budha"

    def test_status_kawin(self):
        assert ocr.parse_status_perkawinan("KAWIN") == "Kawin"

    def test_status_cerai_hidup(self):
        assert ocr.parse_status_perkawinan("CERAI HIDUP") == "Cerai Hidup"

    def test_jk_perempuan_takes_priority(self):
        # Even if "LAKI" appears somewhere, PEREMPUAN should win
        assert ocr.parse_jenis_kelamin("PEREMPUAN", "LAKI-LAKI PEREMPUAN") == "Perempuan"

    def test_jk_laki(self):
        assert ocr.parse_jenis_kelamin("LAKI-LAKI", "LAKI-LAKI") == "Laki-laki"


# ---------------------------------------------------------------------------
# _label_match_quality
# ---------------------------------------------------------------------------

class TestLabelMatchQuality:
    def test_exact_match(self):
        # Line *starts with* a label variant → exact (1.0)
        q = ocr._label_match_quality("NIK 3201234567891234", ["NIK"])
        assert q == ocr.LABEL_QUALITY_EXACT

    def test_fuzzy_match(self):
        # Label appears mid-line → fuzzy (0.85)
        q = ocr._label_match_quality("data: NIK 3201234567891234", ["NIK"])
        assert q == ocr.LABEL_QUALITY_FUZZY

    def test_no_match(self):
        assert ocr._label_match_quality("ALAMAT JL. MERDEKA", ["NIK"]) == 0.0

    def test_whitespace_insensitive(self):
        # Variant with a space should match a no-space version
        q = ocr._label_match_quality("TEMPATTGLLAHIR JAKARTA", ["TEMPAT/TGL LAHIR"])
        # No slash, but minus the whitespace+slash this is still substring-able? No, it's not.
        # The normalizer only strips spaces, not slashes. So this is a no-match.
        assert q == 0.0

    def test_whitespace_insensitive_label(self):
        q = ocr._label_match_quality("JENIS KELAMIN: LAKI", ["JENISKELAMIN"])
        assert q == ocr.LABEL_QUALITY_EXACT


# ---------------------------------------------------------------------------
# _mean_conf
# ---------------------------------------------------------------------------

class TestMeanConf:
    def test_empty_list(self):
        assert ocr._mean_conf([]) == 0.0

    def test_average(self):
        tokens = [("a", 0.8), ("b", 0.6), ("c", 1.0)]
        assert abs(ocr._mean_conf(tokens) - 0.8) < 1e-9

    def test_single_token(self):
        assert ocr._mean_conf([("x", 0.5)]) == 0.5


# ---------------------------------------------------------------------------
# group_into_lines — Y-tolerance grouping & left-to-right sort within line
# ---------------------------------------------------------------------------

def _bbox(x1, y1, x2, y2):
    """Helper: build a 4-point EasyOCR-style bbox."""
    return [[x1, y1], [x2, y1], [x2, y2], [x1, y2]]


class TestGroupIntoLines:
    def test_empty_returns_empty(self):
        assert ocr.group_into_lines([]) == []

    def test_groups_by_y(self):
        # Two tokens on the same row, one on a row far below
        results = [
            (_bbox(0,   0,  50,  20), "NIK",  0.95),
            (_bbox(60,  2, 200,  22), "3201", 0.90),
            (_bbox(0, 100,  80, 120), "NAMA", 0.92),
        ]
        lines = ocr.group_into_lines(results, y_tolerance=18)
        assert len(lines) == 2
        # First line: NIK then 3201 (left-to-right by X)
        assert [t for t, _ in lines[0]] == ["NIK", "3201"]
        assert [t for t, _ in lines[1]] == ["NAMA"]

    def test_within_tolerance_grouped(self):
        # Y differs by 10 < y_tolerance=18 → same line
        results = [
            (_bbox(0,  0, 50, 20), "A", 1.0),
            (_bbox(60, 10, 110, 30), "B", 1.0),
        ]
        lines = ocr.group_into_lines(results, y_tolerance=18)
        assert len(lines) == 1
        assert [t for t, _ in lines[0]] == ["A", "B"]

    def test_sorts_left_to_right(self):
        # Out of order by X — must come back sorted
        results = [
            (_bbox(200, 0, 250, 20), "RIGHT", 1.0),
            (_bbox(0,   2,  50, 22), "LEFT",  1.0),
        ]
        lines = ocr.group_into_lines(results, y_tolerance=18)
        assert [t for t, _ in lines[0]] == ["LEFT", "RIGHT"]

    def test_preserves_confidence(self):
        results = [
            (_bbox(0, 0, 50, 20), "NIK", 0.95),
        ]
        lines = ocr.group_into_lines(results)
        assert lines[0][0] == ("NIK", 0.95)
