"""Entities to control lights."""
import asyncio

from machine import Pin

from mqtt_house.entity.base import Entity


class SinglePinBinarySensor(Entity):
    """A simple BinarySensor Entity using a single pin."""

    def __init__(self, device, entity, initial_state):
        """Initialise the BinarySensor, setting up the control pin."""
        super().__init__(device, entity, initial_state)
        entity["device_class"] = "binary_sensor"
        if entity["options"]["mode"] == "pull-up":
            self._pin = Pin(entity["options"]["pin"], mode=Pin.IN, pull=Pin.PULL_UP)
        else:
            self._pin = Pin(entity["options"]["pin"], mode=Pin.IN, pull=Pin.PULL_DOWN)
        self._polling_task = None

    async def discover(self):
        """Discover this BinarySensor Entity by publishing it to the MQTT server."""
        await super().discover()
        await self.publish_config({"device_class": "binary_sensor", "schema": "json", "state_topic": self.mqtt_topic("state")})

        if self._polling_task is None:
            self._polling_task = asyncio.create_task(self.polling_task())

    async def polling_task(self):
        """Background polling task."""
        value = -1
        while True:
            if self._pin.value() != value:
                value = self._pin.value()
                if value == 1:
                    if self._entity["options"]["mode"] == "pull-up":
                        self._state = {"state": "OFF"}
                    else:
                        self._state = {"state": "ON"}
                else:
                    if self._entity["options"]["mode"] == "pull-up":
                        self._state = {"state": "ON"}
                    else:
                        self._state = {"state": "OFF"}
                await self.publish_state()
            await asyncio.sleep_ms(5)
