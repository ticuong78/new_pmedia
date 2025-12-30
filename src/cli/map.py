import json
from decimal import Decimal
from typing import Any, Dict, Iterable, List, Optional

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


def _to_decimal(x: Any) -> Decimal:
    """
    Convert to Decimal without rounding in formatting.
    We use Decimal(str(x)) so that 0.349 stays "0.349" (not "0.35").
    """
    if isinstance(x, Decimal):
        return x
    if x is None:
        raise ValueError("Cannot convert None to Decimal")
    return Decimal(str(x))


def _get_sentence_id(item: Any, fallback_id: int) -> int:
    # Support: Sentence may have id/index; dict may have id.
    if isinstance(item, Sentence):
        for attr in ("id", "index", "idx"):
            if hasattr(item, attr):
                val = getattr(item, attr)
                if val is not None:
                    return int(val)
        return fallback_id

    if isinstance(item, dict):
        for key in ("id", "sentence_id", "idx", "index"):
            if key in item and item[key] is not None:
                return int(item[key])
        return fallback_id

    return fallback_id


def _normalize_segments_with_id(value: Any) -> List[Dict[str, Any]]:
    """
    Normalize A/B to:
    [
      {"id": int, "sentence_start": Decimal, "sentence_end": Decimal, "sentence_form": str}
    ]
    """
    # If cached STTResponse is passed, it's not the segmented structure we need.
    if isinstance(value, STTResponse):
        raise typer.BadParameter(
            "This command requires segmented A/B with ids, not raw STTResponse."
        )

    # Common shape: {"sentences": [...]}
    if (
        isinstance(value, dict)
        and "sentences" in value
        and isinstance(value["sentences"], list)
    ):
        value = value["sentences"]

    if not isinstance(value, list) or not value:
        raise typer.BadParameter(
            "Expected a list of sentences (or dict with 'sentences')."
        )

    out: List[Dict[str, Any]] = []
    for i, item in enumerate(value, start=1):
        sid = _get_sentence_id(item, i)

        if isinstance(item, Sentence):
            start = _to_decimal(item.start)
            end = _to_decimal(item.end)
            form = str(item.sentence)
        elif isinstance(item, dict):
            # Support multiple key variants
            if "sentence_start" in item:
                start = _to_decimal(item["sentence_start"])
                end = _to_decimal(item["sentence_end"])
                form = str(item.get("sentence_form", item.get("text", "")))
            elif "start" in item and "end" in item:
                start = _to_decimal(item["start"])
                end = _to_decimal(item["end"])
                form = str(item.get("text", item.get("sentence_form", "")))
            else:
                raise typer.BadParameter(
                    f"Unsupported sentence dict shape: {item.keys()}"
                )
        else:
            raise typer.BadParameter(f"Unsupported sentence item type: {type(item)}")

        out.append(
            {
                "id": int(sid),
                "sentence_start": start,
                "sentence_end": end,
                "sentence_form": form,
            }
        )

    # Ensure unique ids
    ids = [x["id"] for x in out]
    if len(ids) != len(set(ids)):
        raise typer.BadParameter(
            "Detected duplicate ids in sentences. ids must be unique."
        )
    return out


def _index_by_id(items: List[Dict[str, Any]]) -> Dict[int, Dict[str, Any]]:
    return {int(x["id"]): x for x in items}


