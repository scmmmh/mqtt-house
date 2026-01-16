"""A sensor that maps multiple pins onto an enumeration of values."""
import asyncio
from machine import Pin

from mqtt_house.entity.base import Entity


class Sensor(Entity):
    """A sensor that maps multiple pins onto an enumeration of values."""

    def __init__(self, device, entity, initial_state):
        """Initialise the Entity, setting up the individual pins."""

        super().__init__(device, entity, initial_state)

        entity["device_class"] = "sensor"

        self._state={"value": None}
        self._measure_task = None
        self._values = []
        for conf in self._entity["options"]["values"]:
            self._values.append({"pin": Pin(conf["pin"], Pin.IN, Pin.PULL_UP), "value": conf["value"]})

    async def discover(self):
        """Discover this multipin Sensor by publishing it to the MQTT server."""
        await super().discover()
        await self.publish_config(
            {
                "expire_after": 600,
                "value_template": "{{ value_json.value }}",
                "device_class": "enum",
                "options": ["forward", "stop", "reverse"]
            }
        )
        if self._measure_task is None:
            self._measure_task = asyncio.create_task(self.measure_task())

    async def measure_task(self):
        """Background measurement task."""
        while True:
            new_state = self._entity["options"]["default"]
            for value in self._values:
                if value["pin"].value() == 0:
                    new_state = value["value"]
                    break
            if new_state != self._state["value"]:
                self._state["value"] = new_state
                await self.publish_state()
            await asyncio.sleep(0.1)
