"""A status LED with indeterminate and activity states."""
import asyncio

from machine import Pin


class StatusLED:
    """Implements the status LED functionality."""

    def __init__(self):
        """Initialise the status LED."""
        self._status_led = Pin("LED", Pin.OUT)
        self._activity_count = 0
        self._blink_task = None

    def start_activity(self):
        """Start an activity.

        Turns off the LED if there is no indeterminate blink task.
        """
        self._activity_count = self._activity_count + 1
        if self._blink_task is None:
            self._status_led.off()

    def stop_activity(self):
        """Stop an activity.

        Turns on the LED if there is no running activity and no indeterminate blink task.
        """
        self._activity_count = max(self._activity_count - 1, 0)
        if self._activity_count == 0 and self._blink_task is None:
            self._status_led.on()

    def start_indeterminate(self):
        """Start an indeterminate task."""
        if self._blink_task is None:
            self._blink_task = asyncio.create_task(self.blink())

    def stop_indeterminate(self):
        """Stop an indeterminate task.

        Sets the LED to the correct state depending on the number of activities running.
        """
        if self._blink_task is not None:
            self._blink_task.cancel()
            self._blink_task = None
            if self._activity_count > 0:
                self._status_led.off()
            else:
                self._status_led.on()

    def shutdown(self):
        """Shutdown all LEDs and tasks."""
        self._status_led.off()
        if self._blink_task is not None:
            self._blink_task.cancel()

    async def blink(self):
        """Background task to blink the status LED."""
        while True:
            self._status_led.toggle()
            await asyncio.sleep(0.2)


status_led = StatusLED()
