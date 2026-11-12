import re

import pytest

from app.repositories.design_repository import DesignRepository


class _RecordingCollection:
    def __init__(self) -> None:
        self.queries: list[dict] = []

    async def count_documents(self, query: dict) -> int:
        self.queries.append(query)
        return 0


@pytest.mark.parametrize(
    "text",
    ["(", "[a-", ".*", "(a+)+$", "a{1,", "\\", "$where", "Dining Room (2)", "50% off?"],
)
@pytest.mark.asyncio
async def test_search_text_is_matched_literally_never_as_a_regex(text: str):
    """User search text is escaped before it reaches MongoDB's $regex."""
    repo = DesignRepository.__new__(DesignRepository)
    repo.designs = _RecordingCollection()  # type: ignore[assignment]

    await repo.list_designs_by_user("665f1c2e9b1d4a00aaaaaaaa", search=text)

    condition = repo.designs.queries[0]["title"]  # type: ignore[attr-defined]
    pattern = condition["$regex"]
    assert condition["$options"] == "i"
    re.compile(pattern)  # always a valid pattern
    # It matches the typed text itself, and nothing the raw text would have matched as a regex.
    assert re.search(pattern, f"My {text} wall", re.IGNORECASE)
    if text == ".*":
        assert not re.search(pattern, "Anything else", re.IGNORECASE)
    if text == "(a+)+$":
        assert not re.search(pattern, "aaaa", re.IGNORECASE)
