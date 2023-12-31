"""Entities to measure temperature."""
import asyncio
import ds18x20
import onewire

from machine import Pin

from mqtt_house.entity.base import Entity


class OneWireDS18x20Temperature(Entity):
    """A temperature Entity measuring using one or more DS18x20 onewire sensors."""

    def __init__(self, device, entity, initial_state):
        """Initialise the Light, setting up the control pin."""
        super().__init__(device, entity, initial_state)
        entity["device_class"] = "sensor"
        self._sensor_hub = ds18x20.DS18X20(onewire.OneWire(Pin(entity["options"]["pin"])))
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
        sensors = self._sensor_hub.scan()
        while True:
            self._sensor_hub.convert_temp()
            await asyncio.sleep(1)
            measurements = [self._sensor_hub.read_temp(sensor) for sensor in sensors]
            if len(measurements) > 0:
                temperature = sum(measurements) / len(measurements)
            else:
                temperature = -56
            self._state = {"temperature": temperature}
            await self.publish_state()
            await asyncio.sleep(29)
