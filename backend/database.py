from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv
import os

load_dotenv()

MONGODB_URL = os.getenv("MONGODB_URL", "mongodb://localhost:27017")
DB_NAME = os.getenv("DB_NAME", "findjol_db")

client = AsyncIOMotorClient(MONGODB_URL)
db = client[DB_NAME]

users_collection = db["users"]
identity_records_collection = db["identity_records"]


async def create_indexes():
    """Call once on startup to ensure unique index on username."""
    await users_collection.create_index("username", unique=True)
    await identity_records_collection.create_index("user_id")
