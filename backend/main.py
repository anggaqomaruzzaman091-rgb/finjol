from fastapi import FastAPI, Depends, HTTPException, Request, status, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import OAuth2PasswordRequestForm
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from datetime import timedelta
from typing import List
from bson import ObjectId
from dotenv import load_dotenv
import re
import os

import models
import schemas
import database
import auth
import deps
import encryption
import ocr_service

load_dotenv()

ALLOWED_ORIGINS = [o.strip() for o in os.getenv("ALLOWED_ORIGINS", "http://localhost:5173").split(",")]

# ---------------------------------------------------------------------------
# Rate limiter
# ---------------------------------------------------------------------------
limiter = Limiter(key_func=get_remote_address)

app = FastAPI(
    title="FindJol KTP Identity API",
    docs_url=None,       # disable Swagger in prod
    redoc_url=None,
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# ---------------------------------------------------------------------------
# Security headers middleware
# ---------------------------------------------------------------------------
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=()"
    return response

# ---------------------------------------------------------------------------
# CORS — only specific origins from env
# ---------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type"],
)


@app.on_event("startup")
async def startup():
    await database.create_indexes()


# ---------------------------------------------------------------------------
# Input validation helpers
# ---------------------------------------------------------------------------
USERNAME_RE = re.compile(r'^[a-zA-Z0-9_\-]{3,50}$')
PASSWORD_MIN = 8

def validate_username(username: str):
    if not USERNAME_RE.match(username):
        raise HTTPException(
            status_code=422,
            detail="Username must be 3–50 characters, letters/digits/_ only.",
        )

def validate_password(password: str):
    if len(password) < PASSWORD_MIN:
        raise HTTPException(
            status_code=422,
            detail=f"Password must be at least {PASSWORD_MIN} characters.",
        )

# ---------------------------------------------------------------------------
# Magic-byte image validation (prevent MIME spoofing)
# ---------------------------------------------------------------------------
IMAGE_SIGNATURES = [
    b'\xff\xd8\xff',        # JPEG
    b'\x89PNG\r\n\x1a\n',  # PNG
    b'GIF87a', b'GIF89a',  # GIF
    b'RIFF',               # WebP (starts with RIFF....WEBP)
    b'BM',                 # BMP
]

def validate_image_bytes(data: bytes):
    for sig in IMAGE_SIGNATURES:
        if data[:len(sig)] == sig:
            return
    raise HTTPException(status_code=400, detail="File is not a valid image.")


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

