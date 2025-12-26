from typing import Callable

from ...core.sentence import Sentence


class SentenceValidator:
    def __init__(self, func: Callable[[float, float, str], bool]) -> None:
        self._func = func

    def validate(self, sentence_obj: Sentence) -> bool:
        return self._func(sentence_obj.start, sentence_obj.end, sentence_obj.sentence)
