from src.domain.core.stt_base import STTBase, STTResponse
from src.application.service.cache import DiskCache


class Transcribe:
    def __init__(
        self,
        transcribing_client: STTBase,
        cache: DiskCache | None = None,
    ):
        self._transcribing_client = transcribing_client
        self._cache = cache

    # common services
    def execute(self, model_id: str, file: bytes) -> tuple[STTResponse, str | None]:
        key = self._cache.make_key("stt", model_id, file) if self._cache else None

        if key and (cached := self._cache.get(key)) is not None:  # type: ignore
            return cached, key

        response = self._transcribing_client.transcribe(model_id, file)

        if key and self._cache:
            self._cache.set(key, response)

        return response, key
