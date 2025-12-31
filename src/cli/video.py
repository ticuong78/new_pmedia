import json
import re
import subprocess
import tempfile
import textwrap
import unicodedata
from pathlib import Path
from typing import Any, Literal, Optional

import typer

from src.cli.container import AppContainer
from src.domain.core.sentence import Sentence

# ----------------------------
# Config
# ----------------------------
MIN_LEN = 0.8

BOX_COLOR = "black@1"  # drawtext
BOX_BORDER = 20  # drawtext

FONT = "Arial"
FONT_SIZE = 70
FONT_COLOR = "white"

WRAP_WIDTH = 55
LINE_SPACING = 18

CAPTION_BASE_OFFSET = 86  # base lift for single-line captions
CAPTION_PER_LINE_OFFSET = 9  # extra lift per additional wrapped line

CAPTION_BOX_H_DEFAULT = 260
CAPTION_BOX_PAD_BOTTOM_DEFAULT = 0

ASS_MARGIN_V = 340
ASS_OUTLINE = 0
ASS_SHADOW = 0
ASS_BOX_ALPHA = 0  # nền đen đặc
TEXT_Y_BIAS = 1375  # số âm = đẩy lên (px theo PlayResY)
TEXT_Y_BIAS_PER_EXTRA_LINE = -6  # mỗi dòng thêm (từ dòng 2 trở đi) đẩy lên thêm chút

# Active box metrics used to align ASS text relative to the caption box center.
_ACTIVE_CAPTION_BOX_H = CAPTION_BOX_H_DEFAULT
_ACTIVE_CAPTION_BOX_PAD_BOTTOM = CAPTION_BOX_PAD_BOTTOM_DEFAULT


# ----------------------------
# Utils
# ----------------------------
def _run(cmd: list[str]) -> None:
    if cmd and cmd[0] == "ffmpeg":
        cmd = [cmd[0], "-hide_banner", "-loglevel", "error", *cmd[1:]]
    subprocess.run(cmd, check=True)


# ----------------------------
# Caption vertical offset logic
# ----------------------------
def _caption_vertical_offset(line_count: int) -> int:
    if line_count <= 0:
        return 0

    extra_lines = max(0, line_count - 1)
    return CAPTION_BASE_OFFSET + extra_lines * CAPTION_PER_LINE_OFFSET


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
        raise ValueError("Segment missing start/end/text")

    start_f = float(start)
    end_f = float(end)
    if end_f <= start_f:
        end_f = start_f + MIN_LEN

    return {"start": start_f, "end": end_f, "text": str(text)}


def _normalize_segments(raw: Any) -> list[dict[str, Any]]:
    if isinstance(raw, str):
        raw = json.loads(raw)

    if isinstance(raw, dict) and "sentences" in raw:
        raw = raw["sentences"]

    if not isinstance(raw, list):
        raise ValueError("Segments must be a list")

    return [_coerce_segment(x) for x in raw]


# ----------------------------
# Text cleaning + wrapping
# ----------------------------
def _is_bad_unicode(ch: str) -> bool:
    if ch == "\n":
        return False
    return unicodedata.category(ch).startswith("C")


def _sanitize_caption(s: str) -> str:
    s = unicodedata.normalize("NFC", s)
    s = s.replace("\r\n", "\n").replace("\r", "\n")
    s = s.replace("\u2028", "\n").replace("\u2029", "\n")
    s = (
        s.replace("\ufeff", "")
        .replace("\u200b", "")
        .replace("\u200c", "")
        .replace("\u200d", "")
    )
    s = "".join(ch for ch in s if not _is_bad_unicode(ch))
    s = re.sub(r"[ \t]+", " ", s)
    s = "\n".join(line.strip() for line in s.split("\n")).strip()
    return s


def _wrap_text(text: str, width: int) -> list[str]:
    return textwrap.wrap(
        text, width=width, break_long_words=False, break_on_hyphens=False
    )


def _prepare_wrapped_text(raw: str) -> tuple[str, int]:
    clean = _sanitize_caption(raw)
    lines = _wrap_text(clean, WRAP_WIDTH)
    lines = [ln for ln in lines if ln.strip()]
    text = "\n".join(lines)
    return text, max(1, len(lines))


def _write_text_utf8(path: Path, text: str) -> None:
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


# ----------------------------
# Filter helpers
# ----------------------------
def _escape_filter_path(p: Path) -> str:
    return p.as_posix().replace("\\", r"\\").replace(":", r"\:").replace("'", r"\'")


