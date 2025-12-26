import typer

from src.cli import cache, segment, stt, tts
from src.cli import translate as translate_cli
from src.cli.container import AppContainer, build_container


app = typer.Typer(help="Media CLI")


@app.callback()
def init_app(ctx: typer.Context):
    """Composition root: build and attach dependencies."""
    ctx.obj = build_container()


app.add_typer(stt.app, name="stt")
app.add_typer(tts.app, name="tts")
app.add_typer(cache.app, name="cache")
app.add_typer(translate_cli.app, name="translate")
app.command(name="segment")(segment.segment)


if __name__ == "__main__":
    app()
