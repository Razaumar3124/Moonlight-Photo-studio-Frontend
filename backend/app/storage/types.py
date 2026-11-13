"""Small value types shared by the storage backends."""

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class StoredObject:
    """One object in storage: its key, size in bytes and last-modified time (UTC)."""

    key: str
    size: int
    last_modified: datetime
