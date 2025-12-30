import json
from dataclasses import dataclass
from typing import Any


@dataclass
class Sentence:
    id: int
    start: float
    end: float
    sentence: str

    def to_json(self) -> str:
        response_dict = {
            "id": self.id,
            "start": self.start,
            "end": self.end,
            "sentence": self.sentence,
        }

        return json.dumps(response_dict)

    def to_srt(self) -> str:
        """Render as SRT block."""
        response_srt = """{start} --> {end}\n{sentence}\n\n"""
        return response_srt.format(
            start=self.start, end=self.end, sentence=self.sentence
        )
