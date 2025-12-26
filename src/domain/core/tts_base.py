from abc import ABC, abstractmethod
from typing import Iterator, Optional


class TTSBase(ABC):
    @abstractmethod
    def synthesize(
        self, text: str, voice_id: str, model_id: Optional[str] = None
    ) -> Iterator[bytes]:
        """Generate audio bytes for the given text."""
        ...
