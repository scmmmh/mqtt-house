"""An ADC sensor."""
import asyncio
import math
from machine import ADC, Pin

from mqtt_house.entity.base import Entity


class ADCSensor(Entity):
    """A sensor connected to one of the ADC pins."""

    def __init__(self, device, entity, initial_state):
        """Initialise the Entity, setting up the ADC device."""

        super().__init__(device, entity, initial_state)

        entity["device_class"] = "sensor"

        self._adc = ADC(Pin(entity["options"]["adc"]["pin"]))
        self._state={"value":0}
        self._measure_task = None

    async def discover(self):
        """Discover this ADC Entity by publishing it to the MQTT server."""
        await super().discover()
        await self.publish_config(
            {
                "expire_after": 600,
                "value_template": "{{ value_json.value }}",
                "suggested_display_precision": 0,
            }
        )
        if self._measure_task is None:
            self._measure_task = asyncio.create_task(self.measure_task())

    async def _measure_state(self):
        adc_value = self._adc.read_u16() >> (16 - self._entity["options"]["adc"]["bits"])
        # (x - in_min) * (out_max - out_min) / (in_max - in_min) + out_min
        value = round((adc_value - 0) * (self._entity["options"]["output"]["max"] - self._entity["options"]["output"]["min"]) / (math.pow(2, self._entity["options"]["adc"]["bits"]) - 1 - 0)  + self._entity["options"]["output"]["min"])
        if value != self._state["value"]:
            self._state["value"] = value
            return True
        return False

    async def measure_task(self):
        """Background measurement task."""
        while True:
            if await self._measure_state():
                await self.publish_state()
            await asyncio.sleep(0.1)
