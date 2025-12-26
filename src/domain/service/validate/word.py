from typing import Callable

from ...core.word import Word


class WordValidator:
    def __init__(self, func: Callable[[float, float, str], bool]) -> None:
        self._func = func

    def validate(self, word_obj: Word) -> bool:
        return self._func(word_obj.start, word_obj.end, word_obj.word)
