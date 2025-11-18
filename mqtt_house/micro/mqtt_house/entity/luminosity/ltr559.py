"""Illuminance entity using the LTR559."""
import asyncio

from breakout_ltr559 import BreakoutLTR559

from mqtt_house.entity.base import Entity
from mqtt_house.sensors import get_i2c

class Illuminance(Entity):
    """A illuminance Entity measuring using a LTR559 sensor."""

    def __init__(self, device, entity, initial_state):
        """Initialise the Entity, setting up the BME280 device."""
        super().__init__(device, entity, initial_state)

        from mqtt_house.sensors import get_bme280

        entity["device_class"] = "sensor"
        self._ltr_559 = BreakoutLTR559(get_i2c(0, entity["options"]["sda"], entity["options"]["sdl"]))
        self._measure_task = None

    async def discover(self):
        """Discover this illuminance Entity by publishing it to the MQTT server."""
        await super().discover()
        await self.publish_config(
            {
                "device_class": "illuminance",
                "expire_after": 600,
                "suggested_display_precision": 0,
                "value_template": "{{ value_json.illuminance }}",
                "unit_of_measurement": "lx",
            }
        )
        if self._measure_task is None:
            self._measure_task = asyncio.create_task(self.measure_task())

    async def measure_task(self):
        """Background measurement task."""
        while True:
            ltr_data = self._ltr_559.get_reading()
            self._state = {"illuminance": ltr_data[BreakoutLTR559.LUX]}
            await self.publish_state()
            await asyncio.sleep(29)
