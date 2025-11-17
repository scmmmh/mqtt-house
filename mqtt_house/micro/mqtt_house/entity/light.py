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
        await self.publish_config({
            "device_class": "light",
            "schema": "json",
            "brightness": False,
            "command_topic": self.mqtt_topic("set")})
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


class ThreePinRGBLight(Entity):
    """A Light Entity controlling three pins (RGB)."""

    def __init__(self, device, entity, initial_state):
        """Initialise the Light, setting up the control pins."""
        super().__init__(device, entity, initial_state)
        entity["device_class"] = "light"
        self._red_pin = None
        self._green_pin = None
        self._blue_pin = None
        if "pins" in entity["options"]:
            if "red" in entity["options"]["pins"]:
                self._red_pin = Pin(entity["options"]["pins"]["red"], Pin.OUT)
            if "green" in entity["options"]["pins"]:
                self._green_pin = Pin(entity["options"]["pins"]["green"], Pin.OUT)
            if "blue" in entity["options"]["pins"]:
                self._blue_pin = Pin(entity["options"]["pins"]["blue"], Pin.OUT)

    async def discover(self):
        """Discover this Light Entity by publishing it to the MQTT server."""
        await super().discover()
        await self.subscribe(self.mqtt_topic("set"))
        await self.publish_config({
            "device_class": "light",
            "schema": "json",
            "command_topic": self.mqtt_topic("set"),
            "supported_color_modes": ["rgb"]
        })
        if self._state is None:
            self._state = {"state": "OFF", "color": {"r": 0, "g": 0, "b": 0}}
            self._set_pins()
        else:
            self._set_pins()

    async def message(self, topic, message):
        """Receive a message from the MQTT server."""
        if topic.endswith("/set"):
            if "state" in message:
                self._state["state"] = message["state"]
            if "color" in message:
                self._state["color"] = message["color"]
            self._set_pins()
            await self.publish_state()

    def _set_pins(self):
        """Set the correct pins, based on the state."""
        if self._state["state"] == "ON":
            if self._red_pin is not None:
                if self._state["color"]["r"] > 128:
                    self._red_pin.on()
                else:
                    self._red_pin.off()
            if self._green_pin is not None:
                if self._state["color"]["g"] > 128:
                    self._green_pin.on()
                else:
                    self._green_pin.off()
            if self._blue_pin is not None:
                if self._state["color"]["b"] > 128:
                    self._blue_pin.on()
                else:
                    self._blue_pin.off()
        else:
            if self._red_pin is not None:
                self._red_pin.off()
            if self._green_pin is not None:
                self._green_pin.off()
            if self._blue_pin is not None:
                self._blue_pin.off()
