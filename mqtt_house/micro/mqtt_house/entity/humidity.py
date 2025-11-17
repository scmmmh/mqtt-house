"""Entities to measure temperature."""
import asyncio

from mqtt_house.entity.base import Entity


class BME280Humidity(Entity):
    """A humidty Entity measuring using a BME280 sensor."""

    def __init__(self, device, entity, initial_state):
        """Initialise the Entity, setting up the BME280 device."""
        super().__init__(device, entity, initial_state)

        from mqtt_house.sensors import get_bme280

        entity["device_class"] = "sensor"
        self._bme280 = get_bme280(0, entity["options"]["sda"], entity["options"]["sdl"], entity["options"]["address"])
        self._measure_task = None

    async def discover(self):
        """Discover this pressure Entity by publishing it to the MQTT server."""
        await super().discover()
        await self.publish_config(
            {
                "device_class": "humidity",
                "expire_after": 600,
                "suggested_display_precision": 0,
                "value_template": "{{ value_json.humidity }}",
                "unit_of_measurement": "%",
            }
        )
        if self._measure_task is None:
            self._measure_task = asyncio.create_task(self.measure_task())

    async def measure_task(self):
        """Background measurement task."""
        while True:
            (_temperature, _pressure, humidity) = self._bme280.read_compensated_data()
            self._state = {"humidity": humidity}
            await self.publish_state()
            await asyncio.sleep(29)
