import os
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from elevenlabs import ElevenLabs

from dotenv import load_dotenv

from src.application.service.cache import DiskCache
from src.application.service.segment import SegmentService
from src.application.usecases.transcribe import Transcribe
from src.application.usecases.translate import Translate
from src.cli.cache import BASE_CACHE_DIR
from src.infras.segmenting.openai_segmenting import OpenAISegmenter
from src.infras.stt.elevenlabs import STTElevenlabs
from src.infras.translate.openai_translate import OpenAITranslator
from openai import OpenAI

load_dotenv()


class SegmentServiceFactory:
    def __init__(self, openai_client: OpenAI) -> None:
        self._openai_client = openai_client

    def get_segment_service(
        self,
        type: Literal["openai", "words_count", "punctuation"],
        prompt: str | None = None,
        model: str | None = None,
    ):
        if type == "openai":
            if not model or not prompt:
                raise ValueError(
                    "When using openai as a segmenter, please provide your service a model and a prompt."
                )
            cache = DiskCache(directory=str(BASE_CACHE_DIR))
            return SegmentService(
                OpenAISegmenter(self._openai_client, prompt, model), cache
            )
        else:
            ...  # haven't supported yet


@dataclass
class AppContainer:
    cache: DiskCache
    transcribe: Transcribe
    segment_service_factory: SegmentServiceFactory
    translate: Translate


def build_container() -> AppContainer:
    elevenlabs_api_key = os.getenv("ELEVENLABS_API_KEY")
    openai_api_key = os.getenv("OPENAI_API_KEY")
    if not elevenlabs_api_key:
        raise RuntimeError("Missing ELEVENLABS_API_KEY")

    if not openai_api_key:
        raise RuntimeError("Missing OPENAI_API_KEY")

    elevenlabs_client = ElevenLabs(api_key=elevenlabs_api_key)
    openai_client = OpenAI(api_key=openai_api_key)
    cache_dir = Path(__file__).resolve().parents[2] / ".cache"
    cache = DiskCache(directory=str(cache_dir))

    stt_adapter = STTElevenlabs(elevenlabs_client.speech_to_text)

    # factory
    segment_service_factory = SegmentServiceFactory(openai_client)

    # use cases
    transcribe = Transcribe(stt_adapter, cache)
    translate = Translate(OpenAITranslator(openai_client), cache)

    return AppContainer(
        cache=cache,
        transcribe=transcribe,
        segment_service_factory=segment_service_factory,
        translate=translate,
    )
