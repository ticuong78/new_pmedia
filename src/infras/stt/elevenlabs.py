from elevenlabs.speech_to_text.client import SpeechToTextClient

from src.domain.core.stt_base import STTBase, STTResponse
from src.domain.core.word import Word


class STTElevenlabs(STTBase):
    _eleven_client: SpeechToTextClient = None  # type: ignore

    def __init__(self, eleven_client: SpeechToTextClient) -> None:
        self._eleven_client = eleven_client

    def transcribe(self, model_id: str, file: bytes) -> STTResponse:
        response = self._eleven_client.convert(
            model_id=model_id,
            file=file,
        )

        return STTResponse(
            text=response.text,  # type: ignore
            words=[
                Word(start=single.start, end=single.end, word=single.text)  # type: ignore
                for single in response.words  # type: ignore
            ],
        )
