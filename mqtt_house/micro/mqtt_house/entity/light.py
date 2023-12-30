import json

from machine import Pin

from mqtt_house.entity.base import Entity
from mqtt_house.util import slugify


class Light(Entity):
    """A simple Light Entity."""

    def __init__(self, device, entity):
        """Initialise the Light, setting up the control pin."""
        super().__init__(device, entity)
        self._pin = Pin(entity["pin"], Pin.OUT)

    async def discover(self):
        """Discover this Light Entity by publishing it to the MQTT server."""
        await super().discover()
        await self._device.subscribe(self.mqtt_topic("set"))
        await self._device.publish(
            self.mqtt_topic("config"),
            json.dumps(
                {
                    "name": self._entity["name"],
                    "device_class": self._entity["device_class"],
                    "schema": "json",
                    "state_topic": self.mqtt_topic("state"),
                    "command_topic": self.mqtt_topic("set"),
                    "unique_id": slugify(f"{self._device.identifier}-{self._entity['name']}"),
                    "device": {
                        "name": self._device.name,
                        "identifiers": [self._device.identifier],
                    },
                }
            ),
        )
        if self._state is None:
            if "initial_state" in self._entity:
                await self.message(self.mqtt_topic("set"), self._entity["initial_state"])
            else:
                self._state = {"state": "OFF"}
                self._pin.off()

    async def message(self, topic, message):
        """Receive a message from the MQTT server."""
        if topic.endswith("/set"):
            if message["state"] == "ON":
                self._pin.on()
                self._state = {"state": "ON"}
            else:
                self._pin.off()
                self._state = {"state": "OFF"}
            await self.publish_state()
