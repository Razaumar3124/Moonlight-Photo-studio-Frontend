from typing import Annotated

from fastapi import Depends
from pymongo.asynchronous.database import AsyncDatabase

from app.db.mongodb import mongo_manager


async def get_db() -> AsyncDatabase:
    """Dependency provider yielding the active AsyncDatabase instance."""
    return mongo_manager.get_database()


DatabaseDep = Annotated[AsyncDatabase, Depends(get_db)]
