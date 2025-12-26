from pathlib import Path

import typer
from rich.console import Console

from src.cli.container import AppContainer

console = Console()
app = typer.Typer(help="Translation commands")


@app.command()
def translate(
    text: str = typer.Argument(..., help="Text to translate or @path/to/file"),
    target: str = typer.Option(..., "--to", "-t", help="Target language (e.g., en, vi)"),
    source: str | None = typer.Option(None, "--from", "-f", help="Source language code (optional)"),
    ctx: typer.Context = typer.Option(None, hidden=True),
):
    """Translate text using configured translator, cache result, and print key."""
    if not isinstance(ctx.obj, AppContainer):
        raise typer.BadParameter("App container not initialized")

    if text.startswith("@"):
        file_path = Path(text[1:])
        if not file_path.exists():
            raise typer.BadParameter(f"File not found: {file_path}")
        text_content = file_path.read_text(encoding="utf-8")
    else:
        text_content = text

    translated, key = ctx.obj.translate.execute(text_content, target, source)

    console.rule("[bold green]Translation Complete")
    console.print(f"[cyan]Cache key:[/cyan] {key}")
    console.print(f"[cyan]Target:[/cyan] {target}")
    if source:
        console.print(f"[cyan]Source:[/cyan] {source}")
    console.print("\n[bold]Result:[/bold]")
    console.print(translated)
