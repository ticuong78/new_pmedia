from typing import Iterable, List, Optional

from openai import OpenAI

from src.domain.core.translator import Translator


class OpenAITranslator(Translator):
    """Translate text using OpenAI chat completions."""

    def __init__(self, client: OpenAI, model: str = "gpt-5-mini-2025-08-07") -> None:
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

    # - Hãy chèn tag ở mức vừa phải (khoảng 4–8 chỗ trong toàn bài) để tạo nhịp và nhấn ý:
    #   [short pause], [pause], [long pause]
    #   và thỉnh thoảng dùng: [rushed] hoặc [drawn out] khi cần nhấn mạnh một câu/đoạn.

    def _build_prompt(
        self, text: str, target_language: str, source_language: Optional[str]
    ) -> str:
        if source_language:
            return f"""Bạn là một chuyên gia dịch thuật và biên tập nội dung tiếng Việt, chuyên viết lời thoại review sản phẩm để đọc voice-over cho video TikTok.

MỤC TIÊU:
- Đây là nhiệm vụ **VIẾT LẠI NGẮN HƠN (REWRITE/COMPRESS)** dựa trên nội dung gốc, KHÔNG phải “tóm tắt”.
- Bạn có thể **lược bớt các câu quảng cáo thuần** (không có thông tin định vị / không có điểm neo), nhưng phải giữ đầy đủ các thông tin quan trọng và các “điểm neo” để nội dung vẫn đúng và dễ ghép.

NHIỆM VỤ:
- Chỉ dịch nội dung từ TIẾNG TRUNG (中文) sang TIẾNG VIỆT.
- KHÔNG dịch bất kỳ ngôn ngữ nào khác ngoài tiếng Trung, kể cả khi văn bản có xen kẽ tiếng Anh, ký hiệu kỹ thuật hoặc tên riêng. Các phần không phải tiếng Trung phải giữ nguyên.
- Giữ nguyên tên sản phẩm, thương hiệu, model, thuật ngữ kỹ thuật (ví dụ: Ugreen S8, Hi-Res, LDAC, AI, Bluetooth 6.0).

ĐIỂM NEO (ANCHORS) — PHẢI ƯU TIÊN GIỮ:
“Điểm neo” là các yếu tố định vị nội dung, gồm:
1) Con số/định lượng/giá tiền/phân khúc: 199 元, 百元档, 六麦克风, 6.0, 千元档, v.v.
2) Tên riêng/tên sản phẩm/brand/model: 绿联 / Ugreen / S8, v.v.
3) Chuẩn/công nghệ/codec: Hi-Res, LDAC, Bluetooth 6.0, 主动降噪, v.v.
4) Tính năng cụ thể dạng danh từ: AI 小助手, 通话记录, 会议纪要, 同声传译, 空间音效, v.v.

QUY TRÌNH (THỰC HIỆN NỘI BỘ):
1) Dịch đầy đủ tiếng Trung sang tiếng Việt (KHÔNG xuất ra bản dịch đầy đủ).
2) Trích các “điểm neo” quan trọng xuất hiện trong văn bản (nội bộ).
3) Viết lại thành lời thoại TikTok (ngôn ngữ nói) theo nguyên tắc:
   - Mỗi câu/cụm câu xoay quanh 1–2 điểm neo chính.
   - Cắt bớt từ đệm, gộp mệnh đề tương đương, đổi cấu trúc cho gọn.
   - KHÔNG thêm ý mới, KHÔNG suy diễn.
   - KHÔNG làm sai nghĩa các điểm neo (không đổi thông số/codec/phiên bản).

QUY TẮC “ANCHOR-FOCUSED” (CHO PHÉP LƯỢC BỚT QUẢNG CÁO THUẦN):
- Ưu tiên giữ tất cả câu/cụm có chứa điểm neo hoặc có thông tin định vị rõ ràng.
- Các câu chỉ mang tính quảng cáo/hô hào/chung chung mà KHÔNG có điểm neo và KHÔNG thêm thông tin định vị cụ thể được phép:
  (a) lược bỏ, hoặc
  (b) gộp thành 1 câu HOOK ngắn ở đầu, hoặc 1 câu CTA ngắn ở cuối.
- Tổng cộng tối đa 2 câu “marketing”: 1 HOOK đầu + 1 CTA cuối. Không rải quảng cáo ở giữa.
- Các câu “định vị đối tượng/phân khúc” (ví dụ: học sinh sinh viên mua được, tầm giá này quá hời, phân khúc dưới 1 triệu) dù không có số vẫn nên giữ (vì là thông tin định vị).

LOCALIZATION:
- Quy đổi tiền tệ Trung Quốc sang VND theo tỷ giá tham chiếu: 1 CNY ≈ 3.500 VND (làm tròn cho dễ đọc).
- Ví dụ: “199 元” → “khoảng 700.000 đồng”; “百元档” → “phân khúc dưới 1 triệu đồng”.

YÊU CẦU LỜI THOẠI:
- Văn phong nói tự nhiên như reviewer, nhịp nhanh, dễ đọc thành tiếng.
- Câu ngắn, rõ ý; nếu một câu quá dài vì nhiều điểm neo thì tách ra 2 câu.
- Không lặp ý; hạn chế kỹ thuật quá sâu, nhưng KHÔNG được bỏ các điểm neo quan trọng.
- Nếu có nhiều tính năng, ưu tiên giữ theo thứ tự: (1) giá/phân khúc, (2) công nghệ/codec/điểm neo kỹ thuật, (3) lợi ích trải nghiệm, (4) AI/tiện ích, (5) kết/CTA.

RÀNG BUỘC THEO THỜI LƯỢNG:
- Lời thoại mục tiêu đọc trong khoảng 35–45 giây.
- Giả định tốc độ đọc tự nhiên khoảng 2.6 từ/giây.
- Nếu cần rút gọn thêm: chỉ được cắt từ đệm/đoạn lặp/quảng cáo thuần; KHÔNG được bỏ điểm neo quan trọng.

ELEVEN V3 AUDIO TAGS:
- Tôi sẽ đưa đoạn thoại này lên ElevenLabs (Eleven v3).
- Tag đặt TRƯỚC câu/cụm cần tác động; không lạm dụng, không đặt tag liên tục.

ĐỊNH DẠNG ĐẦU RA:
- CHỈ xuất ra lời thoại tiếng Việt cuối cùng (đã có tag Eleven v3 nếu cần).
- Không tiêu đề, không markdown, không emoji, không giải thích.

VĂN BẢN:
<<<
{text}
>>>

"""
        return f"Dịch thành tiếng {target_language}:\n\n{text}"
