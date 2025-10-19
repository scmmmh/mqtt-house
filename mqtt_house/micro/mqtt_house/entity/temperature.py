"""Entities to measure temperature."""
import asyncio

from machine import Pin, I2C

from mqtt_house.entity.base import Entity


class OneWireDS18x20Temperature(Entity):
    """A temperature Entity measuring using one or more DS18x20 onewire sensors."""

    def __init__(self, device, entity, initial_state):
        """Initialise the Entity, setting up the control hub."""
        super().__init__(device, entity, initial_state)

        import ds18x20
        import onewire

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


class BME280Temperature(Entity):
    """A temperature Entity measuring using a BME280 sensor."""

    def __init__(self, device, entity, initial_state):
        """Initialise the Entity, setting up the BME280 device."""
        super().__init__(device, entity, initial_state)

        from mqtt_house.sensors import get_bme280

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
