"""Commands for handling devices over-the-air."""

import re
from hashlib import sha256
from importlib import resources
from json import dumps
from time import sleep

from httpx import Client, TransportError, codes
from rich.progress import Progress

from mqtt_house.settings import ConfigModel
from mqtt_house.util import slugify

ENTITY_FILES = {
    "mqtt_house.entity.light.SinglePinSimpleLight": [("mqtt_house.micro", "mqtt_house/entity/light.py")],
    "mqtt_house.entity.light.ThreePinRGBLight": [("mqtt_house.micro", "mqtt_house/entity/light.py")],
    "mqtt_house.entity.temperature.OneWireDS18x20Temperature": [
        ("mqtt_house.micro", "mqtt_house/entity/temperature.py"),
        ("mqtt_house.micro", "onewire.py"),
        ("mqtt_house.micro", "ds18x20.py"),
    ],
    "mqtt_house.entity.display.PicoInkyDisplay": [("mqtt_house.micro", "mqtt_house/entity/display.py")],
    "mqtt_house.entity.switch.HBridgeMomentarySwitch": [("mqtt_house.micro", "mqtt_house/entity/switch.py")],
    "mqtt_house.entity.binary_sensor.SinglePinBinarySensor": [
        ("mqtt_house.micro", "mqtt_house/entity/binary_sensor.py")
    ],
    "mqtt_house.entity.temperature.BME280Temperature": [
        ("mqtt_house.micro", "mqtt_house/entity/temperature.py"),
        ("mqtt_house.micro", "mqtt_house/sensors.py"),
        ("mqtt_house.micro", "bme280_float.py"),
    ],
    "mqtt_house.entity.pressure.BME280Pressure": [
        ("mqtt_house.micro", "mqtt_house/entity/pressure.py"),
        ("mqtt_house.micro", "mqtt_house/sensors.py"),
        ("mqtt_house.micro", "bme280_float.py"),
    ],
    "mqtt_house.entity.humidity.BME280Humidity": [
        ("mqtt_house.micro", "mqtt_house/entity/humidity.py"),
        ("mqtt_house.micro", "mqtt_house/sensors.py"),
        ("mqtt_house.micro", "bme280_float.py"),
    ],
}


class OTAError(Exception):
    """An exception raised during the OTA operation."""

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


def minimise_file(data: bytes):
    """Minimise the file size, stripping comments and empty lines"""
    result = []
    in_comment = False
    for line in data.decode("utf-8").split("\n"):
        if re.match(r"\s*#.*", line):
            continue
        elif line.strip() == "":
            continue
        elif re.match(r"\s*'''.*'''\s*", line) or re.match(r'\s*""".*"""\s*', line):
            continue
        elif not in_comment and (re.match(r"\s*'''.*", line) or re.match(r'\s*""".*', line)):
            in_comment = True
            continue
        elif in_comment and (re.match(r".*'''\s*", line) or re.match(r'.*"""\s*', line)):
            in_comment = False
            continue
        elif in_comment:
            continue
        result.append(f"{line}\n")
    return "".join(result).encode("utf-8")


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
                    "debug": config.debug,
                    "device": config.device.model_dump(),
                    "mqtt": config.mqtt.model_dump(),
                    "wifi": config.wifi.model_dump(),
                }
            ).encode(),
        }
    )
    inventory.append({"fileid": "2", "filename": "entities.json"})
    files.append(
        {
            "fileid": "2",
            "filename": "entities.json",
            "data": dumps([entity.model_dump() for entity in config.entities]).encode(),
        }
    )
    # Add the core files
    base_files = [
        "main.py",
        "microdot.py",
        "mqtt_as.py",
        "mqtt_house/__init__.py",
        "mqtt_house/__about__.py",
        "mqtt_house/device/__init__.py",
        "mqtt_house/device/generic.py",
        "mqtt_house/entity/__init__.py",
        "mqtt_house/entity/base.py",
        "mqtt_house/util.py",
        "ota_server.py",
        "status_led.py",
    ]
    if config.device.type == "enviro":
        base_files.append("mqtt_house/device/enviro.py")
    base_path = resources.files("mqtt_house.micro")
    for idx, filename in enumerate(base_files):
        item_file = base_path
        for part in filename.split("/"):
            item_file = item_file / part
        inventory.append({"fileid": str(idx + 3), "filename": filename})
        files.append({"fileid": str(idx + 3), "filename": filename, "data": minimise_file(item_file.read_bytes())})
    # Add the files required for the configured device and entities
    for entity in config.entities:
        if entity.cls in ENTITY_FILES:
            core_count = len(inventory) + 1
            for idx, (base_pkg, filename) in enumerate(ENTITY_FILES[entity.cls]):
                # Filter duplicates
                uploaded = False
                for inv in inventory:
                    if inv["filename"] == filename:
                        uploaded = True
                if uploaded:
                    continue
                item_file = resources.files(base_pkg)
                for part in filename.split("/"):
                    item_file = item_file / part
                inventory.append({"fileid": str(idx + core_count), "filename": filename})
                files.append(
                    {
                        "fileid": str(idx + core_count),
                        "filename": filename,
                        "data": minimise_file(item_file.read_bytes()),
                    }
                )
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
    response = client.post(f"http://{slugify(config.device.name)}.{config.device.domain}/ota/reset")
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
