from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class PolygraphError(Exception):
    code: str
    message: str
    status_code: int = 400
    detail: dict[str, Any] = field(default_factory=dict)

    def __str__(self) -> str:
        return self.message
