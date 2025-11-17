"""Entities to measure temperature."""
import asyncio

from mqtt_house.entity.base import Entity
from mqtt_house.sensors import get_bme280


class Temperature(Entity):
    """A temperature Entity measuring using a BME280 sensor."""

    def __init__(self, device, entity, initial_state):
        """Initialise the Entity, setting up the BME280 device."""
        super().__init__(device, entity, initial_state)

        entity["device_class"] = "sensor"
        self._bme280 = get_bme280(0, entity["options"]["sda"], entity["options"]["sdl"], entity["options"]["address"])
        self._compensation = entity["options"]["compensation"] if "compensation" in entity["options"] else 0
        self._measure_task = None

    async def discover(self):
        """Discover this temperature Entity by publishing it to the MQTT server."""
        await super().discover()
        await self.publish_config(
            {
                "device_class": "temperature",
                "expire_after": 600,
                "suggested_display_precision": 1,
                "value_template": "{{ value_json.temperature }}",
                "unit_of_measurement": "°C",
            }
        )
        if self._measure_task is None:
            self._measure_task = asyncio.create_task(self.measure_task())

    async def measure_task(self):
        """Background measurement task."""
        while True:
            (temperature, _pressure, _humidity) = self._bme280.read_compensated_data()
            self._state = {"temperature": temperature + self._compensation}
            await self.publish_state()
            await asyncio.sleep(29)
