import typer
from rich.console import Console

from src.cli.container import AppContainer
from src.domain.core.sentence import Sentence
from src.domain.core.stt_base import STTResponse

console = console = Console(force_terminal=True, legacy_windows=False)
app = typer.Typer(help="Translation commands")


def _extract_text(payload) -> str | None:
    """Return plain text from supported cache payloads."""
    if isinstance(payload, STTResponse):
        return payload.text
    if (
        isinstance(payload, list)
        and payload
        and all(isinstance(item, Sentence) for item in payload)
    ):
        return " ".join(sentence.sentence for sentence in payload)
    if isinstance(payload, str):
        return payload
    return None


@app.command()
def translate(
    key: str = typer.Argument(..., help="Cache key containing text to translate"),
    target: str = typer.Option(
        ..., "--to", "-t", help="Target language (e.g., en, vi)"
    ),
    source: str | None = typer.Option(
        None, "--from", "-f", help="Source language code (optional)"
    ),
    quiet: bool = typer.Option(False, "--quiet", "-q", help="Suppress console output"),
    ctx: typer.Context = typer.Option(None, hidden=True),
):
    """Translate text using configured translator, cache result, and print key."""
    if not isinstance(ctx.obj, AppContainer):
        raise typer.BadParameter("App container not initialized")

    cached_value = ctx.obj.cache.get(key)

    if cached_value is None:
        # if not quiet:
        # print"[red]Not found[/red]")
        raise typer.Exit(1)

    text = _extract_text(cached_value)
    if not text:
        # if not quiet:
        # print()
        #     f"[red]Unsupported cache entry type:[/red] {type(cached_value).__name__}"
        # )
        raise typer.Exit(code=1)

    translated, translated_key = ctx.obj.translate.execute(text, target, source)

    print(translated_key)

    if not quiet:
        # print"[bold green]Translation Complete")
        # printf"[cyan]Input key:[/cyan] {key}")
        # if translated_key:
        # printf"[cyan]Cache key:[/cyan] {translated_key}")
        # printf"[cyan]Target:[/cyan] {target}")
        # if source:
        # printf"[cyan]Source:[/cyan] {source}")
        preview = text.strip()
        if preview:
            suffix = "..." if len(preview) > 200 else ""
            # printf"[cyan]Original:[/cyan] {preview[:200]}{suffix}")
        # print"\n[bold]Result:[/bold]")
        # printtranslated)
