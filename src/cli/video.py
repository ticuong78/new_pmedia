import json
import re
import subprocess
import tempfile
import textwrap
import unicodedata
from pathlib import Path
from typing import Any, Literal

import typer

from src.cli.container import AppContainer
from src.domain.core.sentence import Sentence

# ----------------------------
# Config
# ----------------------------
MIN_LEN = 0.8

FONT = "Arial"  # dùng cho ASS + drawtext (nếu ffmpeg build có fontconfig)
FONT_SIZE = 40
FONT_COLOR = "white"

BOX_COLOR = "black@1"  # drawtext
BOX_BORDER = 20  # drawtext

WRAP_WIDTH = 50
LINE_SPACING = 10

# ASS styling
ASS_MARGIN_V = 500  # khoảng cách đáy
ASS_OUTLINE = 0
ASS_SHADOW = 0
ASS_BOX_ALPHA = 0  # 0=opaque, 255=transparent


# ----------------------------
# Process runner
# ----------------------------
def _run(cmd: list[str]) -> None:
    if cmd and cmd[0] == "ffmpeg":
        cmd = [cmd[0], "-hide_banner", "-loglevel", "error", *cmd[1:]]
    subprocess.run(cmd, check=True)


# ----------------------------
# Segment normalization
# ----------------------------
def _coerce_segment(segment: Any) -> dict[str, Any]:
    if isinstance(segment, Sentence):
        start, end, text = segment.start, segment.end, segment.sentence
    elif isinstance(segment, dict):
        start = segment.get("sentence_start") or segment.get("start")
        end = segment.get("sentence_end") or segment.get("end")
        text = (
            segment.get("sentence_form")
            or segment.get("text")
            or segment.get("sentence")
        )
    else:
        raise ValueError("Unsupported segment type")

    if start is None or end is None or text is None:
        raise ValueError("Segment missing start/end/text fields")

    start_f = float(start)
    end_f = float(end)
    if end_f <= start_f:
        end_f = start_f + MIN_LEN

    return {"start": start_f, "end": end_f, "text": str(text)}


def _normalize_segments(raw_segments: Any) -> list[dict[str, Any]]:
    if isinstance(raw_segments, str):
        raw_segments = json.loads(raw_segments)

    if isinstance(raw_segments, dict) and "sentences" in raw_segments:
        raw_segments = raw_segments["sentences"]

    if not isinstance(raw_segments, list):
        raise ValueError("Segments payload must be a list or contain a 'sentences' key")

    return [_coerce_segment(item) for item in raw_segments]


# ----------------------------
# Text cleaning + wrapping
# ----------------------------
def _is_bad_unicode(ch: str) -> bool:
    """
    Loại mọi ký tự thuộc nhóm Unicode 'C*' (control/format/surrogate/private/unassigned)
    vì chúng hay render thành □ trong drawtext/libass.
    Giữ lại newline '\n' để xuống dòng.
    """
    if ch == "\n":
        return False
    cat = unicodedata.category(ch)  # e.g. 'Cc', 'Cf', 'Zs', ...
    return cat.startswith("C")


def _sanitize_caption(s: str) -> str:
    s = unicodedata.normalize("NFC", s)

    # Chuẩn hoá newline
    s = s.replace("\r\n", "\n").replace("\r", "\n")
    s = s.replace("\u2028", "\n").replace("\u2029", "\n")  # line/para separators

    # Xoá BOM / zero-width phổ biến
    s = s.replace("\ufeff", "")
    s = s.replace("\u200b", "").replace("\u200c", "").replace("\u200d", "")

    # Loại toàn bộ ký tự nhóm C* (đây là chỗ fix "□" ở cuối dòng)
    s = "".join(ch for ch in s if not _is_bad_unicode(ch))

    # Chuẩn hoá khoảng trắng (giữ newline)
    s = re.sub(r"[ \t]+", " ", s)
    s = "\n".join(line.strip() for line in s.split("\n")).strip()

    return s


def _wrap_text(text: str, max_chars: int = WRAP_WIDTH) -> list[str]:
    # wrap theo word, không bẻ từ
    return textwrap.wrap(
        text,
        width=max_chars,
        break_long_words=False,
        break_on_hyphens=False,
    )


