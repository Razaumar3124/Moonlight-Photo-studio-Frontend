import logging
import time
from typing import Any

import certifi
from pymongo import AsyncMongoClient
from pymongo.asynchronous.database import AsyncDatabase
from pymongo.errors import ConnectionFailure, OperationFailure, PyMongoError, ServerSelectionTimeoutError

from app.core.config import Settings, get_settings
from app.core.exceptions import DatabaseUnavailableException
from app.core.logging import sanitize_sensitive_data

logger = logging.getLogger("saf_studio.db")


class MongoManager:
    """Singleton connection manager for official PyMongo Async client."""

    def __init__(self) -> None:
        self.client: AsyncMongoClient | None = None
        self.db: AsyncDatabase | None = None
        self._database_name: str = ""

    async def connect(self, settings: Settings | None = None) -> None:
        """Initialize the shared AsyncMongoClient connection pool."""
        if self.client is not None:
            logger.debug("MongoManager: Connection already initialized")
            return

        cfg = settings or get_settings()
        self._database_name = cfg.DATABASE_NAME

        masked_url = sanitize_sensitive_data(cfg.MONGODB_URL)
        is_atlas_or_tls = (
            cfg.MONGODB_URL.startswith("mongodb+srv://")
            or "tls=true" in cfg.MONGODB_URL.lower()
            or "ssl=true" in cfg.MONGODB_URL.lower()
        )
        logger.info(
            "Initializing PyMongo Async client for database '%s' at %s (TLS: %s)",
            self._database_name,
            masked_url,
            is_atlas_or_tls,
        )

        client_kwargs: dict[str, Any] = {
            "serverSelectionTimeoutMS": cfg.MONGODB_TIMEOUT_MS,
            "connectTimeoutMS": cfg.MONGODB_TIMEOUT_MS,
            "minPoolSize": 1,
            "maxPoolSize": 25,
            "maxIdleTimeMS": 45000,
            "uuidRepresentation": "standard",
            "retryWrites": True,
        }

        if is_atlas_or_tls:
            client_kwargs["tlsCAFile"] = certifi.where()

        try:
            self.client = AsyncMongoClient(cfg.MONGODB_URL, **client_kwargs)
            self.db = self.client[self._database_name]
            logger.info("PyMongo Async client connection pool configured successfully")
        except PyMongoError as err:
            logger.error("Failed to initialize PyMongo Async client: %s", err)
            raise DatabaseUnavailableException(
                message="Failed to initialize MongoDB client",
                issue=str(err),
            ) from err

    async def disconnect(self) -> None:
        """Close the AsyncMongoClient connection pool cleanly."""
        if self.client is not None:
            logger.info("Closing PyMongo Async connection pool")
            try:
                await self.client.close()
            except Exception as e:
                logger.warning("Error during MongoDB client closure: %s", e)
            finally:
                self.client = None
                self.db = None
                logger.info("PyMongo Async connection pool closed")

    def get_database(self) -> AsyncDatabase:
        """Return the active database instance."""
        if self.db is None:
            raise DatabaseUnavailableException(
                message="Database connection has not been initialized",
                issue="Application database manager is not connected",
            )
        return self.db

    async def ping(self) -> float:
        """Ping the MongoDB server and return round-trip latency in milliseconds.

        Raises:
            DatabaseUnavailableException: If ping fails or times out.
        """
        if self.client is None or self.db is None:
            raise DatabaseUnavailableException(
                message="Database connection has not been initialized",
                issue="MongoDB client instance is null",
            )

        try:
            start_time = time.perf_counter()
            # Execute low-overhead ping command against the admin/current database
            await self.db.command("ping")
            latency_ms = round((time.perf_counter() - start_time) * 1000, 2)
            return latency_ms
        except (ServerSelectionTimeoutError, ConnectionFailure) as exc:
            logger.error("MongoDB connectivity check failed: %s", type(exc).__name__)
            raise DatabaseUnavailableException(
                message="Database service is currently unreachable",
                issue=f"MongoDB ping timed out or refused connection: {type(exc).__name__}",
            ) from exc
        except PyMongoError as exc:
            logger.error("PyMongo error during ping: %s", exc)
            raise DatabaseUnavailableException(
                message="Database operation failed",
                issue=f"PyMongo command failed: {type(exc).__name__}",
            ) from exc
        except Exception as exc:
            logger.error("Unexpected error during database ping: %s", exc)
            raise DatabaseUnavailableException(
                message="Database check failed unexpectedly",
                issue=f"Unexpected error: {type(exc).__name__}",
            ) from exc


mongo_manager = MongoManager()
