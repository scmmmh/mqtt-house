"""CLI commands for handling configurations."""
from json import dumps
from time import sleep

from httpx import Client, TransportError, codes
from rich.progress import Progress
from typer import FileBinaryRead, Typer
from yaml import safe_load

from mqtt_house.__about__ import __version__
from mqtt_house.base import app, console
from mqtt_house.settings import ConfigModel
from mqtt_house.util import slugify

config_group = Typer()
app.add_typer(config_group, name="config")


def get_device_version(config: ConfigModel, client: Client, progress: Progress) -> dict | None:
    """Retrieves the device's version or None if the device could not be contacted."""
    task = progress.add_task("Checking the device version", total=1, start=False)
    try:
        response = client.get(f"http://{slugify(config.device.name)}.{config.device.domain}/about")
        if response.status_code == codes.OK:
            return response.json()
    except TransportError:
        pass
    finally:
        progress.start_task(task)
        progress.update(task, advance=1)
    return None


def perform_upload(config: ConfigModel, client: Client, progress: Progress) -> str:
    """Perform the actual upload of the configuration.

    This checks that the device can receive the configuration, uploads it, resets the device, and then waits for the
    device to become available again.
    """
    # Check that the device is connectable and has a version that is supported.
    about = get_device_version(config, client, progress)
    if about is None:
        return (
            f":x: [logging.level.error]The device could not be contacted at http://{slugify(config.device.name)}."
            "{config.device.domain}. Please check the device and domain name settings."
        )
    elif "version" not in about:
        return (
            f":x: [logging.level.error]The device at http://{slugify(config.device.name)}.{config.device.domain} "
            "did not respond with version information. Please check the device and domain name settings."
        )
    elif about["version"] != __version__:
        return (
            f":x: [logging.level.error]The device at http://{slugify(config.device.name)}.{config.device.domain} "
            "did not respond with the current version. Please update the device first."
        )
    # Upload the core configuration file.
    task = progress.add_task("Uploading the configuration", total=2)
    response = client.put(
        f"http://{slugify(config.device.name)}.{config.device.domain}/update/file",
        content=dumps(
            {
                "device": config.device.model_dump(),
                "mqtt": config.mqtt.model_dump(),
                "wifi": config.wifi.model_dump(),
            }
        ),
        headers={"X-Filename": "config.json"},
    )
    if response.status_code == codes.NO_CONTENT:
        progress.update(task, advance=1)
    else:
        return f":x: [logging.level.error]Received error {response.status_code} when uploading the configuration."
    # Upload the entities file.
    response = client.put(
        f"http://{slugify(config.device.name)}.{config.device.domain}/update/file",
        content=dumps(config.entities),
        headers={"X-Filename": "entities.json"},
    )
    if response.status_code == codes.NO_CONTENT:
        progress.update(task, advance=1)
    else:
        return f":x: [logging.level.error]Received error {response.status_code} uploading the entities"
    # Reset the device and wait for it to become available again.
    task = progress.add_task("Resetting the device", total=12, start=False)
    response = client.post(
        f"http://{slugify(config.device.name)}.{config.device.domain}/reset",
        content=dumps(config.entities),
    )
    progress.start_task(task)
    if response.status_code == codes.ACCEPTED:
        countdown = 12
        success = False
        while countdown > 0:
            sleep(5)
            try:
                response = client.get(f"http://{slugify(config.device.name)}.{config.device.domain}/about")
                if response.status_code == codes.OK and response.json()["version"] == "0.0.1":
                    success = True
                    break
            except TransportError:
                pass
            finally:
                countdown = countdown - 1
                progress.update(task, advance=1)
        progress.update(task, completed=12)
        if success:
            return ":heavy_check_mark: [green]The device has been updated with the new configuration."
        else:
            return (
                f":x: [logging.level.error]The device at http://{slugify(config.device.name)}.{config.device.domain}"
                " did not reappear within one minute after resetting."
            )
    else:
        progress.update(task, completed=12)
        return ":x: [logging.level.error]Received error {response.status_code} when trying to reset the device."


@config_group.command()
def upload(config_file: FileBinaryRead):
    """Upload a configuration to the device."""
    config = ConfigModel(**safe_load(config_file))
    with Client() as client:
        with Progress() as progress:
            result = perform_upload(config, client, progress)
    console(result)
