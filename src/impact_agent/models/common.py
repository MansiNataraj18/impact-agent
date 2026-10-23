from typing import Literal

from pydantic import BaseModel


class UnresolvedItem(BaseModel):
    scope: Literal["tdd", "section", "change"]
    change_number: int | None = None
    field: str | None = None
    reason: str
    line: int | None = None
