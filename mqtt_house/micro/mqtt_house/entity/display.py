"""Entities to measure temperature."""
import asyncio


from machine import Pin
from picographics import PicoGraphics, DISPLAY_INKY_PACK

from mqtt_house.entity.base import Entity


class PicoInkyDisplay(Entity):
    """A display Entity using the Pico Inky display."""

    def __init__(self, device, entity, initial_state):
        """Initialise the Light, setting up the control pin."""
        super().__init__(device, entity, initial_state)
        self._display = PicoGraphics(display=DISPLAY_INKY_PACK)
        self._display.set_font("sans")
        self._display.set_thickness(2)
        self._update_task = None

    async def discover(self):
        """Discovery is disabled."""
        if self._update_task is None:
            self._update_task = asyncio.create_task(self.update_task())

    async def update_task(self):
        """Background measurement task."""
        self._display.set_pen(15)
        self._display.clear()
        self._display.set_pen(0)
        self._display.set_update_speed(0)
        self._display.update()
        last_values = dict([(idx, None) for idx, _ in enumerate(self._entity["options"]["elements"])])
        while True:
            values = {}
            for idx, element in enumerate(self._entity["options"]["elements"]):
                if "entity" in element:
                    if element["entity"] in self._device.state:
                        values[idx] = element["value"].format(**self._device.state[element["entity"]])
                    else:
                        values[idx] = "-"
                else:
                    values[idx] = element["value"]
            changed = False
            for key in last_values.keys():
                if key not in values or last_values[key] != values[key]:
                    changed = True
                    break
            if changed:
                self._display.set_update_speed(2)
                self._display.set_pen(15)
                self._display.clear()
                self._display.set_pen(0)
                for idx, element in enumerate(self._entity["options"]["elements"]):
                    left = 0
                    top = 0
                    angle = 0
                    letter_spacing = 0
                    if "font" in element:
                        if "thickness" in element["font"]:
                            self._display.set_thickness(element["font"]["thickness"])
                        if "letter-spacing" in element["font"]:
                            letter_spacing = element["font"]["letter-spacing"]
                    if "position" in element:
                        if "left" in element["position"]:
                            left = element["position"]["left"]
                        if "top" in element["position"]:
                            top = element["position"]["top"]
                        if "angle" in element["position"]:
                            angle = element["position"]["angle"]
                    self._display.text(values[idx], left, top, angle, letter_spacing)
                self._display.update()
            last_values = values
            await asyncio.sleep(self._entity["options"]["refresh"] if "refresh" in self._entity["options"] else 30)
