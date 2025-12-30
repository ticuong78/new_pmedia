import json
from typing import Any, Iterable, Optional

import typer

from src.cli.container import AppContainer
from src.domain.core.sentence import Sentence
from src.domain.core.stt_base import STTResponse

app = typer.Typer(help="Transcript mapping commands")

DEFAULT_PROMPT_TEMPLATE_2 = """Bạn được cung cấp hai tập dữ liệu:

1) **Phiên bản A** (gốc tiếng Trung), mỗi câu có:
- `id` (số nguyên, duy nhất)
- `sentence_start`
- `sentence_end`
- `sentence_form`

{goc}

2) **Phiên bản B** (tiếng Việt đã rewrite), mỗi câu có:
- `id` (số nguyên, duy nhất)
- `sentence_start`
- `sentence_end`
- `sentence_form`

{rut}

====================
## MỤC TIÊU
Tạo danh sách mapping 1–1 giữa B và A:
- Với **MỖI** câu B, chọn **CHÍNH XÁC 1** câu A có ngữ nghĩa/ý chính tương đương nhất.
- Ưu tiên match bằng **điểm neo (anchors)**.

====================
## RÀNG BUỘC 1–1 (CỰC QUAN TRỌNG)
- Mỗi câu B phải map tới đúng 1 câu A.
- Một câu A chỉ được dùng cho tối đa 1 câu B (không được nhiều B dùng chung 1 A).
- Mapping phải giữ thứ tự timeline:
  - Nếu `id_B(i) < id_B(j)` thì `id_A(i) < id_A(j)`.

Nếu hai câu B có nội dung gần nhau nhưng A chỉ có một câu “neo mạnh”:
- Câu B nào bám neo rõ hơn thì lấy câu A đó.
- Câu B còn lại phải chọn câu A kế cận có cùng chủ đề (dù neo yếu hơn) để tránh dùng chung.

====================
## ĐIỂM NEO (ANCHORS)
Điểm neo là các yếu tố định vị nội dung, ưu tiên:
1) Con số/định lượng: 12ms, 7.1, 125 giờ, bốn chế độ, v.v.
2) Tên sản phẩm/brand/model: 京韵 GX401 / GX401 / JINGHUIJX 401, v.v.
3) Công nghệ/thuật ngữ: FPS, Hi-Res, LDAC, Bluetooth, Light Speed, DH, ANC, mic kéo/rút, v.v.
4) Cụm tính năng đặc trưng: nghe tiếng bước chân/tiếng súng, đệm tai thoáng khí, bất đối xứng, đèn LED, pin, v.v.

Lưu ý:
- Anchor có thể xuất hiện bằng tiếng Việt trong B nhưng tiếng Trung trong A (ví dụ “mười hai mili giây” tương đương “十二毫秒”).
- Không cần khớp từng chữ; chỉ cần đúng ngữ cảnh/ý.

====================
## QUY TRÌNH CHỌN A CHO TỪNG B
Với mỗi câu B:
1) Trích anchors chính từ B (1–3 neo).
2) Tìm câu A có anchors tương ứng mạnh nhất.
3) Nếu câu A đã được dùng bởi câu B trước đó, bắt buộc chọn câu A khác (gần nhất và cùng chủ đề) để tránh trùng.
4) Nếu có nhiều câu A đều phù hợp, chọn câu A:
   - có neo rõ hơn,
   - và giúp toàn bộ mapping giữ thứ tự tăng dần, không bị “đảo”.

====================
## OUTPUT (BẮT BUỘC)
Chỉ trả về DUY NHẤT 1 JSON object, không markdown, không giải thích.

{
  "clarity": <number từ 0..1>,
  "mappings": [
    { "id_A": <number>, "id_B": <number> }
  ]
}

Yêu cầu thêm:
- `mappings` phải có đúng số phần tử bằng số câu trong B.
- `id_B` xuất hiện đúng 1 lần.
- `id_A` không được lặp lại.
- `mappings` phải được sắp xếp theo `id_B` tăng dần.

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
        help="Override OpenAI model id; defaults to gpt-5-mini-2025-08-07.",
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
            model=model or "gpt-5-mini-2025-08-07",
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

    map_key = cache.make_key("map", rut_key, goc_key, model or "gpt-5-mini-2025-08-07")
    cache.set(map_key, parsed)

    print(map_key)
