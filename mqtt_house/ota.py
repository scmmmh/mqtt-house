"""CLI commands for handling configurations."""
from hashlib import sha256
from importlib import resources
from json import dumps
from time import sleep

from httpx import Client, Response, TransportError, codes
from rich.progress import Progress
from typer import FileBinaryRead
from yaml import safe_load

from mqtt_house.__about__ import __version__
from mqtt_house.base import app, console
from mqtt_house.settings import ConfigModel
from mqtt_house.util import slugify


def get_device_version(config: ConfigModel, client: Client, progress: Progress) -> dict | None:
    """Retrieves the device's version or None if the device could not be contacted."""
    task = progress.add_task("Checking the device version", total=1, start=False)
    try:
        response = client.get(f"http://{slugify(config.device.name)}.{config.device.domain}/ota/about")
        if response.status_code == codes.OK:
            return response.json()
    except TransportError:
        pass
    finally:
        progress.start_task(task)
        progress.update(task, advance=1)
    return None


def upload_data(config: ConfigModel, client: Client, item: dict) -> Response:
    sha256_hash = sha256(item["data"])
    return client.put(
        f"http://{slugify(config.device.name)}.{config.device.domain}/ota/file",
        content=item["data"],
        headers={"X-Fileid": item["fileid"], "X-Filehash": sha256_hash.hexdigest()},
    )


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
    files = []
    # Prepare the files to upload
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
        files.append({"fileid": str(idx + 3), "filename": filename, "data": item_file.read_bytes()})
    # Upload the inventory
    task = progress.add_task("Uploading the inventory", total=1)
    inventory = []
    for item in files:
        inventory.append({"fileid": item["fileid"], "filename": item["filename"]})
    response = client.put(
        f"http://{slugify(config.device.name)}.{config.device.domain}/ota/inventory",
        content=dumps(inventory).encode(),
        headers={"X-Filehash": sha256(dumps(inventory).encode()).hexdigest()},
    )
    if response.status_code == codes.NO_CONTENT:
        progress.update(task, advance=1)
    else:
        return f":x: [logging.level.error]Received error {response.status_code} when uploading the inventory"
    # Upload the files
    task = progress.add_task("Uploading the files", total=len(files))
    for item in files:
        response = upload_data(config, client, item)
        if response.status_code == codes.NO_CONTENT:
            progress.update(task, advance=1)
        else:
            return f":x: [logging.level.error]Received error {response.status_code} when uploading the {filename}."
    # Start the update
    task = progress.add_task("Committing the changes", total=1, start=False)
    response = client.post(f"http://{slugify(config.device.name)}.{config.device.domain}/ota/commit")
    progress.start_task(task)
    if response.status_code == codes.NO_CONTENT:
        progress.update(task, completed=1)
    else:
        return f":x: [logging.level.error]Received error {response.status_code} when committing the update."
    # Reset the device and wait for it to become available again.
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
        if success:
            return ":heavy_check_mark: [green]The device has been updated with the new configuration."
        else:
            return (
                f":x: [logging.level.error]The device at http://{slugify(config.device.name)}.{config.device.domain}"
                " did not reappear within one minute after resetting."
            )
    else:
        progress.update(task, completed=60)
        return ":x: [logging.level.error]Received error {response.status_code} when trying to reset the device."


@app.command()
def ota_deploy(config_file: FileBinaryRead):
    """Deploy a device via an OTA update."""
    config = ConfigModel(**safe_load(config_file))
    with Client() as client:
        with Progress() as progress:
            result = perform_upload(config, client, progress)
    console(result)
