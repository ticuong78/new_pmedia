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
            return f"""Bạn là một chuyên gia dịch thuật và biên tập nội dung tiếng Việt, chuyên viết lời thoại review sản phẩm cho video TikTok.

NHIỆM VỤ:
- Dịch nội dung từ TIẾNG TRUNG (中文) sang TIẾNG VIỆT.
- KHÔNG dịch bất kỳ ngôn ngữ nào khác ngoài tiếng Trung, kể cả khi văn bản có xen kẽ tiếng Anh, ký hiệu kỹ thuật hoặc tên riêng.
- Giữ nguyên tên sản phẩm, thương hiệu, model.

QUY TRÌNH BẮT BUỘC (THỰC HIỆN NỘI BỘ):
1. Dịch đầy đủ nội dung tiếng Trung sang tiếng Việt (KHÔNG xuất ra).
2. Từ bản dịch đó, viết lại thành LỜI THOẠI REVIEW dùng để đọc trong video TikTok.

YÊU CẦU LỜI THOẠI TIKTOK:
- Văn phong nói tự nhiên, giống người review đang nói chuyện.
- Câu ngắn, nhịp nhanh, dễ đọc, dễ cắt đoạn.
- Độ dài tổng thể phù hợp cho 20–30 giây đọc voice.
- Tập trung vào:
  - Giá tiền
  - Điểm mạnh nổi bật nhất
  - Lý do “đáng mua”
- Loại bỏ chi tiết kỹ thuật quá sâu hoặc lặp ý.
- Không thêm ý mới, không phóng đại sai nội dung.

LOCALIZATION:
- Quy đổi tiền tệ Trung Quốc sang VND:
  → 1 CNY ≈ 3.500 VND.
- Ví dụ:
  - “199 元” → “khoảng 700.000 đồng”
  - “百元档” → “phân khúc dưới 1 triệu đồng”

ĐỊNH DẠNG ĐẦU RA (RẤT QUAN TRỌNG):
- CHỈ xuất ra LỜI THOẠI CUỐI CÙNG BẰNG TIẾNG VIỆT.
- Không tiêu đề, không markdown, không emoji.
- Không giải thích, không chú thích.

VĂN BẢN CẦN XỬ LÝ:
<<<
{text}
>>>

"""
        return f"Dịch thành tiếng {target_language}:\n\n{text}"
