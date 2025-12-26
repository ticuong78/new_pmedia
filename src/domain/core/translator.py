from abc import ABC, abstractmethod
from typing import Iterable, List, Optional


class Translator(ABC):
    @abstractmethod
    def translate(
        self, text: str, target_language: str, source_language: Optional[str] = None
    ) -> str:
        ...

    def translate_many(
        self, texts: Iterable[str], target_language: str, source_language: Optional[str] = None
    ) -> List[str]:
        """Default batch implementation."""
        return [self.translate(text, target_language, source_language) for text in texts]
