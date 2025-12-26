from pathlib import Path

import typer
from rich.console import Console

from src.cli.container import AppContainer

console = console = Console(force_terminal=True, legacy_windows=False)
app = typer.Typer(help="Text-to-speech commands")


@app.command()
def synthesize(
    text: str | None = typer.Argument(
        None,
        help="Text to synthesize. Use --key to read text from cache instead.",
    ),
    cache_key: str | None = typer.Option(
        None,
        "--key",
        "-k",
        help="Cache key containing translated text to read aloud",
    ),
    voice_id: str = typer.Option(..., "--voice", "-v", help="ElevenLabs voice id"),
    model_id: str | None = typer.Option(
        None, "--model", "-m", help="ElevenLabs TTS model id (optional)"
    ),
    output: Path = typer.Option(
        Path("output.mp3"),
        "--output",
        "-o",
        help="Path to save synthesized audio",
        show_default=True,
    ),
    quiet: bool = typer.Option(False, "--quiet", "-q", help="Suppress console output"),
    ctx: typer.Context = typer.Option(None, hidden=True),
):
    """Synthesize speech from text or a cached translation key."""
    if not isinstance(ctx.obj, AppContainer):
        raise typer.BadParameter("App container not initialized")

    if bool(text) == bool(cache_key):
        raise typer.BadParameter("Provide either text or --key, but not both.")

    try:
        if cache_key:
            audio_stream, resolved_text = ctx.obj.tts.synthesize_from_cache(
                cache_key, voice_id, model_id
            )
            source_label = f"cache key: {cache_key}"
        else:
            assert text is not None
            audio_stream, resolved_text = ctx.obj.tts.synthesize(
                text, voice_id, model_id
            )
            source_label = "inline text"
    except KeyError as err:
        # printf"[red]{err}[/red]")
        raise typer.Exit(code=1)
    except ValueError as err:
        # printf"[red]{err}[/red]")
        raise typer.Exit(code=1)

    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("wb") as f:
        for chunk in audio_stream:
            f.write(chunk)

    # if not quiet:
    #     # print"[bold green]TTS Complete")
    #     # printf"[cyan]Source:[/cyan] {source_label}")
    #     # printf"[cyan]Voice:[/cyan] {voice_id}")
    #     # if model_id:
    #         # printf"[cyan]Model:[/cyan] {model_id}")
    #     if resolved_text:
    #         preview = resolved_text.strip()
    #         if preview:
    #             suffix = "..." if len(preview) > 200 else ""
    # printf"[cyan]Text preview:[/cyan] {preview[:200]}{suffix}")
    # printf"[cyan]Saved to:[/cyan] {output}")
