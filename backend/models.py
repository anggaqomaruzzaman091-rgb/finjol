from datetime import datetime


def user_document(username: str, hashed_password: str) -> dict:
    return {
        "username": username,
        "hashed_password": hashed_password,
        "is_active": True,
    }


def identity_record_document(user_id: str, req) -> dict:
    """Build a MongoDB document from a VerifyRequest schema."""
    return {
        "user_id": user_id,
        "document_type": req.document_type,
        # Encrypted PII — set by caller after encryption
        "encrypted_nik":            "",
        "encrypted_full_name":      "",
        "encrypted_date_of_birth":  "",
        # Plaintext non-sensitive fields
        "tempat_lahir":       req.tempat_lahir or "",
        "jenis_kelamin":      req.jenis_kelamin or "",
        "gol_darah":          req.gol_darah or "",
        "alamat":             req.alamat or "",
        "rt_rw":              req.rt_rw or "",
        "kelurahan":          req.kelurahan or "",
        "kecamatan":          req.kecamatan or "",
        "agama":              req.agama or "",
        "status_perkawinan":  req.status_perkawinan or "",
        "pekerjaan":          req.pekerjaan or "",
        "kewarganegaraan":    req.kewarganegaraan or "",
        "berlaku_hingga":     req.berlaku_hingga or "",
        "created_at":         datetime.utcnow(),
    }
