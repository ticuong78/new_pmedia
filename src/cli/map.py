import json
from typing import Any, Iterable, Optional

import typer

from src.cli.container import AppContainer
from src.domain.core.sentence import Sentence
from src.domain.core.stt_base import STTResponse

app = typer.Typer(help="Transcript mapping commands")

DEFAULT_PROMPT_TEMPLATE_2 = """Bạn được cung cấp hai tập dữ liệu:

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
1) Với **MỖI** câu B, chọn **một câu hoặc một nhóm câu liên tiếp** trong A có **ý chính tương đương nhất** (ưu tiên “điểm neo”: giá tiền, tên sản phẩm, Hi-Res, LDAC, Bluetooth, thông số…).
2) Gán timestamp cho C theo A, và **BẢO TOÀN TOÀN BỘ khoảng nghỉ giữa các câu như trong B** (bao gồm cả micro-gap), để tránh tổng thời lượng sau khi ghép bị bị rút ngắn.

====================
## QUY TẮC GHÉP NỘI DUNG (A ↔ B)
- Không cần khớp từng chữ; chỉ cần đúng ngữ cảnh/ý chính.
- Một câu B có thể map tới nhiều câu A **liên tiếp**.
- Ưu tiên đoạn A có “điểm neo” rõ ràng để cắt ghép ổn định.

====================
## QUY TẮC TIMESTAMP (C) + BẢO TOÀN KHOẢNG NGHỈ (KHÔNG DÙNG NGƯỠNG)
Ký hiệu:
- `duration_B[i] = B[i].sentence_end - B[i].sentence_start`
- `gap_B[i] = B[i+1].sentence_start - B[i].sentence_end` (chỉ áp dụng với i < n-1)
- Định nghĩa khoảng nghỉ cần bảo toàn:
  - `pause_B[i] = max(0, gap_B[i])`
  - KHÔNG được đặt ngưỡng (ví dụ 0.30s) để loại bỏ micro-gap.
  - Mọi `pause_B[i] > 0` đều phải được giữ.

### 1) Chọn cụm A cho từng câu B
Với mỗi câu B[i], chọn 1 cụm A[i] (1 hoặc nhiều câu A liên tiếp) sao cho đúng ý nhất.
Ghi lại:
- `start_A[i] = sentence_start` của câu A đầu tiên trong cụm A[i]
- `end_A[i]   = sentence_end` của câu A cuối cùng trong cụm A[i]

### 2) Tính thời lượng thoại tương ứng cho C
- `start_C[i] = start_A[i]`
- `talk_end_C[i] = start_C[i] + duration_B[i]`

Ràng buộc phạm vi A:
- `talk_end_C[i]` KHÔNG được vượt `end_A[i]`.
- Nếu `talk_end_C[i] > end_A[i]`:
  - Ưu tiên mở rộng cụm A[i] (thêm các câu A kế tiếp, vẫn liên tiếp) để `end_A[i]` đủ bao phủ `talk_end_C[i]`.
  - Nếu không thể mở rộng hợp lý, kẹp:
    - `talk_end_C[i] = end_A[i]`

### 3) BẢO TOÀN KHOẢNG NGHỈ: đẩy start câu sau (ưu tiên), không “xóa gap”
Mục tiêu: khoảng cách giữa hai caption trong C phải bằng khoảng cách tương ứng trong B:
- Với i < n-1, yêu cầu:
  - `start_C[i+1] >= talk_end_C[i] + pause_B[i]`

Cách thực hiện:
- Bước A (ưu tiên): khi chọn cụm A cho câu B[i+1], hãy chọn cụm A bắt đầu muộn hơn sao cho thỏa:
  - `start_A[i+1] >= talk_end_C[i] + pause_B[i]`
  Khi đó `start_C[i+1] = start_A[i+1]` và khoảng nghỉ được giữ.

- Bước B (chỉ khi bắt buộc): nếu không có cụm A nào phù hợp để bắt đầu muộn hơn mà vẫn đúng ngữ nghĩa,
  thì cho phép “kẹp khoảng nghỉ” để không overlap:
  - `start_C[i+1] = max(start_A[i+1], talk_end_C[i])`
  (Lưu ý: Bước B sẽ làm mất một phần pause. Chỉ dùng khi không thể chọn cụm A khác hợp lý.)

### 4) Xác định `sentence_end` cho C
Để thể hiện “khoảng nghỉ ở cuối câu trước” trong chính câu trước, đặt:
- Nếu i < n-1:
  - `sentence_end_C[i] = min(talk_end_C[i] + pause_B[i], start_C[i+1])`
- Nếu i = n-1:
  - `sentence_end_C[i] = talk_end_C[i]`

Giải thích ngắn gọn bằng quy tắc:
- Câu i kết thúc sau phần thoại + phần nghỉ (pause) của nó,
- nhưng không bao giờ được vượt qua `start` của câu kế tiếp.

### 5) Ràng buộc “KHÔNG OVERLAP”
Bắt buộc:
- `sentence_start_C[i+1] >= sentence_end_C[i]`
Nếu vi phạm, phải quay lại bước chọn cụm A hoặc áp dụng kẹp theo Bước B ở trên.

====================
## ĐỊNH DẠNG ĐẦU RA (BẮT BUỘC)
Chỉ trả về DUY NHẤT 1 JSON object, có đúng 1 key ngoài cùng là `"sentences"`.
Không giải thích thêm, không markdown ngoài JSON.

{
  "sentences": [
    {
      "sentence_start": <number>,
      "sentence_end": <number>,
      "sentence_form": "<giữ nguyên sentence_form từ B>"
    }
  ]
}

LƯU Ý CHO CÂU CUỐI (BẮT BUỘC):

Sau khi hoàn tất việc map toàn bộ câu và sinh xong phiên bản C,
hãy so sánh tổng thời lượng thoại của B và C như sau:

- total_duration_B
  = tổng ( B[i].sentence_end - B[i].sentence_start ) với mọi câu i trong B

- total_duration_C
  = tổng ( C[i].sentence_end - C[i].sentence_start ) với mọi câu i trong C

Nếu total_duration_B > total_duration_C
(thể hiện phiên bản C bị hụt thời lượng so với B),
thì bù phần thời lượng còn thiếu bằng cách:

sentence_end_C[last]
  = sentence_end_C[last]
  + ( total_duration_B - total_duration_C )

Ràng buộc bắt buộc:
- Chỉ được phép cập nhật `sentence_end` của câu C cuối cùng.
- Không được thay đổi `sentence_start` của bất kỳ câu nào.
- Không phân bổ phần thời lượng bị hụt sang các câu khác.
- Không được thay đổi nội dung `sentence_form`.

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
