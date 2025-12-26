from typing import Optional, Iterator

from elevenlabs.text_to_speech.client import TextToSpeechClient

from src.domain.core.tts_base import TTSBase

class TTSElevenlabs(TTSBase):
    _eleven_client: TextToSpeechClient = None  # type: ignore

    def __init__(self, _eleven_client: TextToSpeechClient) -> None:
        self._eleven_client = _eleven_client

    def synthesize(
        self,
        text: str,
        voice_id: str,
        model_id: Optional[str] = None,
    ) -> Iterator[bytes]:
        data = self._eleven_client.convert(
            voice_id=voice_id, text=text, model_id=model_id
        )

        return data
