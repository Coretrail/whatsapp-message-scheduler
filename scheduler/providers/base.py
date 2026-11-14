"""Provider boundary: retry means definitely not submitted; unknown is never replayed."""
from dataclasses import dataclass
from typing import Literal, Protocol

@dataclass(frozen=True)
class Result:
    state: Literal['accepted', 'retry', 'failed', 'unknown']
    provider_id: str | None = None
    error: str | None = None

class Provider(Protocol):
    def send(self, job: dict) -> Result: ...
    def health(self) -> dict: ...