@app.post("/api/v1/auth/token", response_model=schemas.Token)
@limiter.limit("10/minute")
async def login_for_access_token(request: Request, form_data: OAuth2PasswordRequestForm = Depends()):
    user = await database.users_collection.find_one({"username": form_data.username})
    if not user or not auth.verify_password(form_data.password, user["hashed_password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Username atau password salah",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token = auth.create_access_token(
        data={"sub": user["username"]},
        expires_delta=timedelta(minutes=auth.ACCESS_TOKEN_EXPIRE_MINUTES),
    )
    return {"access_token": access_token, "token_type": "bearer"}


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------

@app.post("/api/v1/users", response_model=schemas.UserInDB)
@limiter.limit("5/minute")
async def create_user(request: Request, user: schemas.UserCreate):
    validate_username(user.username)
    validate_password(user.password)

    existing = await database.users_collection.find_one({"username": user.username})
    if existing:
        raise HTTPException(status_code=400, detail="Username sudah terdaftar")

    hashed_password = auth.get_password_hash(user.password)
    doc = models.user_document(user.username, hashed_password)
    result = await database.users_collection.insert_one(doc)

    return schemas.UserInDB(
        id=str(result.inserted_id),
        username=user.username,
        hashed_password=hashed_password,
    )


# ---------------------------------------------------------------------------
# KTP Scan
# ---------------------------------------------------------------------------

@app.post("/api/v1/identity/scan", response_model=schemas.ScanResult)
@limiter.limit("20/minute")
async def scan_ktp(
    request: Request,
    file: UploadFile = File(...),
    current_user: dict = Depends(deps.get_current_user),
):
    contents = await file.read()

    # Size guard (5 MB)
    if len(contents) > 5 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Ukuran file terlalu besar (max 5 MB)")

    # Magic-byte validation — don't trust client MIME
    validate_image_bytes(contents)

    result = await ocr_service.process_document_image(contents, file.filename)
    return result


# ---------------------------------------------------------------------------
# Verify & Save
# ---------------------------------------------------------------------------

@app.post("/api/v1/identity/verify", response_model=schemas.IdentityRecordResponse)
@limiter.limit("10/minute")
async def verify_and_save_identity(
    request: Request,
    payload: schemas.VerifyRequest,
    current_user: dict = Depends(deps.get_current_user),
):
    # Validate NIK format
    if not re.match(r'^\d{16}$', payload.nik):
        raise HTTPException(status_code=422, detail="NIK harus tepat 16 digit angka")

    doc = models.identity_record_document(str(current_user["_id"]), payload)
    doc["encrypted_nik"]           = encryption.encrypt_pii(payload.nik)
    doc["encrypted_full_name"]     = encryption.encrypt_pii(payload.full_name)
    doc["encrypted_date_of_birth"] = encryption.encrypt_pii(payload.date_of_birth or "")

    result = await database.identity_records_collection.insert_one(doc)

    return schemas.IdentityRecordResponse(
        id=str(result.inserted_id),
        user_id=str(current_user["_id"]),
        document_type=payload.document_type,
        created_at=doc["created_at"],
        nik=payload.nik,
        full_name=payload.full_name,
        tempat_lahir=payload.tempat_lahir,
        date_of_birth=payload.date_of_birth,
        jenis_kelamin=payload.jenis_kelamin,
        gol_darah=payload.gol_darah,
        alamat=payload.alamat,
        rt_rw=payload.rt_rw,
        kelurahan=payload.kelurahan,
        kecamatan=payload.kecamatan,
        agama=payload.agama,
        status_perkawinan=payload.status_perkawinan,
        pekerjaan=payload.pekerjaan,
        kewarganegaraan=payload.kewarganegaraan,
        berlaku_hingga=payload.berlaku_hingga,
    )


# ---------------------------------------------------------------------------
# Get my saved identities
# ---------------------------------------------------------------------------

@app.get("/api/v1/identity/me", response_model=List[schemas.IdentityRecordResponse])
@limiter.limit("30/minute")
async def get_my_identities(
    request: Request,
    current_user: dict = Depends(deps.get_current_user),
):
    cursor = database.identity_records_collection.find(
        {"user_id": str(current_user["_id"])}
    )
    records = await cursor.to_list(length=100)

    return [
        schemas.IdentityRecordResponse(
            id=str(r["_id"]),
            user_id=r["user_id"],
            document_type=r["document_type"],
            created_at=r["created_at"],
            nik=encryption.decrypt_pii(r.get("encrypted_nik", "")),
            full_name=encryption.decrypt_pii(r.get("encrypted_full_name", "")),
            tempat_lahir=r.get("tempat_lahir", ""),
            date_of_birth=encryption.decrypt_pii(r.get("encrypted_date_of_birth", "")),
            jenis_kelamin=r.get("jenis_kelamin", ""),
            gol_darah=r.get("gol_darah", ""),
            alamat=r.get("alamat", ""),
            rt_rw=r.get("rt_rw", ""),
            kelurahan=r.get("kelurahan", ""),
            kecamatan=r.get("kecamatan", ""),
            agama=r.get("agama", ""),
            status_perkawinan=r.get("status_perkawinan", ""),
            pekerjaan=r.get("pekerjaan", ""),
            kewarganegaraan=r.get("kewarganegaraan", ""),
            berlaku_hingga=r.get("berlaku_hingga", ""),
        )
        for r in records
    ]
