import json
from typing import Iterable

from src.domain.core.sentence import Sentence


def sentence_to_json(sentence: Sentence) -> str:
    """Serialize a single sentence to JSON string."""
    return json.dumps(
        {"start": sentence.start, "end": sentence.end, "sentence": sentence.sentence}
    )


def sentence_to_srt(sentence: Sentence) -> str:
    """Render a single sentence as an SRT string."""
    return f"\n{sentence.start} --> {sentence.end}\n{sentence.sentence}\n"
