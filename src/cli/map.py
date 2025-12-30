import json
from decimal import Decimal
from typing import Any, Dict, Iterable, List, Optional

import typer

from src.cli.container import AppContainer
from src.domain.core.sentence import Sentence
from src.domain.core.stt_base import STTResponse

app = typer.Typer(help="Transcript mapping commands")

# ### 2) Tính pause cần đệm (pause_padding)
# - Nếu i < n-1:
#   - `pause_padding[i] = gap_B[i]` nếu `gap_B[i] >= PAUSE_THRESHOLD`
#   - ngược lại `pause_padding[i] = 0`
# - Nếu i = n-1: `pause_padding[i] = 0`


# ### 5) Ràng buộc "KHÔNG OVERLAP" giữa các câu C theo thứ tự B
# Yêu cầu: với mọi i < n-1 phải có:
# - `start_C[i+1] >= end_C[i]`
# Cách xử lý khi có nguy cơ overlap:
# - Bước A (ưu tiên): khi chọn cụm A cho B[i+1], hãy chọn một cụm A **bắt đầu muộn hơn** sao cho:
#   - `start_C[i+1] >= proposed_end_C[i]`
#   (tức là tránh overlap bằng cách chọn start_A khác phù hợp hơn cho câu sau)
# - Nếu không thể chọn cụm A khác hợp lý, thì Bước B (bắt buộc):
#   - **kẹp end câu trước** để không overlap:
#     - `end_C[i] = min(proposed_end_C[i], start_C[i+1])`
#   - Nếu kẹp khiến câu quá ngắn vô lý, hãy quay lại và **chọn lại cụm A** (ưu tiên có điểm neo) cho một trong hai câu.

# ### 4) Ràng buộc "không tạo timestamp ngoài phạm vi A"
# Bạn KHÔNG được bịa thời gian vượt quá dữ liệu A đã chọn:
# - Nếu `proposed_end_C[i]` vượt quá `end_A_of_group[i]` thì:
#   - Ưu tiên **mở rộng group A** (thêm các câu A kế tiếp, vẫn phải liên tiếp) để `end_A_of_group[i]` đủ bao phủ `proposed_end_C[i]`.
#   - Nếu không thể mở rộng hợp lý, thì **kẹp lại**:
#     - `proposed_end_C[i] = end_A_of_group[i]`
#   (tức là: cố giữ pause, nhưng không vượt biên A)

# ### 6) Giá trị cuối cùng
# - `end_C[i]` là giá trị sau khi đã:
#   - cộng pause (nếu có),
#   - mở rộng group A (nếu cần),
#   - và kẹp để tránh overlap (nếu bắt buộc).

DEFAULT_PROMPT_TEMPLATE_2 = """
Bạn được cung cấp hai tập dữ liệu:

1) **Phiên bản A** (gốc tiếng Trung), mỗi câu có:
- `sentence_start`
- `sentence_end`
- `sentence_form`

{goc}

2) **Phiên bản B** (dịch + rút gọn tiếng Việt), mỗi câu có:
- `sentence_start`
- `sentence_end`
- `sentence_form`

{rut}

====================
## MỤC TIÊU
Tạo **phiên bản C** bằng cách:
1) Với **MỖI** câu B, chọn **một câu** trong A có **ý chính tương đương nhất** (ưu tiên có “điểm neo”: giá tiền, tên sản phẩm, Hi-Res, LDAC, Bluetooth, thông số..., các điểm neo này phải là Tiếng Việt nhé ngoại trừ tên sản phẩm bằng Tiếng Anh).
2) Gán timestamp cho C theo A, nhưng **có “đệm khoảng nghỉ (pause)” ở CUỐI câu trước** nếu B thể hiện có khoảng nghỉ.

====================
## QUY TẮC GHÉP NỘI DUNG (A với B)
- Không cần khớp từng chữ, chỉ cần đúng ngữ cảnh/ý chính.
- Một câu B có thể map tới nhiều câu A **liên tiếp** nhưng chỉ lấy câu đầu tiên và các câu còn lại thì để cho lần sau.
- Không tái sử dụng A: mỗi câu A chỉ được ghép tối đa 1 lần. Mapping phải đi từ trái sang phải theo
- Ưu tiên đoạn A có "điểm neo" dễ nhận biết để cắt ghép ổn định.

====================
## QUY TẮC TIMESTAMP (C) + ĐỆM KHOẢNG NGHỈ
Ký hiệu:
- `duration_B[i] = B[i].sentence_end - B[i].sentence_start`
- `gap_B[i] = B[i+1].sentence_start - B[i].sentence_end` (chỉ áp dụng với i < n-1)

### 1) Tính start/end cơ bản cho từng câu C
Với mỗi câu B[i], sau khi chọn được A tương ứng:
- `start_C[i] = start_A[i]`  (lấy đúng `sentence_start` của câu A đầu tiên tìm được)
- `base_end_C[i] = start_C[i] + duration_B[i]`

### 2) End có đệm pause (tạm tính)
- `proposed_end_C[i] = base_end_C[i] + pause_padding[i]`

### 3) Xử lý overlap
Với hai đoạn bất kỳ i và j, nếu `start_C[i] == start_C[j]` thì có thể:
- `start_C[j] = proposed_end_C[i]` (proposed_end_C đã đệm pause padding nhé)

Với hai đoạn bất kỳ i và j, nếu `start_C[i] < start_C[j]` thì có thể:
- `start_C[j] = proposed_end_C[i]` (proposed_end_C đã đệm pause padding nhé) 

====================
## ĐỊNH DẠNG ĐẦU RA (BẮT BUỘC)
Chỉ trả về DUY NHẤT 1 JSON object, có đúng 1 key ngoài cùng là `"sentences"`.
Không giải thích thêm, không markdown ngoài JSON.

{
  "confidence": <phần trăm độ tự tin về độ chính xác kết quả đầu ra>,
  "sentences": [
    {
      "sentence_start": <number>,
      "sentence_end": <number>,
      "sentence_form": "<giữ nguyên sentence_form từ B>"
    }
  ]
}

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
