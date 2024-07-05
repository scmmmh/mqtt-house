"""Entities to control switches."""
from machine import Pin
from uasyncio import sleep_ms

from mqtt_house.entity.base import Entity


class HBridgeMomentarySwitch(Entity):
    """A simple Switch Entity controlling a h-bridge momentary switch."""

    def __init__(self, device, entity, initial_state):
        """Initialise the Light, setting up the control pin."""
        super().__init__(device, entity, initial_state)
        entity["device_class"] = "switch"
        self._pin_enable = Pin(entity["options"]["pins"]["enable"], Pin.OUT)
        self._pin1 = Pin(entity["options"]["pins"]["pin1"], Pin.OUT)
        self._pin2 = Pin(entity["options"]["pins"]["pin2"], Pin.OUT)
        self._pin_enable.off()
        self._pin1.off()
        self._pin2.off()

    async def discover(self):
        """Discover this Light Entity by publishing it to the MQTT server."""
        await super().discover()
        await self.subscribe(self.mqtt_topic("set"))
        await self.publish_config({"device_class": "switch", "schema": "json", "command_topic": self.mqtt_topic("set")})
        if self._state is None:
            self._state = {"state": "OFF"}
        await self._toggle()

    async def message(self, topic, message):
        """Receive a message from the MQTT server."""
        if topic.endswith("/set"):
            if message["state"] == "ON":
                self._state = {"state": "ON"}
            else:
                self._state = {"state": "OFF"}
            await self._toggle()
            await self.publish_state()

    async def _toggle(self):
        if self._state is not None:
            if self._state["state"] == "ON":
                self._pin1.on()
                self._pin2.off()
            elif self._state["state"] == "OFF":
                self._pin1.off()
                self._pin2.on()
            self._pin_enable.on()
            await sleep_ms(50)
            self._pin_enable.off()
            self._pin1.off()
            self._pin2.off()
