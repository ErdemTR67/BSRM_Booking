from typing import Generic, TypeVar

from pydantic import BaseModel, Field


ItemT = TypeVar("ItemT")


class PageResponse(BaseModel, Generic[ItemT]):
    items: list[ItemT]
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=100)
    total: int = Field(ge=0)
