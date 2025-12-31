from typing import List

from src.domain.core.segmenter import Segmenter
from src.domain.core.sentence import Sentence
from src.domain.core.word import Word


class WordCountSegmenter(Segmenter):
    """Segment words into sentences by a fixed max word count."""

    def __init__(self, max_words_per_segment: int = 5) -> None:
        if max_words_per_segment <= 0:
            raise ValueError("max_words_per_segment must be > 0")
        self._max_words_per_segment = max_words_per_segment

    @staticmethod
    def _is_word_token(text: str) -> bool:
        stripped = text.strip()
        return bool(stripped) and any(ch.isalnum() for ch in stripped)

    def _join_words(self, words: List[Word]) -> str:
        # Normalize spacing to avoid artifacts from tokenization.
        text = " ".join(w.word.strip() for w in words).strip()
        for punct in [",", ".", "?", "!", ";", ":"]:
            text = text.replace(f" {punct}", punct)
        return text

    def segment(self, words: List[Word]) -> List[Sentence]:
        segments: List[List[Word]] = []
        current_segment: List[Word] = []
        word_count = 0

        for word in words:
            if not current_segment and word.word == " ":
                # Skip leading whitespace-only tokens.
                continue

            current_segment.append(word)

            if self._is_word_token(word.word):
                word_count += 1

            if word_count >= self._max_words_per_segment:
                segments.append(current_segment)
                current_segment = []
                word_count = 0

        if current_segment:
            segments.append(current_segment)

        sentences: List[Sentence] = []
        for segment in segments:
            sentences.append(
                Sentence(
                    id=0,  # Will be set by SegmentService.
                    start=segment[0].start,
                    end=segment[-1].end,
                    sentence=self._join_words(segment),
                )
            )

        return sentences
