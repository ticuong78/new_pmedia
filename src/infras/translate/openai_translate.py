from typing import Iterable, List, Optional

from openai import OpenAI

from src.domain.core.translator import Translator


class OpenAITranslator(Translator):
    """Translate text using OpenAI chat completions."""

    def __init__(self, client: OpenAI, model: str = "gpt-4o") -> None:
        self._client = client
        self._model = model

    def translate(
        self,
        text: str,
        target_language: str,
        source_language: Optional[str] = None,
    ) -> str:
        prompt = self._build_prompt(text, target_language, source_language)
        response = self._client.chat.completions.create(
            model=self._model,
            messages=[
                {
                    "role": "system",
                    "content": "You are a precise translator. Keep meaning and tone.",
                },
                {"role": "user", "content": prompt},
            ],
        )

        content = response.choices[0].message.content
        if not content:
            raise RuntimeError("Translation failed: empty response")
        return content.strip()

    def translate_many(
        self,
        texts: Iterable[str],
        target_language: str,
        source_language: Optional[str] = None,
    ) -> List[str]:
        return [
            self.translate(text, target_language, source_language) for text in texts
        ]

    def _build_prompt(
        self, text: str, target_language: str, source_language: Optional[str]
    ) -> str:
        if source_language:
            return (
                f"Translate from {source_language} to {target_language}:\n\n{text}"
            )
        return f"Translate to {target_language}:\n\n{text}"
