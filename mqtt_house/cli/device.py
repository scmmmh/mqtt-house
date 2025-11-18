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
    get_device_host,
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
def version(config_file: FileBinaryRead, host: str | None = None):
    """Get an OTA device's version."""
    config = ConfigModel(**safe_load(config_file))
    try:
        with Client(timeout=30) as client:
            version = ".".join([str(c) for c in get_device_version(config, client, host=host)])
            console(f"Device version: {version}")
    except OTAError as e:
        console(f":x: [logging.level.error]{e!s}")


@group.command()
def ota_update(
    config_file: FileBinaryRead,
    host: str | None = None,
    upgrade_major_version: bool = False,  # noqa:FBT001,FBT002
):
    """Update a device via an OTA update."""
    config = ConfigModel(**safe_load(config_file))
    try:
        with Client(timeout=30) as client:
            with Progress() as progress:
                prepare_device(config, client, progress, host=host, upgrade_major_version=upgrade_major_version)
                upload_files(*prepare_update(config), config, client, progress, host=host)
                commit_update(config, client, progress, host=host)
                reset_device(config, client, progress, host=host)
            console(
                f":heavy_check_mark: [green]The device {get_device_host(config, host=host)}"
                " has been updated with the new configuration."
            )
    except OTAError as e:
        console(f":x: [logging.level.error]{e!s}")


@group.command()
def reset(config_file: FileBinaryRead, host: str | None = None):
    """Reset an OTA device."""
    config = ConfigModel(**safe_load(config_file))
    try:
        with Client(timeout=30) as client:
            with Progress() as progress:
                reset_device(config, client, progress, host=host)
            console(
                f":heavy_check_mark: [green]The device http://{slugify(config.device.name)}.{config.device.domain}"
                " has been reset."
            )
    except OTAError as e:
        console(f":x: [logging.level.error]{e!s}")
