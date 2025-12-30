from typing import List

from src.domain.core.segmenter import Segmenter
from src.domain.core.sentence import Sentence
from src.domain.core.word import Word


class PunctuationSegmenter(Segmenter):
    """Segment words into sentences using simple punctuation rules."""

    def __init__(self, sentence_end_tokens: str = ".?!") -> None:
        # Example: ".?!" to treat ., ?, ! as sentence boundaries.
        self._sentence_end_tokens = tuple(sentence_end_tokens)

    def _is_sentence_ending(self, token: str) -> bool:
        return any(end_token in token for end_token in self._sentence_end_tokens)

    def _join_words(self, words: List[Word]) -> str:
        # Normalize to avoid duplicated spacing coming from raw word tokens.
        text = " ".join(word.word.strip() for word in words).strip()
        # text = "".join(text.split())
        for end_token in self._sentence_end_tokens:
            text = text.replace(f" {end_token}", end_token)
        return text

    def segment(self, words: List[Word]) -> List[Sentence]:
        segments: List[List[Word]] = []
        current_sentence: List[Word] = []

        for word in words:
            if not current_sentence and not word.word.strip():
                # Skip leading whitespace-only tokens.
                continue

            current_sentence.append(word)

            if self._is_sentence_ending(word.word):
                segments.append(current_sentence)
                current_sentence = []

        if current_sentence:
            segments.append(current_sentence)

        sentences: List[Sentence] = []
        for segment in segments:
            start = segment[0].start
            end = segment[-1].end
            sentence_text = self._join_words(segment)
            sentences.append(
                Sentence(
                    id=len(segments) + 1, start=start, end=end, sentence=sentence_text
                )
            )

        return sentences