# ----------------------------
# drawtext
# ----------------------------
def _drawtext_filter_from_file(text_path: Path, line_count: int) -> str:
    offset = _caption_vertical_offset(line_count)
    margin_v = ASS_MARGIN_V + offset
    textfile = _escape_filter_path(text_path)

    return (
        f"drawtext=textfile='{textfile}':"
        f"font='{FONT}':"
        f"fontsize={FONT_SIZE}:"
        f"fontcolor={FONT_COLOR}:"
        f"box=1:boxcolor={BOX_COLOR}:boxborderw={BOX_BORDER}:"
        f"line_spacing={LINE_SPACING}:"
        f"x=(w-text_w)/2:"
        f"y=h-text_h-{margin_v}"
    )


# ----------------------------
# ASS subtitles
# ----------------------------
def _ass_color(rgb: str, alpha: int = 0) -> str:
    named = {"white": (255, 255, 255), "black": (0, 0, 0)}
    if rgb in named:
        r, g, b = named[rgb]
    else:
        r, g, b = (255, 255, 255)
    return f"&H{alpha:02X}{b:02X}{g:02X}{r:02X}"


def _escape_ass_text(s: str) -> str:
    return (
        s.replace("\\", r"\\")
        .replace("{", r"\{")
        .replace("}", r"\}")
        .replace("\n", r"\N")
    )


def _write_ass_file(path: Path, duration: float, text: str, line_count: int) -> None:
    offset = _caption_vertical_offset(line_count)
    margin_v = ASS_MARGIN_V + offset

    primary = _ass_color("white", 0)
    back = _ass_color("black", ASS_BOX_ALPHA)

    def fmt(t: float) -> str:
        cs = int(round(max(t, 0) * 100))
        s = cs // 100
        cs %= 100
        m, s = divmod(s, 60)
        h, m = divmod(m, 60)
        return f"{h}:{m:02d}:{s:02d}.{cs:02d}"

    ass_text = _escape_ass_text(text)

    # Compute center of the caption box (assuming PlayResX=1080, PlayResY=1920).
    box_h = _ACTIVE_CAPTION_BOX_H or CAPTION_BOX_H_DEFAULT
    box_pad_bottom = _ACTIVE_CAPTION_BOX_PAD_BOTTOM or 0
    center_x = 540
    center_y = int(1920 - margin_v - (box_h / 2) + box_pad_bottom)

    # Bias upward based on wrapped line count.
    extra_lines = max(0, line_count - 1)
    center_y += TEXT_Y_BIAS + extra_lines * TEXT_Y_BIAS_PER_EXTRA_LINE

    # Force text to anchor at the center position.
    ass_text = f"{{\\an5\\pos({center_x},{center_y})}}{ass_text}"

    content = f"""[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{FONT},{FONT_SIZE},{primary},{primary},{primary},{back},0,0,0,0,100,100,0,0,1,{ASS_OUTLINE},{ASS_SHADOW},5,80,80,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
Dialogue: 0,{fmt(0)},{fmt(duration)},Default,,0,0,0,,{ass_text}
"""
    _write_text_utf8(path, content)


def _subtitles_filter(path: Path) -> str:
    return f"subtitles='{_escape_filter_path(path)}'"


# ----------------------------
# Rendering
# ----------------------------
def _render_parts(
    video_in: Path,
    segments: list[dict[str, Any]],
    tmp_dir: Path,
    method: Literal["ass", "drawtext"],
    box_filter: Optional[str],
) -> list[Path]:
    outputs: list[Path] = []

    for i, seg in enumerate(segments):
        part = tmp_dir / f"part_{i:03d}.mp4"
        duration = seg["end"] - seg["start"]

        wrapped_text, line_count = _prepare_wrapped_text(seg["text"])

        if method == "drawtext":
            txt = tmp_dir / f"cap_{i:03d}.txt"
            _write_text_utf8(txt, wrapped_text)
            vf_text = _drawtext_filter_from_file(txt, line_count)
            vf = f"{box_filter},{vf_text}" if box_filter else vf_text
        else:
            ass = tmp_dir / f"cap_{i:03d}.ass"
            _write_ass_file(ass, duration, wrapped_text, line_count)
            vf_sub = _subtitles_filter(ass)
            vf = f"{box_filter},{vf_sub}" if box_filter else vf_sub

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

        outputs.append(part)

    return outputs


def _concat(parts: list[Path], tmp_dir: Path) -> Path:
    txt = tmp_dir / "concat.txt"
    txt.write_text("\n".join(f"file '{p.as_posix()}'" for p in parts), encoding="utf-8")

    out = tmp_dir / "merged.mp4"
    _run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            txt.as_posix(),
            "-c",
            "copy",
            out.as_posix(),
        ]
    )
    return out


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
            video_out.as_posix(),
        ]
    )


