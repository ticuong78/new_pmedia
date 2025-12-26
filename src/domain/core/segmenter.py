from abc import ABC, abstractmethod
from typing import List

from .sentence import Sentence
from .word import Word


class Segmenter(ABC):
    @abstractmethod
    def segment(self, words: List[Word]) -> List[Sentence]:
        pass
