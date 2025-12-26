from typing import Iterator

from src.application.service.cache import DiskCache
from src.domain.core.sentence import Sentence
from src.domain.core.stt_base import STTResponse
from src.domain.core.tts_base import TTSBase


class TextToSpeech:
    def __init__(self, tts_client: TTSBase, cache: DiskCache | None = None) -> None:
        self._tts_client = tts_client
        self._cache = cache

    def _extract_text(self, payload) -> str | None:
        if isinstance(payload, STTResponse):
            return payload.text
        if isinstance(payload, list) and payload and all(
            isinstance(item, Sentence) for item in payload
        ):
            return " ".join(sentence.sentence for sentence in payload)
        if isinstance(payload, str):
            return payload
        return None

    def synthesize(
        self, text: str, voice_id: str, model_id: str | None = None
    ) -> tuple[Iterator[bytes], str]:
        """Synthesize directly from text."""
        return self._tts_client.synthesize(text, voice_id, model_id), text

    def synthesize_from_cache(
        self, key: str, voice_id: str, model_id: str | None = None
    ) -> tuple[Iterator[bytes], str]:
        if not self._cache:
            raise ValueError("Cache is required to synthesize from a cached key.")

        cached_value = self._cache.get(key)

        if cached_value is None:
            raise KeyError(f"Cache key not found: {key}")

        text = self._extract_text(cached_value)
        if not text:
            raise ValueError(
                f"Unsupported cache entry type: {type(cached_value).__name__}"
            )

        return self._tts_client.synthesize(text, voice_id, model_id), text
