"""One row in the sources panel."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Source:
    id: str
    label: str
    status: str
    detail: str

    def as_dict(self) -> dict[str, str]:
        return {
            "id": self.id,
            "label": self.label,
            "status": self.status,
            "detail": self.detail,
        }


def clip(text: str, limit: int = 180) -> str:
    cleaned = " ".join((text or "").split())
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 1].rstrip() + "…"