# ----------------------------
# Standalone box overlay helper
# ----------------------------
def add_box_overlay(
    video_in: Path,
    video_out: Path,
    box_h: int = 260,
    alpha: float = 0.75,
    box_width: Optional[int] = None,
    align: Literal["left", "center", "right"] = "center",
    margin_bottom: int = 0,
) -> None:
    """Overlay a translucent box at the bottom of a video."""
    vf = _build_box_filter(
        box_h=box_h,
        alpha=alpha,
        box_width=box_width,
        align=align,
        margin_bottom=margin_bottom,
    )
    _run(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(video_in),
            "-vf",
            vf,
            "-c:a",
            "copy",
            str(video_out),
        ]
    )


def _build_box_filter(
    *,
    box_h: int,
    alpha: float,
    box_width: Optional[int],
    align: Literal["left", "center", "right"],
    margin_bottom: int,
) -> str:
    w_expr = "iw" if box_width is None else str(max(1, box_width))
    if align == "center":
        x_expr = f"(iw-{w_expr})/2"
    elif align == "right":
        x_expr = f"iw-{w_expr}"
    else:
        x_expr = "0"

    y_expr = f"h-{margin_bottom}-{box_h}"

    return (
        f"drawbox=x={x_expr}:"
        f"y={y_expr}:"
        f"w={w_expr}:h={box_h}:"
        f"color=black@{alpha}:"
        f"t=fill"
    )


# ----------------------------
# Typer command
# ----------------------------
def render_video(
    map_key: str = typer.Argument(...),
    video_path: Path = typer.Option(..., "--video", "-v"),
    audio_mp3: Path | None = typer.Option(None, "--audio", "-a"),
    output: Path | None = typer.Option(None, "--output", "-o"),
    method: Literal["ass", "drawtext"] = typer.Option("ass"),
    caption_box: bool = typer.Option(
        False,
        "--caption-box/--no-caption-box",
        help="Add a translucent box beneath the captions after rendering",
    ),
    caption_box_height: int = typer.Option(
        260, "--caption-box-height", help="Height of the caption box (pixels)"
    ),
    caption_box_alpha: float = typer.Option(
        0.75, "--caption-box-alpha", help="Opacity of the caption box (0-1)"
    ),
    caption_box_width: Optional[int] = typer.Option(
        None,
        "--caption-box-width",
        help="Width of the caption box in pixels (default: full width)",
    ),
    caption_box_align: Literal["left", "center", "right"] = typer.Option(
        "center",
        "--caption-box-align",
        help="Horizontal alignment for the caption box when width is set",
    ),
    caption_box_margin_bottom: Optional[int] = typer.Option(
        None,
        "--caption-box-margin-bottom",
        help="Bottom margin (pixels) for the caption box position; default auto-aligns with captions",
    ),
    ctx: typer.Context = typer.Option(None, hidden=True),
):
    if not isinstance(ctx.obj, AppContainer):
        raise typer.BadParameter("App container not initialized")

    cache = ctx.obj.cache
    data = cache.get(map_key)
    if data is None:
        raise typer.BadParameter("Cache key not found")

    segments = _normalize_segments(data)
    # Estimate max line count to align box near the caption area when auto margin is used.
    max_lines = 1
    for seg in segments:
        _, lines = _prepare_wrapped_text(seg["text"])
        max_lines = max(max_lines, lines)

    global _ACTIVE_CAPTION_BOX_H, _ACTIVE_CAPTION_BOX_PAD_BOTTOM
    _ACTIVE_CAPTION_BOX_H = CAPTION_BOX_H_DEFAULT
    _ACTIVE_CAPTION_BOX_PAD_BOTTOM = CAPTION_BOX_PAD_BOTTOM_DEFAULT

    out = output or video_path.with_stem(video_path.stem + "_captioned")
    box_filter = None
    if caption_box:
        auto_margin = max(0, ASS_MARGIN_V + _caption_vertical_offset(max_lines) - 40)
        margin_bottom = (
            caption_box_margin_bottom
            if caption_box_margin_bottom is not None
            else auto_margin
        )
        _ACTIVE_CAPTION_BOX_H = caption_box_height
        _ACTIVE_CAPTION_BOX_PAD_BOTTOM = caption_box_margin_bottom or 0
        box_filter = _build_box_filter(
            box_h=caption_box_height,
            alpha=caption_box_alpha,
            box_width=caption_box_width,
            align=caption_box_align,
            margin_bottom=margin_bottom,
        )

    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        parts = _render_parts(video_path, segments, tmp_dir, method, box_filter)
        merged = _concat(parts, tmp_dir)

        if audio_mp3:
            _mux_audio(merged, audio_mp3, out)
        else:
            merged.replace(out)

    cache.set(
        cache.make_key("video", map_key, out.name),
        {"input": str(video_path), "output": str(out), "segments": len(segments)},
    )
