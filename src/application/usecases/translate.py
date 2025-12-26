from src.application.service.cache import DiskCache
from src.domain.core.translator import Translator


class Translate:
    def __init__(self, translator: Translator, cache: DiskCache | None = None):
        self._translator = translator
        self._cache = cache

    def execute(
        self, text: str, target_language: str, source_language: str | None = None
    ) -> tuple[str, str | None]:
        key = (
            self._cache.make_key(
                "translate",
                target_language,
                source_language or "",
                bytes(text, "utf-8"),
            )
            if self._cache
            else None
        )

        if key and (cached := self._cache.get(key)) is not None:
            return cached, key  # type: ignore

        translated = self._translator.translate(text, target_language, source_language)

        if key and self._cache:
            self._cache.set(key, translated)

        return translated, key
