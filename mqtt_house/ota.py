"""CLI commands for handling configurations."""
from hashlib import sha256
from importlib import resources
from json import dumps
from time import sleep

from httpx import Client, TransportError, codes
from rich.progress import Progress
from typer import FileBinaryRead
from yaml import safe_load

from mqtt_house.base import app, console
from mqtt_house.settings import ConfigModel
from mqtt_house.util import slugify


class OTAError(Exception):
    """An exception raised during the OTA update."""

    pass


def get_device_version(config: ConfigModel, client: Client) -> dict | None:
    """Retrieves the device's version or None if the device could not be contacted."""
    try:
        response = client.get(f"http://{slugify(config.device.name)}.{config.device.domain}/ota/about")
        if response.status_code == codes.OK:
            return [int(c) for c in response.json()["version"].split(".")]
        msg = (
            f"Failed to get the device version from http://{slugify(config.device.name)}.{config.device.domain} "
            "({response.status_code})."
        )

        raise OTAError(msg)
    except TransportError as err:
        msg = f"The device could not be reached at http://{slugify(config.device.name)}.{config.device.domain}."
        raise OTAError(msg) from err
    except KeyError as err:
        msg = f"Failed to get a valid device version from http://{slugify(config.device.name)}.{config.device.domain}."
        raise OTAError(msg) from err


def prepare_device(config: ConfigModel, client: Client, progress: Progress) -> None:
    """Prepare the device for the OTA update."""
    task = progress.add_task("Preparing the device", total=2)
    # Check the device version allows an upgrade
    version = get_device_version(config, client)
    if version[0] != 0:
        msg = (
            f"The device at http://{slugify(config.device.name)}.{config.device.domain} "
            "has a major version mismatch and cannot be updated over-the-air."
        )
        raise OTAError(msg)
    progress.update(task, advance=1)
    # Rollback any existing upgrade
    try:
        response = client.post(f"http://{slugify(config.device.name)}.{config.device.domain}/ota/rollback")
        if response.status_code != codes.NO_CONTENT:
            msg = (
                f"Preparing the device at http://{slugify(config.device.name)}.{config.device.domain} "
                f"for the update failed ({response.status_code})"
            )
            raise OTAError(msg)
    except TransportError as err:
        msg = f"The device could not be reached at http://{slugify(config.device.name)}.{config.device.domain}."
        raise OTAError(msg) from err
    progress.update(task, advance=1)


def prepare_update(config: ConfigModel) -> tuple[list, list]:
    """Prepare the inventory and files for upload."""
    inventory = []
    files = []
    # Add the config files
    inventory.append(
        {
            "fileid": "1",
            "filename": "config.json",
        }
    )
    files.append(
        {
            "fileid": "1",
            "filename": "config.json",
            "data": dumps(
                {
                    "device": config.device.model_dump(),
                    "mqtt": config.mqtt.model_dump(),
                    "wifi": config.wifi.model_dump(),
                }
            ).encode(),
        }
    )
    inventory.append({"fileid": "2", "filename": "entities.json"})
    files.append({"fileid": "2", "filename": "entities.json", "data": dumps(config.entities).encode()})
    base_path = resources.files("mqtt_house.micro")
    for idx, filename in enumerate(
        [
            "main.py",
            "microdot.py",
            "mqtt_as.py",
            "mqtt_house/__init__.py",
            "ota_server.py",
            "status_led.py",
        ]
    ):
        item_file = base_path
        for part in filename.split("/"):
            item_file = item_file / part
        inventory.append({"fileid": str(idx + 3), "filename": filename})
        files.append({"fileid": str(idx + 3), "filename": filename, "data": item_file.read_bytes()})
    return inventory, files


def upload_file(item: dict, config: ConfigModel, client: Client, endpoint: str = "/file") -> None:
    """Upload a single file to the device."""
    sha256_hash = sha256(item["data"])
    try:
        response = client.put(
            f"http://{slugify(config.device.name)}.{config.device.domain}/ota{endpoint}",
            content=item["data"],
            headers={"X-Fileid": item["fileid"], "X-Filehash": sha256_hash.hexdigest()},
        )
        if response.status_code != codes.NO_CONTENT:
            msg = (
                f"Failed to upload {item['filename']} to http://{slugify(config.device.name)}.{config.device.domain}"
                f" ({response.status_code})."
            )
            raise OTAError(msg)
    except TransportError as err:
        msg = f"The device could not be reached at http://{slugify(config.device.name)}.{config.device.domain}."
        raise OTAError(msg) from err


def upload_files(inventory: list, files: list, config: ConfigModel, client: Client, progress: Progress) -> None:
    """Upload all files to the device."""
    task = progress.add_task("Uploading the new files", total=len(files) + 1)
    upload_file({"fileid": "-1", "data": dumps(inventory).encode()}, config, client, endpoint="/inventory")
    progress.update(task, advance=1)
    for item in files:
        upload_file(item, config, client)
        progress.update(task, advance=1)


def commit_update(config: ConfigModel, client: Client, progress: Progress) -> None:
    """Commit all uploaded changes."""
    task = progress.add_task("Committing the changes", total=1, start=False)
    try:
        response = client.post(f"http://{slugify(config.device.name)}.{config.device.domain}/ota/commit")
        progress.start_task(task)
        if response.status_code == codes.NO_CONTENT:
            progress.update(task, completed=1)
        else:
            msg = (
                f"The update to http://{slugify(config.device.name)}.{config.device.domain} failed to"
                f" commit correctly ({response.status_code})."
            )
            raise OTAError(msg)
    except TransportError as err:
        msg = f"The device could not be reached at http://{slugify(config.device.name)}.{config.device.domain}."
        raise OTAError(msg) from err


def reset(config: ConfigModel, client: Client, progress: Progress) -> None:
    """Reset the device and wait for it to reappear."""
    task = progress.add_task("Resetting the device", total=60, start=False)
    response = client.post(
        f"http://{slugify(config.device.name)}.{config.device.domain}/ota/reset",
        content=dumps(config.entities),
    )
    progress.start_task(task)
    if response.status_code == codes.ACCEPTED:
        countdown = 60
        success = False
        while countdown > 0:
            sleep(1)
            try:
                response = client.get(f"http://{slugify(config.device.name)}.{config.device.domain}/ota/about")
                if response.status_code == codes.OK and response.json()["version"] == "0.0.1":
                    success = True
                    break
            except TransportError:
                pass
            finally:
                countdown = countdown - 1
                progress.update(task, advance=1)
        progress.update(task, completed=60)
        if not success:
            msg = (
                f"The device at http://{slugify(config.device.name)}.{config.device.domain}"
                " did not reappear within one minute after resetting."
            )
            raise OTAError(msg)
    else:
        msg = (
            f"Received error {response.status_code} when trying to reset the device at"
            f" http://{slugify(config.device.name)}.{config.device.domain}."
        )
        raise OTAError(msg)


@app.command()
def ota_deploy(config_file: FileBinaryRead):
    """Deploy a device via an OTA update."""
    config = ConfigModel(**safe_load(config_file))
    try:
        with Client() as client:
            with Progress() as progress:
                prepare_device(config, client, progress)
                upload_files(*prepare_update(config), config, client, progress)
                commit_update(config, client, progress)
                reset(config, client, progress)
                console(
                    f":heavy_check_mark: [green]The device http://{slugify(config.device.name)}.{config.device.domain}"
                    " has been updated with the new configuration."
                )
    except OTAError as e:
        console(f":x: [logging.level.error]{e!s}")
    # console(result)
