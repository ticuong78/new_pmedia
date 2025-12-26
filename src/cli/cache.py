from pathlib import Path
from typing import Any, Literal

import typer
from rich.console import Console
from rich.table import Table

from src.application.formatters.word import word_to_json
from src.application.service.cache import DiskCache
from src.domain.core.sentence import Sentence
from src.domain.core.stt_base import STTResponse

BASE_CACHE_DIR = Path(__file__).resolve().parents[2] / ".cache"

console = Console()
app = typer.Typer(help="Cache inspection commands")


def _render_stt_content(
    value,
    *,
    verbose: Literal["text", "words", "hybrid"],
    truncate: bool,
    console: Console,
    text_limit: int = 200,
    words_limit: int = 10,
):
    def _render_text():
        if truncate:
            preview = value.text[:text_limit]
            suffix = "..." if len(value.text) > text_limit else ""
            console.print(f"[cyan]Text:[/cyan] {preview}{suffix}")
        else:
            console.print(f"[cyan]Text:[/cyan] {value.text}")

    def _render_words():
        json_words = [word_to_json(single_word) for single_word in value.words]

        if truncate:
            preview = json_words[:words_limit]
            suffix = "..." if len(json_words) > words_limit else ""
            console.print(f"[cyan]Words:[/cyan] {preview}{suffix}")
        else:
            console.print(f"[cyan]Words:[/cyan] {json_words}")

    if verbose == "text":
        _render_text()

    elif verbose == "words":
        _render_words()

    else:  # hybrid
        _render_text()
        _render_words()


def _classify_value(value: Any) -> str:
    if isinstance(value, STTResponse):
        return "transcript"
    if isinstance(value, list) and all(isinstance(item, Sentence) for item in value):
        return "segment"
    return type(value).__name__


def _iter_cache(cache: DiskCache):
    for key in cache._cache.iterkeys():  # type: ignore[attr-defined]
        yield key, cache.get(key)  # type: ignore


@app.command("get")
def get_key(
    key: str = typer.Argument(..., help="Cache key"),
    verbose: Literal["text", "words", "hybrid"] = typer.Option(
        "text",
        "--verbose",
        "-v",
        help="Output mode: text, words, or hybrid",
        show_default=True,
    ),
    truncate: bool = typer.Option(
        True,
        "--truncate/--no-truncate",
        help="Truncate long output",
        show_default=True,
    ),
):
    """Get a cached item by key."""
    cache = DiskCache(directory=str(BASE_CACHE_DIR))
    value = cache.get(key)
    if value is None:
        console.print("[red]Not found[/red]")
        raise typer.Exit(1)

    console.print(f"[cyan]Key:[/cyan] {key}")
    console.print(f"[cyan]Type:[/cyan] {_classify_value(value)}")
    if isinstance(value, STTResponse):
        _render_stt_content(
            value,
            verbose=verbose,
            truncate=truncate,
            console=console,
        )
        console.print(f"[cyan]Words:[/cyan] {len(value.words)}")
    elif isinstance(value, list) and value and isinstance(value[0], Sentence):
        console.print(f"[cyan]Sentences:[/cyan] {len(value)}")
        preview = value[0].sentence
        console.print(f"[cyan]Preview:[/cyan] {preview}")
    else:
        console.print(repr(value))


@app.command("exists")
def exists(key: str):
    """Check if a cache key exists."""
    cache = DiskCache(directory=str(BASE_CACHE_DIR))
    found = cache.get(key) is not None
    console.print("[green]Yes[/green]" if found else "[red]No[/red]")
    raise typer.Exit(0 if found else 1)


@app.command("list")
def list_keys(
    prefix: str = typer.Option("", "--prefix", "-p", help="Filter keys by prefix")
):
    """List cache keys and their types."""
    cache = DiskCache(directory=str(BASE_CACHE_DIR))
    table = Table(title="Cache keys", show_lines=False)
    table.add_column("Key", overflow="fold", no_wrap=True)
    table.add_column("Type")
    count = 0
    for key, value in _iter_cache(cache):
        if prefix and not str(key).startswith(prefix):
            continue
        table.add_row(str(key), _classify_value(value))
        count += 1
    console.print(table)
    console.print(f"[cyan]Total:[/cyan] {count}")


@app.command("stats")
def stats():
    """Show cache statistics for transcripts vs segments."""
    cache = DiskCache(directory=str(BASE_CACHE_DIR))
    total = 0
    transcripts = 0
    segments = 0
    for _, value in _iter_cache(cache):
        total += 1
        kind = _classify_value(value)
        if kind == "transcript":
            transcripts += 1
        elif kind == "segment":
            segments += 1
    console.print(f"[cyan]Total keys:[/cyan] {total}")
    console.print(f"[cyan]Transcripts:[/cyan] {transcripts}")
    console.print(f"[cyan]Segments:[/cyan] {segments}")


@app.command("clear")
def clear(
    confirm: bool = typer.Option(
        False, "--yes", "-y", help="Confirm clearing the cache"
    )
):
    """Clear the cache store."""
    if not confirm:
        console.print("[yellow]Use --yes to confirm clearing the cache[/yellow]")
        raise typer.Exit(1)
    cache = DiskCache(directory=str(BASE_CACHE_DIR))
    cache.clear()
    console.print("[green]Cache cleared[/green]")
