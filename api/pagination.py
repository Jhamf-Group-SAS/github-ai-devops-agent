"""
Pagination utilities for list endpoints.
"""

from dataclasses import dataclass
from typing import Generic, TypeVar

T = TypeVar("T")


@dataclass
class Page(Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int

    @property
    def total_pages(self) -> int:
        if self.page_size == 0:
            return 0
        return (self.total + self.page_size - 1) // self.page_size

    @property
    def has_next(self) -> bool:
        return self.page < self.total_pages

    @property
    def has_prev(self) -> bool:
        return self.page > 1


def paginate(items: list[T], page: int = 1, page_size: int = 20) -> Page[T]:
    """Slice a list into a Page."""
    if page < 1:
        page = 1
    if page_size < 1:
        page_size = 20
    start = (page - 1) * page_size
    end = start + page_size
    return Page(
        items=items[start:end],
        total=len(items),
        page=page,
        page_size=page_size,
    )
