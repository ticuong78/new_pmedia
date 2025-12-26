import json
from typing import Any, Iterable, Optional

import typer

from src.cli.container import AppContainer
from src.domain.core.sentence import Sentence
from src.domain.core.stt_base import STTResponse

app = typer.Typer(help="Transcript mapping commands")

DEFAULT_PROMPT_TEMPLATE_2 = """
Bạn được cung cấp hai tập dữ liệu:

1. Phiên bản A (nội dung gốc tiếng Trung), gồm nhiều câu, mỗi câu có:
- sentence_start
- sentence_end
- sentence_form

{goc}

2. Phiên bản B (nội dung đã dịch và rút gọn sang tiếng Việt), gồm các câu:
- sentence_start
- sentence_end
- sentence_form

{rut}

Nhiệm vụ của bạn:

Với MỖI câu trong phiên bản B, hãy xác định câu hoặc nhóm câu trong phiên bản A
có NỘI DUNG TƯƠNG ĐƯƠNG VỀ NGỮ NGHĨA NHẤT.

Lưu ý:
- Một câu B có thể tương ứng với nhiều câu A liên tiếp.
- Không được suy diễn timestamp mới.
- Phải sử dụng timestamp gốc của phiên bản A.

Đầu ra cho mỗi câu B là một object JSON có dạng:

{
  "sentence_start": <min(sentence_start_A)>,
  "sentence_end": <max(sentence_end_A)>,
  "sentence_form": "<sentence_form_B>"
}

Trong đó:
- sentence_start và sentence_end là timestamp gốc lấy từ phiên bản A.
- sentence_form là sentence_form của phiên bản B (UTF-8).

Định dạng đầu ra là MỘT MẢNG JSON.
Không giải thích gì thêm.

"""



def _extract_from_json_value(value: Any) -> str:
    if isinstance(value, Sentence):
        return _render_sentence(value)
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        for key in ("text", "sentence", "content"):
            if key in value:
                return str(value[key])
        if "words" in value and isinstance(value["words"], Iterable):
            words = [
                w.get("word")
                for w in value["words"]
                if isinstance(w, dict) and "word" in w
            ]
            return " ".join(word for word in words if word)
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, list):
        parts = [_extract_from_json_value(item) for item in value]
        return "\n".join(part for part in parts if part)
    return str(value)


def _parse_json_response(content: str) -> Any:
    stripped = content.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        stripped = "\n".join(lines).strip()
    return json.loads(stripped)


def _render_sentence(sentence: Sentence) -> str:
    return f"[{sentence.start:.2f}-{sentence.end:.2f}] {sentence.sentence}"


def _extract_from_cache_value(value: Any) -> str:
    if isinstance(value, STTResponse):
        return value.text
    if (
        isinstance(value, list)
        and value
        and all(isinstance(item, Sentence) for item in value)
    ):
        return "\n".join(_render_sentence(item) for item in value)
    return _extract_from_json_value(value)


@app.command()
def map(
    prompt: str = typer.Option(
        DEFAULT_PROMPT_TEMPLATE_2,
        "--prompt",
        help="Prompt template; must include {rut} and {goc} placeholders.",
    ),
    rut_key: str = typer.Option(
        ...,
        "--rut-key",
        help="Cache key for shortened/edited transcript (segments or text).",
    ),
    goc_key: str = typer.Option(
        ...,
        "--goc-key",
        help="Cache key for original transcript (segments or text).",
    ),
    model: Optional[str] = typer.Option(
        None,
        "--model",
        help="Override OpenAI model id; defaults to gpt-4o.",
    ),
    show_prompt: bool = typer.Option(
        False, "--show-prompt", help="Print the filled prompt before sending to OpenAI."
    ),
    ctx: typer.Context = typer.Option(None, hidden=True),
):
    if not isinstance(ctx.obj, AppContainer):
        raise typer.BadParameter("App container not initialized")

    cache = ctx.obj.cache

    rut_value = cache.get(rut_key)
    goc_value = cache.get(goc_key)
    if rut_value is None:
        raise typer.BadParameter(f"Cache key not found for rut: {rut_key}")
    if goc_value is None:
        raise typer.BadParameter(f"Cache key not found for goc: {goc_key}")

    transcript_text = _extract_from_cache_value(rut_value)
    transcript_text_speed = _extract_from_cache_value(goc_value)

    filled_prompt = prompt.replace("{rut}", transcript_text).replace(
        "{goc}", transcript_text_speed or transcript_text
    )

    if show_prompt:
        print(filled_prompt)

    if not isinstance(ctx.obj, AppContainer):
        raise typer.BadParameter("App container not initialized")

    client = ctx.obj.openai_client

    try:
        response = client.chat.completions.create(
            messages=[
                {
                    "role": "system",
                    "content": "You are a helpful assistant working with transcriptions, translating and writing.",
                },
                {"role": "user", "content": filled_prompt},
            ],
            model=model or "gpt-4o",
            response_format={"type": "json_object"},
        )
    except Exception as exc:
        raise typer.Exit(code=1) from exc

    if not getattr(response, "choices", None):
        raise typer.Exit(code=1)

    message = response.choices[0].message.content
    if not message:
        raise typer.Exit(code=1)

    try:
        parsed = _parse_json_response(message)
    except Exception as exc:
        raise typer.Exit(code=1) from exc

    map_key = cache.make_key("map", rut_key, goc_key, model or "gpt-4o")
    cache.set(map_key, parsed)

    print(map_key)
