"""MQTT-House CLI application."""

from rich import print as console
from typer import Typer

from mqtt_house.__about__ import __version__
from mqtt_house.cli.device import group as device_group
from mqtt_house.lib.install import get_boards

app = Typer(help="MQTT House CLI Application")
app.add_typer(device_group)


@app.command()
def connected_boards() -> None:
    """List connected boards."""
    for name, device in get_boards():
        console(f"{name} ({device})")


@app.command()
def version() -> None:
    """Output the current version."""
    console(f"Version: [bold]{__version__}[/bold]")
