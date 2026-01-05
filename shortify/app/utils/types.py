from typing import Any, TypedDict


class PaginationDict(TypedDict):
    page: int
    per_page: int
    total: int
    results: list[Any]