@app.command()
def build_c(
    map_key: str = typer.Option(
        ...,
        "--map-key",
        help="Cache key that stores mapping output (clarity + mappings).",
    ),
    rut_key: str = typer.Option(
        ...,
        "--rut-key",
        help="Cache key for B (Vietnamese) segmented sentences WITH ids.",
    ),
    goc_key: str = typer.Option(
        ..., "--goc-key", help="Cache key for A (Chinese) segmented sentences WITH ids."
    ),
    ctx: typer.Context = typer.Option(None, hidden=True),
):
    """
    Build version C segments by mapping each B to exactly one A:
      start_C = start_A
      end_C = start_C + duration_B + pause_padding
    where pause_padding comes from gaps in B.
    """
    if not isinstance(ctx.obj, AppContainer):
        raise typer.BadParameter("App container not initialized")

    cache = ctx.obj.cache

    mapping_obj = cache.get(map_key)
    if mapping_obj is None:
        raise typer.BadParameter(f"Cache key not found for map: {map_key}")

    rut_value = cache.get(rut_key)
    goc_value = cache.get(goc_key)
    if rut_value is None:
        raise typer.BadParameter(f"Cache key not found for rut: {rut_key}")
    if goc_value is None:
        raise typer.BadParameter(f"Cache key not found for goc: {goc_key}")

    # Normalize A/B to Decimal timeline
    a_items = _normalize_segments_with_id(goc_value)
    b_items = _normalize_segments_with_id(rut_value)

    a_by_id = _index_by_id(a_items)
    b_by_id = _index_by_id(b_items)

    # Parse mappings
    mappings = mapping_obj.get("mappings")
    if not isinstance(mappings, list) or not mappings:
        raise typer.BadParameter(
            "Mapping object must contain non-empty 'mappings' list."
        )

    # Validate 1-1 and sort by id_B
    seen_a = set()
    seen_b = set()
    mappings_sorted = sorted(mappings, key=lambda x: int(x["id_B"]))

    for m in mappings_sorted:
        if not isinstance(m, dict) or "id_A" not in m or "id_B" not in m:
            raise typer.BadParameter("Each mapping must be {id_A, id_B}.")
        ida = int(m["id_A"])
        idb = int(m["id_B"])
        if idb in seen_b:
            raise typer.BadParameter(f"Duplicate id_B in mappings: {idb}")
        seen_a.add(ida)
        seen_b.add(idb)
        if ida not in a_by_id:
            raise typer.BadParameter(f"Mapping refers to missing A id: {ida}")
        if idb not in b_by_id:
            raise typer.BadParameter(f"Mapping refers to missing B id: {idb}")

    pause_th = Decimal("0")
    include_b_gaps_as_pause = True
    clamp_to_next_start = True

    c_sentences: List[Dict[str, Any]] = []
    prev_end: Optional[Decimal] = None

    for i, m in enumerate(mappings_sorted):
        ida = int(m["id_A"])
        idb = int(m["id_B"])

        a = a_by_id[ida]
        b = b_by_id[idb]

        start_a: Decimal = a["sentence_start"]
        start_b: Decimal = b["sentence_start"]
        end_b: Decimal = b["sentence_end"]

        duration_b = end_b - start_b
        if duration_b <= Decimal("0"):
            raise typer.BadParameter(f"Invalid duration in B id={idb}: end <= start")

        # Base timing anchored to A
        start_c = start_a
        end_c = start_c + duration_b

        # Pause padding from B gaps
        if include_b_gaps_as_pause and i < len(mappings_sorted) - 1:
            next_idb = int(mappings_sorted[i + 1]["id_B"])
            next_b = b_by_id[next_idb]
            gap_b = next_b["sentence_start"] - end_b  # can be negative/zero/positive

            if gap_b >= pause_th and gap_b > Decimal("0"):
                end_c = end_c + gap_b

        # Clamp to next start_C to prevent overlap (recommended)
        if clamp_to_next_start and i < len(mappings_sorted) - 1:
            next_ida = int(mappings_sorted[i + 1]["id_A"])
            next_a = a_by_id[next_ida]
            next_start_c = next_a["sentence_start"]
            if end_c > next_start_c:
                end_c = next_start_c

        c_sentences.append(
            {
                "id_A": ida,
                "id_B": idb,
                "sentence_start": float(start_c),
                "sentence_end": float(end_c),
                "sentence_form": b["sentence_form"],
            }
        )
        prev_end = end_c

    result = {
        "source": {
            "map_key": map_key,
            "rut_key": rut_key,
            "goc_key": goc_key,
            "include_b_gaps_as_pause": bool(include_b_gaps_as_pause),
            "pause_threshold": format(pause_th, "f"),
            "clamp_to_next_start": bool(clamp_to_next_start),
        },
        "sentences": c_sentences,
    }

    out_key = cache.make_key(
        "c",
        map_key,
        rut_key,
        goc_key,
        "pause" if include_b_gaps_as_pause else "nopause",
    )
    cache.set(out_key, result)

    print(out_key)
