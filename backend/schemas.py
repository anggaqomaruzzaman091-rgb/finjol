from pydantic import BaseModel
from typing import Optional
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
