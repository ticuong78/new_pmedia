import hashlib
from typing import List, Tuple

from src.application.service.cache import DiskCache
from src.domain.core.segmenter import Segmenter
from src.domain.core.sentence import Sentence
from src.domain.core.word import Word


class SegmentService:
    """Application service to run segmentation and cache results."""

    def __init__(self, segmenter: Segmenter, cache: DiskCache) -> None:
        self._segmenter = segmenter
        self._cache = cache

    def _fingerprint(self, words: List[Word]) -> bytes:
        # Create a deterministic fingerprint from word timings and text.
        payload = "|".join(f"{w.start}-{w.end}-{w.word}" for w in words)
        return hashlib.sha256(payload.encode("utf-8")).digest()

    def segment(self, words: List[Word]) -> Tuple[List[Sentence], str | None]:
        key = (
            self._cache.make_key("segment", self._fingerprint(words))
            if self._cache
            else None
        )

        if key and (cached := self._cache.get(key)) is not None:
            return cached, key  # type: ignore

        sentences = self._segmenter.segment(words)
        # print(sentences)
        for idx, sentence in enumerate(sentences, start=1):
            sentence.id = idx  # type: ignore[attr-defined]
            # print(sentence.id)
            # print(sentence)

        if key and self._cache:
            self._cache.set(key, sentences)

        return sentences, key
