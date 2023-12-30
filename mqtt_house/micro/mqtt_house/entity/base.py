"""The base Entity class."""
import json

from mqtt_house.__about__ import __version__
from mqtt_house.util import slugify


class Entity:
    """Represents a single Entity."""

    def __init__(self, device, entity):
        """Initialise the entity with the device and entity settings."""
        self._device = device
        self._entity = entity
        self._state = None

    def mqtt_topic(self, topic):
        """Return the correct MQTT topic for this entity."""
        return f"homeassistant/{self._entity['device_class']}/{self._device.identifier}-{slugify(self._entity['name'])}/{topic}"

    async def subscribe(self, topic):
        """Subscribe to an MQTT topic."""
        await self._device.subscribe(topic)

    async def discover(self):
        """Unused."""
        pass

    async def publish_config(self, config):
        """Publish the Entity's configuration to the configuration MQTT topic."""
        config["name"] = self._entity["name"]
        config["state_topic"] = self.mqtt_topic("state")
        config["unique_id"] = slugify(f"{self._device.identifier}-{self._entity['name']}")
        config["device"] = {
            "identifiers": [self._device.identifier],
            "manufacturer": "MQTT House",
            "model": "MQTT House @ Pi Pico",
            "name": self._device.name,
            "sw_version": f"v{__version__}",
        }
        await self._device.publish(self.mqtt_topic("config"), json.dumps(config))

    async def publish_state(self):
        """Publish the Entity's current state."""
        await self._device.publish(
            self.mqtt_topic("state"),
            json.dumps(self._state),
        )

    async def message(self, topic, message):
        """Unused."""
        pass
