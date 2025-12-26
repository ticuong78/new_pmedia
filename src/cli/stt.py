import typer
from pathlib import Path

from rich.console import Console

from src.cli.container import AppContainer

console = console = Console(force_terminal=True, legacy_windows=False)
app = typer.Typer(help="Speech-to-text commands")


@app.command()
def transcribe(
    audio_path: Path = typer.Argument(..., help="Path to the audio file"),
    model_id: str = typer.Option(
        "scribe_v2",
        "--model",
        "-m",
        help="ElevenLabs STT model id",
    ),
    quiet: bool = typer.Option(False, "--quiet", "-q", help="Suppress console output"),
    ctx: typer.Context = typer.Option(None, hidden=True),
):
    """Transcribe audio, cache the result, and print the cache key."""
    if not audio_path.exists():
        raise typer.BadParameter(f"File not found: {audio_path}")

    if not isinstance(ctx.obj, AppContainer):
        raise typer.BadParameter("App container not initialized")

    audio_bytes = audio_path.read_bytes()

    response, key = ctx.obj.transcribe.execute(model_id, audio_bytes)

    print(key)

    if not quiet:
        # print"[bold green]Transcription Complete")
        # printf"[cyan]Cache key:[/cyan] {key}")
        if response and getattr(response, "text", None):
            preview = response.text.strip()
            if len(preview) > 200:
                preview = preview[:200] + "..."
            # printf"[bold]Preview:[/bold] {preview}")
