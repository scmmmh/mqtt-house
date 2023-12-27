"""The version command."""
from mqtt_house.__about__ import __version__
from mqtt_house.base import app, console


@app.command()
def version() -> None:
    """Output the current version."""
    console(f"Version: [bold]{__version__}[/bold]")
