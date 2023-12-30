"""The main microcontroller script."""
import asyncio
import json

from ota_server import server
from mqtt_house.device import Device


with open("config.json") as settings_f:
    with open("entities.json") as entities_f:
        settings = json.load(settings_f)
        entities = json.load(entities_f)
        controller = Device(settings, entities, server)
        asyncio.run(controller.start())
