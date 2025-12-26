from dataclasses import dataclass


@dataclass
class Word:
    start: float
    end: float
    word: str
