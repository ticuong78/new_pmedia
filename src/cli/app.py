import typer

from src.cli import cache, segment, stt, tts
from src.cli import translate as translate_cli
from src.cli import map as map_cli
from src.cli import video as video_cli
from src.cli.container import AppContainer, build_container


app = typer.Typer(help="Media CLI")


@app.callback()
def init_app(ctx: typer.Context):
    """Composition root: build and attach dependencies."""
    ctx.obj = build_container()


app.add_typer(stt.app, name="stt")
app.add_typer(tts.app, name="tts")
app.add_typer(cache.app, name="cache")
app.command(name="translate")(translate_cli.translate)
app.command(name="segment")(segment.segment)
app.command(name="map")(map_cli.map)
app.command(name="build_c")(map_cli.build_c)
app.command(name="video")(video_cli.render_video)


if __name__ == "__main__":
    app()
