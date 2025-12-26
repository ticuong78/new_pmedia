import json
from typing import List

from openai import OpenAI

from src.domain.core.sentence import Sentence
from src.domain.core.segmenter import Segmenter
from src.domain.core.word import Word
from src.domain.service.validate.sentence import SentenceValidator


class OperationFailure(Exception):
    pass


class OpenAISegmenter(Segmenter):
    """Segmenter backed by OpenAI chat completions."""

    def __init__(self, open_ai_client: OpenAI, prompt: str, model: str) -> None:
        self._open_ai_client = open_ai_client
        self._prompt = prompt
        self._model = model
        self._sentence_validator: SentenceValidator | None = None

    def segment(self, words: List[Word]) -> List[Sentence]:
        if not self._prompt:
            raise ValueError("Missing prompt for current segmenter.")

        words_json = json.dumps([w.__dict__ for w in words], ensure_ascii=False)

        chat_response = self._open_ai_client.chat.completions.create(
            messages=[
                {
                    "role": "system",
                    "content": "You are a helpful assistant working with transcriptions, translating and writing.",
                },
                {"role": "user", "content": self._prompt.format(words=words_json)},
            ],
            model=self._model,
            response_format={"type": "json_object"},
        )

        content = chat_response.choices[0].message.content

        if not content:
            raise OperationFailure("Failed to perform segmentation by OpenAI.")

        try:
            payload = json.loads(content)
        except json.JSONDecodeError as err:
            raise OperationFailure(f"Failed to decode segmentation output: {err}") from err

        sentences_payload = payload["sentences"] if isinstance(payload, dict) else payload
        sentences = [
            Sentence(start=entry["start"], end=entry["end"], sentence=entry["sentence"])
            for entry in sentences_payload
        ]

        if self._sentence_validator:
            for s in sentences:
                self._sentence_validator.validate(s)

        return sentences
