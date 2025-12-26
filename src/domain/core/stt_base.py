from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List

from .word import Word


@dataclass
class STTResponse:
    text: str
    words: List[Word]


class STTBase(ABC):
    @abstractmethod
    def transcribe(self, model_id: str, file: bytes) -> STTResponse: ...
