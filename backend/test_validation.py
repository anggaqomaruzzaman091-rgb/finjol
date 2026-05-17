"""
Tests for the input-validation helpers in main.py:
  - validate_image_bytes (magic-byte check)
  - validate_username    (regex check)
  - validate_password    (length check)
"""

import pytest
from fastapi import HTTPException

import main


# ---------------------------------------------------------------------------
# Magic-byte image validation
# ---------------------------------------------------------------------------

class TestValidateImageBytes:
    def test_accepts_jpeg(self):
        main.validate_image_bytes(b"\xff\xd8\xff\xe0" + b"\x00" * 50)

    def test_accepts_png(self):
        main.validate_image_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 50)

    def test_accepts_gif87(self):
        main.validate_image_bytes(b"GIF87a" + b"\x00" * 50)

    def test_accepts_gif89(self):
        main.validate_image_bytes(b"GIF89a" + b"\x00" * 50)

    def test_accepts_webp_riff(self):
        main.validate_image_bytes(b"RIFF" + b"\x00\x00\x00\x00" + b"WEBP" + b"\x00" * 50)

    def test_accepts_bmp(self):
        main.validate_image_bytes(b"BM" + b"\x00" * 50)

    def test_rejects_arbitrary_bytes(self):
        with pytest.raises(HTTPException) as exc:
            main.validate_image_bytes(b"dummy_bytes_no_magic_here")
        assert exc.value.status_code == 400

    def test_rejects_empty(self):
        with pytest.raises(HTTPException):
            main.validate_image_bytes(b"")

    def test_rejects_short_prefix(self):
        # Too short to contain any signature
        with pytest.raises(HTTPException):
            main.validate_image_bytes(b"\xff\xd8")


# ---------------------------------------------------------------------------
# Username validation
# ---------------------------------------------------------------------------

class TestValidateUsername:
    @pytest.mark.parametrize("name", [
        "user1",
        "abc",                       # minimum length
        "a" * 50,                    # maximum length
        "user_name",
        "user-name",
        "USER123_test-OK",
    ])
    def test_accepts_valid(self, name):
        main.validate_username(name)  # should not raise

    @pytest.mark.parametrize("name", [
        "ab",                        # too short
        "a" * 51,                    # too long
        "user name",                 # space not allowed
        "user@name",                 # @ not allowed
        "user.name",                 # dot not allowed
        "",
    ])
    def test_rejects_invalid(self, name):
        with pytest.raises(HTTPException) as exc:
            main.validate_username(name)
        assert exc.value.status_code == 422


# ---------------------------------------------------------------------------
# Password validation
# ---------------------------------------------------------------------------

class TestValidatePassword:
    def test_accepts_min_length(self):
        main.validate_password("a" * 8)

    def test_accepts_long(self):
        main.validate_password("a" * 200)

    def test_rejects_too_short(self):
        with pytest.raises(HTTPException) as exc:
            main.validate_password("a" * 7)
        assert exc.value.status_code == 422

    def test_rejects_empty(self):
        with pytest.raises(HTTPException):
            main.validate_password("")
