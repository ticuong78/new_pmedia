import typer

from typing import Literal
from rich.console import Console

from src.cli.container import AppContainer
from src.domain.core.stt_base import STTResponse

console = Console()

app = typer.Typer()

SEGMENT_PROMPT = """
Cho đoạn nội dung sau đây:

{words}


Yêu cầu chức năng:

Bạn hãy decode nội dung (nếu có), sau đó, tạo ra một json content chứa một mảng gồm nhiều các Sentence. Mỗi Sentence sẽ bao gồm `start`, `end` và `sentence`, sao cho một câu khi được tạo ra sẽ có một ngữ nghĩa theo ngữ cảnh nhất định và phải phù hợp.

Yều cầu định dạng đầu ra:

{{
    "sentences": [
        {{
            "start": <float>,
            "end": <float>,
            "sentence": <string>
        }},
        ...
    ]
}}

Lưu ý: cho tôi json và không giải thích gì thêm.
"""


@app.command()
def segment(
    key: str = typer.Argument(..., help="Cached transcript key to segment"),
    technique: Literal["openai", "words_count", "punctuation"] = typer.Option(
        "openai",
        help="Segment technique to use",
    ),
    model: Literal[
        "gpt-5.2-pro",
        "gpt-5.2-pro-2025-12-11",
        "gpt-5.2-chat-latest",
        "gpt-4o",
        "chatgpt-4o-latest",
        "gpt-4o-2024-11-20",
    ] = typer.Option("gpt-4o", help="OpenAi model to use"),
    ctx: typer.Context = typer.Option(None, hidden=True),
):
    if not isinstance(ctx.obj, AppContainer):
        raise typer.BadParameter("App container not initialized")

    transcript = ctx.obj.cache.get(key)
    segment_tecnique = ctx.obj.segment_service_factory.get_segment_service(
        technique, SEGMENT_PROMPT, model=model
    )

    if not segment_tecnique:
        raise ValueError("Segment Technique should not be null.")

    if transcript is None:
        console.print("[red]Not found[/red]")
        raise typer.Exit(1)

    if isinstance(transcript, STTResponse):
        console.print("[green]Segmenting transcript...[/green]")
        (result, key) = segment_tecnique.segment(transcript.words)  # type: ignore

        console.print(result)

        console.print(f"[cyan]Cached segmented transcript key: [/cyan]{key}")

    else:
        console.print(
            f"[red]Unsupported transcript type: [/red] {type(transcript).__name__}"
        )
        raise typer.Exit(code=1)
