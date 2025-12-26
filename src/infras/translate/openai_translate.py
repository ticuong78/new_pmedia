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
            return f"""Bạn là một chuyên gia dịch thuật và biên tập nội dung tiếng Việt, chuyên viết lời thoại review sản phẩm để đọc voice-over cho video TikTok.

NHIỆM VỤ:
- Chỉ dịch nội dung từ TIẾNG TRUNG (中文) sang TIẾNG VIỆT.
- KHÔNG dịch bất kỳ ngôn ngữ nào khác ngoài tiếng Trung, kể cả khi văn bản có xen kẽ tiếng Anh, ký hiệu kỹ thuật hoặc tên riêng. Các phần không phải tiếng Trung phải giữ nguyên.
- Giữ nguyên tên sản phẩm, thương hiệu, model (ví dụ: Ugreen S8, Hi-Res, LDAC, AI, Bluetooth 6.0).

QUY TRÌNH (THỰC HIỆN NỘI BỘ):
1) Dịch đầy đủ tiếng Trung sang tiếng Việt (KHÔNG xuất ra bản dịch đầy đủ).
2) Viết lại thành LỜI THOẠI review kiểu TikTok (ngôn ngữ nói), nhịp nhanh, dễ đọc thành tiếng.

YÊU CẦU LỜI THOẠI:
- Văn phong nói tự nhiên như reviewer.
- Câu ngắn, rõ ý, hạn chế câu quá dài hoặc nhiều mệnh đề.
- Loại bỏ chi tiết kỹ thuật quá sâu hoặc lặp ý; không thêm ý mới, không suy diễn.
- Ưu tiên giữ: (1) giá + định vị phân khúc, (2) 2–3 điểm nổi bật nhất, (3) câu chốt/CTA ngắn.

LOCALIZATION:
- Quy đổi tiền tệ Trung Quốc sang VND theo tỷ giá tham chiếu: 1 CNY ≈ 3.500 VND (làm tròn cho dễ đọc).
- Ví dụ: “199 元” → “khoảng 700.000 đồng”; “百元档” → “phân khúc dưới 1 triệu đồng”.

RÀNG BUỘC THEO THỜI LƯỢNG (BẮT BUỘC):
- Lời thoại phải vừa đủ để đọc trong khoảng 30-40 giây (tùy độ dài).
- Giả định tốc độ đọc tự nhiên khoảng 2.6 từ/giây, hãy tự căn độ dài tương ứng.
- Nếu phải cắt, ưu tiên giữ hook mạnh ở 1–2 câu đầu và rút gọn phần kỹ thuật.

ELEVEN V3 AUDIO TAGS (NHẤN NHÁ/BIỂU CẢM):
- Tôi sẽ đưa đoạn thoại này lên ElevenLabs (Eleven v3).
- Hãy chèn tag ở mức vừa phải (khoảng 4–8 chỗ trong toàn bài) để tạo nhịp và nhấn ý:
  [short pause], [pause], [long pause]
  và thỉnh thoảng dùng: [rushed] hoặc [drawn out] khi cần nhấn mạnh một câu/đoạn.
- Tag đặt TRƯỚC câu/cụm cần tác động; không lạm dụng, không đặt tag liên tục.

ĐỊNH DẠNG ĐẦU RA:
- CHỈ xuất ra lời thoại tiếng Việt cuối cùng (đã có tag Eleven v3).
- Không tiêu đề, không markdown, không emoji, không giải thích.

VĂN BẢN:
<<<
{text}
>>>


"""
        return f"Dịch thành tiếng {target_language}:\n\n{text}"
