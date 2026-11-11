from datetime import UTC, datetime

from bson import ObjectId
from pymongo import ASCENDING, IndexModel
from pymongo.asynchronous.collection import AsyncCollection
from pymongo.asynchronous.database import AsyncDatabase
from pymongo.errors import DuplicateKeyError

from app.core.exceptions import AccountAlreadyExistsException
from app.models.user import UserInDB


class UserRepository:
    """Data access repository for users collection."""

    def __init__(self, db: AsyncDatabase) -> None:
        self.collection: AsyncCollection = db["users"]

    async def create_indexes(self) -> None:
        """Create necessary indexes for users collection idempotently."""
        indexes = [
            IndexModel([("email", ASCENDING)], unique=True, name="idx_users_email_unique"),
            IndexModel(
                [("phone", ASCENDING)],
                unique=True,
                sparse=True,
                name="idx_users_phone_unique_sparse",
            ),
            IndexModel([("google_id", ASCENDING)], sparse=True, name="idx_users_google_id_sparse"),
        ]
        await self.collection.create_indexes(indexes)

    async def create(self, user: UserInDB) -> UserInDB:
        """Insert a new user document. Handles duplicate key errors safely."""
        doc = user.model_dump(by_alias=True)
        # Ensure _id is stored as BSON ObjectId
        doc["_id"] = ObjectId(user.id)

        try:
            await self.collection.insert_one(doc)
            return user
        except DuplicateKeyError as e:
            err_msg = str(e)
            if "email" in err_msg:
                raise AccountAlreadyExistsException(
                    field="email", issue="Email is already registered"
                ) from e
            if "phone" in err_msg:
                raise AccountAlreadyExistsException(
                    field="phone", issue="Mobile number is already registered"
                ) from e
            raise AccountAlreadyExistsException(
                field="identifier",
                issue="An account with this email or mobile number already exists",
            ) from e

    async def get_by_id(self, user_id: str) -> UserInDB | None:
        """Find user by string ObjectId."""
        if not ObjectId.is_valid(user_id):
            return None
        doc = await self.collection.find_one({"_id": ObjectId(user_id)})
        return UserInDB(**doc) if doc else None

    async def get_by_email(self, email: str) -> UserInDB | None:
        """Find user by lowercase email."""
        doc = await self.collection.find_one({"email": email.strip().lower()})
        return UserInDB(**doc) if doc else None

    async def get_by_phone(self, phone: str) -> UserInDB | None:
        """Find user by E.164 phone."""
        doc = await self.collection.find_one({"phone": phone.strip()})
        return UserInDB(**doc) if doc else None

    async def get_by_google_id(self, google_id: str) -> UserInDB | None:
        """Find user by Google OAuth provider ID."""
        doc = await self.collection.find_one({"google_id": google_id})
        return UserInDB(**doc) if doc else None

    async def update_last_login(self, user_id: str) -> None:
        """Record the timestamp of a successful authentication."""
        if ObjectId.is_valid(user_id):
            await self.collection.update_one(
                {"_id": ObjectId(user_id)},
                {"$set": {"last_login_at": datetime.now(UTC), "updated_at": datetime.now(UTC)}},
            )

    async def link_google_id(self, user_id: str, google_id: str) -> None:
        """Associate a verified Google ID with an existing user account."""
        if ObjectId.is_valid(user_id):
            await self.collection.update_one(
                {"_id": ObjectId(user_id)},
                {"$set": {"google_id": google_id, "updated_at": datetime.now(UTC)}},
            )

    async def update_password(self, user_id: str, password_hash: str) -> None:
        """Update user password hash and record password change timestamp."""
        if ObjectId.is_valid(user_id):
            now = datetime.now(UTC)
            await self.collection.update_one(
                {"_id": ObjectId(user_id)},
                {
                    "$set": {
                        "password_hash": password_hash,
                        "password_changed_at": now,
                        "updated_at": now,
                    }
                },
            )
