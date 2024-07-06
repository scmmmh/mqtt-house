"""CLI commands for a single device"""

from typing import Optional

from httpx import Client
from rich import print as console
from rich.progress import Progress
from typer import FileBinaryRead, Typer
from yaml import safe_load

from mqtt_house.lib.install import install as install_device
from mqtt_house.lib.ota import (
    OTAError,
    commit_update,
    get_device_version,
    prepare_device,
    prepare_update,
    upload_files,
)
from mqtt_house.lib.ota import reset as reset_device
from mqtt_house.settings import ConfigModel
from mqtt_house.util import slugify

group = Typer(name="device", help="Commands for a single device")


@group.command()
def install(config_file: FileBinaryRead, board: Optional[str] = None) -> None:
    """Install to a locally connected board."""
    config = ConfigModel(**safe_load(config_file))
    with Progress() as progress:
        install_device(config, progress, board)


@group.command()
def version(config_file: FileBinaryRead):
    """Get an OTA device's version."""
    config = ConfigModel(**safe_load(config_file))
    try:
        with Client(timeout=30) as client:
            version = ".".join([str(c) for c in get_device_version(config, client)])
            console(f"Device version: {version}")
    except OTAError as e:
        console(f":x: [logging.level.error]{e!s}")


@group.command()
def ota_update(config_file: FileBinaryRead):
    """Update a device via an OTA update."""
    config = ConfigModel(**safe_load(config_file))
    try:
        with Client(timeout=30) as client:
            with Progress() as progress:
                prepare_device(config, client, progress)
                upload_files(*prepare_update(config), config, client, progress)
                commit_update(config, client, progress)
                reset_device(config, client, progress)
            console(
                f":heavy_check_mark: [green]The device http://{slugify(config.device.name)}.{config.device.domain}"
                " has been updated with the new configuration."
            )
    except OTAError as e:
        console(f":x: [logging.level.error]{e!s}")


@group.command()
def reset(config_file: FileBinaryRead):
    """Reset an OTA device."""
    config = ConfigModel(**safe_load(config_file))
    try:
        with Client(timeout=30) as client:
            with Progress() as progress:
                reset_device(config, client, progress)
            console(
                f":heavy_check_mark: [green]The device http://{slugify(config.device.name)}.{config.device.domain}"
                " has been reset."
            )
    except OTAError as e:
        console(f":x: [logging.level.error]{e!s}")
