from pydantic import BaseModel
from typing import Optional, Dict, List, Any
from datetime import datetime


class ScanResult(BaseModel):
    document_type: str
    nik: Optional[str] = None
    full_name: Optional[str] = None
    tempat_lahir: Optional[str] = None
    date_of_birth: Optional[str] = None
    jenis_kelamin: Optional[str] = None
    gol_darah: Optional[str] = None
    alamat: Optional[str] = None
    rt_rw: Optional[str] = None
    kelurahan: Optional[str] = None
    kecamatan: Optional[str] = None
    agama: Optional[str] = None
    status_perkawinan: Optional[str] = None
    pekerjaan: Optional[str] = None
    kewarganegaraan: Optional[str] = None
    berlaku_hingga: Optional[str] = None
    # Precision data: aggregate score + per-field confidence (both in [0,1])
    precision_score: Optional[float] = None
    field_precision: Optional[Dict[str, float]] = None
    # Which engine(s) contributed — diagnostic for dual-engine merge
    engines_used: Optional[List[str]] = None
    field_source: Optional[Dict[str, str]] = None
    # YOLO region detection: bbox per field (xyxy in cropped-image coords)
    field_bbox: Optional[Dict[str, List[int]]] = None
    # Raw YOLO detections for inspection / UI overlay
    yolo_detections: Optional[List[Dict[str, Any]]] = None


class VerifyRequest(BaseModel):
    document_type: str
    nik: str
    full_name: str
    tempat_lahir: Optional[str] = None
    date_of_birth: Optional[str] = None
    jenis_kelamin: Optional[str] = None
    gol_darah: Optional[str] = None
    alamat: Optional[str] = None
    rt_rw: Optional[str] = None
    kelurahan: Optional[str] = None
    kecamatan: Optional[str] = None
    agama: Optional[str] = None
    status_perkawinan: Optional[str] = None
    pekerjaan: Optional[str] = None
    kewarganegaraan: Optional[str] = None
    berlaku_hingga: Optional[str] = None


class IdentityRecordResponse(BaseModel):
    id: str
    user_id: str
    document_type: str
    created_at: datetime
    nik: Optional[str] = None
    full_name: Optional[str] = None
    tempat_lahir: Optional[str] = None
    date_of_birth: Optional[str] = None
    jenis_kelamin: Optional[str] = None
    gol_darah: Optional[str] = None
    alamat: Optional[str] = None
    rt_rw: Optional[str] = None
    kelurahan: Optional[str] = None
    kecamatan: Optional[str] = None
    agama: Optional[str] = None
    status_perkawinan: Optional[str] = None
    pekerjaan: Optional[str] = None
    kewarganegaraan: Optional[str] = None
    berlaku_hingga: Optional[str] = None


class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    username: Optional[str] = None


class User(BaseModel):
    username: str


class UserCreate(User):
    password: str


class UserInDB(BaseModel):
    id: str
    username: str
    hashed_password: str
