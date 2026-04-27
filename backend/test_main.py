import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine  # type: ignore
from sqlalchemy.orm import sessionmaker  # type: ignore
import uuid

import main
import database
import encryption
from models import Base

# Setup testing DB
SQLALCHEMY_DATABASE_URL = "sqlite:///./test_secure_backend.db"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()

main.app.dependency_overrides[database.get_db] = override_get_db
client = TestClient(main.app)

@pytest.fixture(autouse=True)
def run_around_tests():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)

def test_encryption_decryption():
    test_str = "sensitive_data_123"
    encrypted = encryption.encrypt_pii(test_str)
    assert encrypted != test_str
    
    decrypted = encryption.decrypt_pii(encrypted)
    assert decrypted == test_str

def test_user_flow():
    # Use unique username to avoid conflicts across test runs if DB persists
    username = f"testuser_{uuid.uuid4().hex[:8]}"
    
    # 1. Create User
    response = client.post(
        "/api/v1/users",
        json={"username": username, "password": "testpassword"}
    )
    assert response.status_code == 200
    assert response.json()["username"] == username
    
    # 2. Login
    response = client.post(
        "/api/v1/auth/token",
        data={"username": username, "password": "testpassword"}
    )
    assert response.status_code == 200
    token = response.json()["access_token"]
    assert token is not None
    
    return token

def test_scan_and_verify(tmp_path):
    token = test_user_flow()
    headers = {"Authorization": f"Bearer {token}"}
    
    # 1. Scan Mock Document
    image_path = tmp_path / "dummy.png"
    image_path.write_bytes(b"dummy_bytes")
    
    with open(image_path, "rb") as f:
        scan_resp = client.post(
            "/api/v1/identity/scan",
            files={"file": ("dummy.png", f, "image/png")},
            headers=headers
        )
    
    assert scan_resp.status_code == 200
    scan_data = scan_resp.json()
    assert scan_data["document_type"] == "KTP"
    
    # 2. Verify and Save
    verify_resp = client.post(
        "/api/v1/identity/verify",
        json={
            "document_type": scan_data["document_type"],
            "nik": scan_data["nik"],
            "full_name": scan_data["full_name"],
            "date_of_birth": scan_data["date_of_birth"]
        },
        headers=headers
    )
    assert verify_resp.status_code == 200
    assert verify_resp.json()["nik"] == scan_data["nik"]
    
    # 3. Fetch Decrypted Record
    get_resp = client.get(
        "/api/v1/identity/me",
        headers=headers
    )
    assert get_resp.status_code == 200
    records = get_resp.json()
    assert len(records) == 1
    assert records[0]["nik"] == scan_data["nik"] # Should be successfully decrypted
