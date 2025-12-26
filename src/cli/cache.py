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

console = console = Console(force_terminal=True, legacy_windows=False)
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
            # printf"[cyan]Text:[/cyan] {preview}{suffix}")
        # else:
        # printf"[cyan]Text:[/cyan] {value.text}")

    def _render_words():
        json_words = [word_to_json(single_word) for single_word in value.words]

        if truncate:
            preview = json_words[:words_limit]
            suffix = "..." if len(json_words) > words_limit else ""
            # printf"[cyan]Words:[/cyan] {preview}{suffix}")
        # else:
        # printf"[cyan]Words:[/cyan] {json_words}")

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
    quiet: bool = typer.Option(False, "--quiet", "-q", help="Suppress console output"),
):
    """Get a cached item by key."""
    cache = DiskCache(directory=str(BASE_CACHE_DIR))
    value = cache.get(key)
    if value is None:
        # if not quiet:
        # print"[red]Not found[/red]")
        raise typer.Exit(1)

    if quiet:
        return

    # printf"[cyan]Key:[/cyan] {key}")
    # printf"[cyan]Type:[/cyan] {_classify_value(value)}")
    if isinstance(value, STTResponse):
        _render_stt_content(
            value,
            verbose=verbose,
            truncate=truncate,
            console=console,
        )
        # printf"[cyan]Words:[/cyan] {len(value.words)}")
    elif isinstance(value, list) and value and isinstance(value[0], Sentence):
        # printf"[cyan]Sentences:[/cyan] {len(value)}")
        preview = value[0].sentence
        # printf"[cyan]Preview:[/cyan] {preview}")
    # else:
    # printrepr(value))


@app.command("exists")
def exists(
    key: str,
    quiet: bool = typer.Option(False, "--quiet", "-q", help="Suppress console output"),
):
    """Check if a cache key exists."""
    cache = DiskCache(directory=str(BASE_CACHE_DIR))
    found = cache.get(key) is not None
    # if not quiet:
    # print"[green]Yes[/green]" if found else "[red]No[/red]")
    raise typer.Exit(0 if found else 1)


@app.command("list")
def list_keys(
    prefix: str = typer.Option("", "--prefix", "-p", help="Filter keys by prefix"),
    quiet: bool = typer.Option(False, "--quiet", "-q", help="Suppress console output"),
):
    """List cache keys and their types."""
    cache = DiskCache(directory=str(BASE_CACHE_DIR))
    if quiet:
        for key, value in _iter_cache(cache):
            if prefix and not str(key).startswith(prefix):
                continue
            # keep traversal for parity with non-quiet mode
        return
    table = Table(title="Cache keys", show_lines=False)
    table.add_column("Key", overflow="fold", no_wrap=True)
    table.add_column("Type")
    count = 0
    for key, value in _iter_cache(cache):
        if prefix and not str(key).startswith(prefix):
            continue
        table.add_row(str(key), _classify_value(value))
        count += 1
    # printtable)
    # printf"[cyan]Total:[/cyan] {count}")


@app.command("stats")
def stats(
    quiet: bool = typer.Option(False, "--quiet", "-q", help="Suppress console output"),
):
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
    if quiet:
        return
    # printf"[cyan]Total keys:[/cyan] {total}")
    # printf"[cyan]Transcripts:[/cyan] {transcripts}")
    # printf"[cyan]Segments:[/cyan] {segments}")


@app.command("clear")
def clear(
    confirm: bool = typer.Option(
        False, "--yes", "-y", help="Confirm clearing the cache"
    ),
    quiet: bool = typer.Option(False, "--quiet", "-q", help="Suppress console output"),
):
    """Clear the cache store."""
    if not confirm:
        # if not quiet:
        # print"[yellow]Use --yes to confirm clearing the cache[/yellow]")
        raise typer.Exit(1)
    cache = DiskCache(directory=str(BASE_CACHE_DIR))
    cache.clear()
    # if not quiet:
    # print"[green]Cache cleared[/green]")


@app.command("delete")
def delete_key(
    key: str = typer.Argument(..., help="Cache key to delete"),
    quiet: bool = typer.Option(False, "--quiet", "-q", help="Suppress console output"),
):
    """Delete a single cache entry by key."""
    cache = DiskCache(directory=str(BASE_CACHE_DIR))
    existed = cache.get(key) is not None
    cache.delete(key)
    if quiet:
        return
    # if existed:
    # printf"[green]Deleted:[/green] {key}")
    # else:
    # printf"[yellow]Key not found:[/yellow] {key}")
