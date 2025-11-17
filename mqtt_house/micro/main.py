"""The main microcontroller script."""

import asyncio
import json

from ota_server import server


with open("config.json") as settings_f:
    with open("entities.json") as entities_f:
        settings = json.load(settings_f)
        entities = json.load(entities_f)
        if settings["device"]["type"] == "generic":
            from mqtt_house.device.generic import Device
        elif settings["device"]["type"] == "enviro":
            from mqtt_house.device.enviro import EnviroDevice as Device
        controller = Device(settings, entities, server)
        asyncio.run(controller.start())
