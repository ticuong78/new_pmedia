import json
from typing import Iterable

from src.domain.core.word import Word


def word_to_json(word: Word) -> str:
    """Serialize a single word to JSON string."""
    return json.dumps({"start": word.start, "end": word.end, "word": word.word})


def word_to_srt(word: Word) -> str:
    """Render a single word as an SRT string."""
    return f"{word.start} --> {word.end}\n{word.word}\n"
