"""Entities to control lights."""
from machine import Pin

from mqtt_house.entity.base import Entity


class SinglePinSimpleLight(Entity):
    """A simple Light Entity controlled by a single pin."""

    def __init__(self, device, entity, initial_state):
        """Initialise the Light, setting up the control pin."""
        super().__init__(device, entity, initial_state)
        entity["device_class"] = "light"
        self._pin = Pin(entity["options"]["pin"], Pin.OUT)

    async def discover(self):
        """Discover this Light Entity by publishing it to the MQTT server."""
        await super().discover()
        await self.subscribe(self.mqtt_topic("set"))
        await self.publish_config({"device_class": "light", "schema": "json", "command_topic": self.mqtt_topic("set")})
        if self._state is None:
            self._state = {"state": "OFF"}
            self._pin.off()
        else:
            if self._state["state"] == "ON":
                self._pin.on()
            else:
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
