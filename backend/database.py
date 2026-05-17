from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv
import os
import certifi

load_dotenv()

MONGODB_URL = os.getenv("MONGODB_URL", "mongodb://localhost:27017")
DB_NAME = os.getenv("DB_NAME", "findjol_db")

# Atlas (`mongodb+srv://`) needs a working TLS chain. On Windows the system
# cert store doesn't always have Atlas's intermediate CAs, producing
# `TLSV1_ALERT_INTERNAL_ERROR` during handshake. Always point pymongo at
# certifi's bundled chain — harmless for plain `mongodb://localhost`.
_client_kwargs: dict = {}
if MONGODB_URL.startswith("mongodb+srv://") or "tls=true" in MONGODB_URL.lower():
    _client_kwargs["tlsCAFile"] = certifi.where()

client = AsyncIOMotorClient(MONGODB_URL, **_client_kwargs)
db = client[DB_NAME]

users_collection = db["users"]
identity_records_collection = db["identity_records"]


async def create_indexes():
    """Call once on startup to ensure unique index on username."""
    await users_collection.create_index("username", unique=True)
    await identity_records_collection.create_index("user_id")
