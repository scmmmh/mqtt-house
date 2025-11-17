import asyncio
import json
import network
import sys
from machine import Pin

from mqtt_as import MQTTClient, config
from status_led import status_led

from mqtt_house.util import slugify


class Device:
    """The main application device."""

    def __init__(self, settings, entities, server):
        """Initialise the MQTT connection."""
        self.settings = settings
        config["server"] = settings["mqtt"]["server"]
        config["ssl"] = (
            True
            if "mqtt" in settings
            and "ssl" in settings["mqtt"]
            and settings["mqtt"]["ssl"]
            else False
        )
        config["user"] = settings["mqtt"]["user"]
        config["password"] = settings["mqtt"]["password"]
        config["ssid"] = settings["wifi"]["ssid"]
        config["wifi_pw"] = settings["wifi"]["password"]
        network.hostname(slugify(settings["device"]["name"]))
        config["queue_len"] = 1
        MQTTClient.DEBUG = True
        self._client = MQTTClient(config)

        self.name = settings["device"]["name"]
        self.identifier = slugify(self.name)

        try:
            with open("state.json") as in_f:
                self.state = json.load(in_f)
        except Exception:
            self.state = {}

        self._entitites = []
        for entity in entities:
            try:
                module = entity["cls"][: entity["cls"].rfind(".")]
                cls = entity["cls"][entity["cls"].rfind(".") + 1 :]
                if module not in sys.modules:
                    exec(f"import {module}")
                self._entitites.append(
                    getattr(sys.modules[module], cls)(
                        self,
                        entity,
                        (
                            self.state[entity["name"]]
                            if entity["name"] in self.state
                            else None
                        ),
                    )
                )
            except Exception as e:
                print(e)

        self._server = server

    async def subscribe(self, topic):
        """Subscribe to the given MQTT topic."""
        status_led.start_activity()
        await self._client.subscribe(topic)
        status_led.stop_activity()

    async def publish(self, topic, message):
        """Publish an MQTT message."""
        status_led.start_activity()
        await self._client.publish(topic, message)
        status_led.stop_activity()

    async def update_state(self, name, state):
        """Update the global state with the state of an entity."""
        self.state[name] = state
        with open("state.json", "w") as out_f:
            json.dump(self.state, out_f)

    async def discover(self):
        """Run the discovery process for all entities and then publish their states."""
        for entity in self._entitites:
            await entity.discover()
        await asyncio.sleep(5)
        for entity in self._entitites:
            await entity.publish_state()

    async def messages(self):
        """Handle incoming MQTT messages."""
        async for topic, message, retained in self._client.queue:
            try:
                status_led.start_activity()
                topic = topic.decode()
                status_led.stop_activity()
                if topic == f"{self.settings['mqtt']['prefix']}/status":
                    if message.decode() == "online":
                        await self.discover()
                else:
                    found = False
                    for entity in self._entitites:
                        if entity.mqtt_topic("set") == topic:
                            await entity.message(topic, json.loads(message))
                            found = True
                            break
                    if not found:
                        print(topic)
            except Exception as e:
                print(e)

    async def connection_monitor(self):
        """Monitor the connection, running the discovery when needed."""
        while True:
            await self._client.up.wait()
            self._client.up.clear()
            status_led.stop_indeterminate()
            await self.subscribe(f"{self.settings['mqtt']['prefix']}/status")
            await self.discover()

    async def start(self):
        """Start the controller."""
        try:
            while True:
                try:
                    status_led.start_indeterminate()
                    await self._client.connect()
                    asyncio.create_task(self.connection_monitor())
                    asyncio.create_task(self.messages())
                    self._server.run(port=80)
                except OSError as e:
                    status_led.stop_indeterminate()
                    print(e)
                    await asyncio.sleep(5)
        finally:
            self._client.close()
            status_led.shutdown()


class EnviroDevice(Device):

    async def start(self):
        """Start the controller."""
        from machine import RTC
        from pcf85063a import PCF85063A
        from pimoroni_i2c import PimoroniI2C

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