def _prepare_wrapped_text(raw: str) -> str:
    clean = _sanitize_caption(raw)
    lines = _wrap_text(clean, max_chars=WRAP_WIDTH)
    # tránh dòng rỗng do ký tự lạ
    lines = [ln.strip() for ln in lines if ln.strip()]
    return "\n".join(lines)


def _write_text_utf8_unix(path: Path, text: str) -> None:
    # ép newline '\n' để tránh rác Windows line ending
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


# ----------------------------
# Filter helpers (escape path in filtergraph)
# ----------------------------
def _escape_filter_path(p: Path) -> str:
    # escape cho filtergraph: \, :, '
    s = p.as_posix()
    return s.replace("\\", r"\\").replace(":", r"\:").replace("'", r"\'")


# ----------------------------
# Method 1: drawtext with textfile
# ----------------------------
def _drawtext_filter_from_file(text_path: Path) -> str:
    textfile = _escape_filter_path(text_path)
    return (
        f"drawtext=textfile='{textfile}':"
        f"font='{FONT}':"
        f"fontsize={FONT_SIZE}:"
        f"fontcolor={FONT_COLOR}:"
        f"box=1:boxcolor={BOX_COLOR}:boxborderw={BOX_BORDER}:"
        f"line_spacing={LINE_SPACING}:"
        f"x=(w-text_w)/2:"
        f"y=h-text_h-{ASS_MARGIN_V}"
    )


# ----------------------------
# Method 2: ASS + subtitles filter (ổn định Unicode nhất)
# ----------------------------
def _ass_color_bgr_hex(rgb: str, alpha: int = 0) -> str:
    """
    ASS màu dạng &HAABBGGRR
    - rgb: "white" hoặc "#RRGGBB" hoặc "black"
    - alpha: 0..255 (0 opaque, 255 transparent)
    """
    named = {"white": (255, 255, 255), "black": (0, 0, 0)}
    if rgb in named:
        r, g, b = named[rgb]
    elif rgb.startswith("#") and len(rgb) == 7:
        r = int(rgb[1:3], 16)
        g = int(rgb[3:5], 16)
        b = int(rgb[5:7], 16)
    else:
        # fallback: coi như white
        r, g, b = (255, 255, 255)

    return f"&H{alpha:02X}{b:02X}{g:02X}{r:02X}"


def _escape_ass_text(s: str) -> str:
    # ASS: \N xuống dòng, escape \ và { }
    s = s.replace("\\", r"\\")
    s = s.replace("{", r"\{").replace("}", r"\}")
    s = s.replace("\n", r"\N")
    return s


def _write_ass_file(path: Path, duration: float, text: str) -> None:
    """
    Tạo 1 ASS cho 1 đoạn part (từ 0 -> duration).
    Alignment=2 => bottom-center.
    BorderStyle=3 => hộp nền đặc.
    """
    primary = _ass_color_bgr_hex("white", alpha=0)
    back = _ass_color_bgr_hex("black", alpha=ASS_BOX_ALPHA)

    # format time h:mm:ss.cs (centiseconds)
    def fmt(t: float) -> str:
        if t < 0:
            t = 0
        cs = int(round(t * 100))
        s = cs // 100
        cs = cs % 100
        m = s // 60
        s = s % 60
        h = m // 60
        m = m % 60
        return f"{h}:{m:02d}:{s:02d}.{cs:02d}"

    start = fmt(0.0)
    end = fmt(duration)

    ass_text = _escape_ass_text(text)

    content = f"""[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{FONT},{FONT_SIZE},{primary},{primary},{primary},{back},0,0,0,0,100,100,0,0,3,{ASS_OUTLINE},{ASS_SHADOW},2,80,80,{ASS_MARGIN_V},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
Dialogue: 0,{start},{end},Default,,0,0,0,,{ass_text}
"""
    _write_text_utf8_unix(path, content)


def _subtitles_filter(ass_path: Path) -> str:
    # subtitles filter path escape
    p = _escape_filter_path(ass_path)
    return f"subtitles='{p}'"


