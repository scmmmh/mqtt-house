import asyncio

from machine import RTC, Pin
from pcf85063a import PCF85063A
from pimoroni_i2c import PimoroniI2C
from status_led import status_led

from mqtt_house.device.generic import Device


class EnviroDevice(Device):

    async def start(self):
        """Start the controller."""
        hold_vsys_en_pin = Pin(2, Pin.OUT, value=True)
        i2c = PimoroniI2C(4, 5, 100000)
        rtc = PCF85063A(i2c)
        i2c.writeto_mem(0x51, 0x00, b'\x00')
        rtc.enable_timer_interrupt(False)
        t = rtc.datetime()
        RTC().datetime((t[0], t[1], t[2], t[6], t[3], t[4], t[5], 0))
        try:
            connected = False
            while not connected:
                try:
                    status_led.start_indeterminate()
                    await self._client.connect()
                    await self._client.up.wait()
                    connected = True
                    status_led.stop_indeterminate()
                except OSError as e:
                    status_led.stop_indeterminate()
                    print(e)
                    await asyncio.sleep(5)
            if connected:
                await self.discover()
        finally:
            self._client.close()
            status_led.shutdown()

        rtc.clear_timer_flag()
        rtc.clear_alarm_flag()
        dt = rtc.datetime()
        hour, minute, second = dt[3:6]
        minute = minute + 5
        while minute >= 60:
            minute -= 60
            hour += 1
        if hour >= 24:
            hour -= 24
        rtc.set_alarm(0, minute, hour)
        rtc.enable_alarm_interrupt(True)
        hold_vsys_en_pin.init(Pin.IN)
