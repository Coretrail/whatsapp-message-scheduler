"""Strict registry. Future providers require explicit implementation and review."""
import os
from .base import Provider, Result
from .demo import DemoProvider

class Channels:
    def __init__(self, name: str | None = None):
        selected = os.getenv('MESSAGE_PROVIDER', 'demo') if name is None else name
        if selected != 'demo':
            raise ValueError('Only the demo provider is supported in this release')
        self.provider: Provider = DemoProvider()

    def send(self, job: dict) -> Result:
        return self.provider.send(job)

    def health(self) -> dict:
        return self.provider.health()