# ----------------------------
# Rendering pipeline
# ----------------------------
def _render_parts(
    video_in: Path,
    segments: list[dict[str, Any]],
    tmp_dir: Path,
    method: Literal["ass", "drawtext"] = "ass",
) -> list[Path]:
    part_files: list[Path] = []

    for idx, seg in enumerate(segments):
        part = tmp_dir / f"part_{idx:03d}.mp4"
        duration = seg["end"] - seg["start"]

        wrapped_text = _prepare_wrapped_text(seg["text"])

        if method == "drawtext":
            txt_path = tmp_dir / f"caption_{idx:03d}.txt"
            _write_text_utf8_unix(txt_path, wrapped_text)
            vf = _drawtext_filter_from_file(txt_path)
        else:
            ass_path = tmp_dir / f"caption_{idx:03d}.ass"
            _write_ass_file(ass_path, duration, wrapped_text)
            vf = _subtitles_filter(ass_path)

        _run(
            [
                "ffmpeg",
                "-y",
                "-ss",
                str(seg["start"]),
                "-i",
                str(video_in),
                "-t",
                str(duration),
                "-vf",
                vf,
                "-an",
                "-c:v",
                "libx264",
                "-preset",
                "veryfast",
                part.as_posix(),
            ]
        )

        part_files.append(part)

    return part_files


def _concat_parts(part_files: list[Path], tmp_dir: Path) -> Path:
    concat_txt = tmp_dir / "concat.txt"
    concat_txt.write_text(
        "\n".join(f"file '{p.as_posix()}'" for p in part_files),
        encoding="utf-8",
    )

    merged_video = tmp_dir / "merged.mp4"
    _run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            concat_txt.as_posix(),
            "-c",
            "copy",
            merged_video.as_posix(),
        ]
    )
    return merged_video


def _mux_audio(merged_video: Path, audio_mp3: Path, video_out: Path) -> None:
    _run(
        [
            "ffmpeg",
            "-y",
            "-i",
            merged_video.as_posix(),
            "-i",
            audio_mp3.as_posix(),
            "-map",
            "0:v:0",
            "-map",
            "1:a:0",
            "-c:v",
            "copy",
            "-c:a",
            "aac",
            "-shortest",
            video_out.as_posix(),
        ]
    )


# ----------------------------
# Typer command
# ----------------------------
def render_video(
    map_key: str = typer.Argument(
        ..., help="Cache key returned by `map` (containing mapped sentences)."
    ),
    video_path: Path = typer.Option(
        ..., "--video", "-v", help="Source video file used for rendering captions."
    ),
    audio_mp3: Path | None = typer.Option(
        None,
        "--audio",
        "-a",
        help="Optional MP3 file to replace the video's audio track.",
    ),
    output: Path | None = typer.Option(
        None, "--output", "-o", help="Output path. Defaults to <video>_captioned.mp4"
    ),
    method: Literal["ass", "drawtext"] = typer.Option(
        "ass",
        "--method",
        help="Burn method: 'ass' (recommended, stable Unicode) or 'drawtext' (textfile).",
    ),
    ctx: typer.Context = typer.Option(None, hidden=True),
):
    """
    Render a captioned video from a cached map key.
    """
    if not isinstance(ctx.obj, AppContainer):
        raise typer.BadParameter("App container not initialized")

    cache = ctx.obj.cache
    cached_value = cache.get(map_key)
    if cached_value is None:
        raise typer.BadParameter(f"Cache key not found: {map_key}")

    try:
        segments = _normalize_segments(cached_value)
    except ValueError as exc:
        raise typer.BadParameter(str(exc))

    if not video_path.exists():
        raise typer.BadParameter(f"Video file not found: {video_path}")
    if audio_mp3 and not audio_mp3.exists():
        raise typer.BadParameter(f"Audio file not found: {audio_mp3}")

    video_out = output or video_path.with_stem(video_path.stem + "_captioned")
    video_out.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        parts = _render_parts(video_path, segments, tmp_dir, method=method)
        merged_video = _concat_parts(parts, tmp_dir)

        if audio_mp3:
            _mux_audio(merged_video, audio_mp3, video_out)
        else:
            merged_video.replace(video_out)

    result_key = cache.make_key("video", map_key, video_out.name)
    cache.set(
        result_key,
        {
            "map_key": map_key,
            "input": str(video_path),
            "output": str(video_out),
            "audio": str(audio_mp3) if audio_mp3 else None,
            "segments_count": len(segments),
            "method": method,
        },
    )
