import asyncio
import json
import sys

from mqtt_as import MQTTClient, config
from status_led import status_led

from mqtt_house.util import slugify


class Device:
    """The main application device."""

    def __init__(self, settings, entities, server):
        """Initialise the MQTT connection."""
        config["server"] = settings["mqtt"]["server"]
        config["ssl"] = True if "mqtt" in settings and "ssl" in settings["mqtt"] and settings["mqtt"]["ssl"] else False
        config["user"] = settings["mqtt"]["user"]
        config["password"] = settings["mqtt"]["password"]
        config["ssid"] = settings["wifi"]["ssid"]
        config["wifi_pw"] = settings["wifi"]["password"]
        config["hostname"] = slugify(settings["device"]["name"])
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
                        self, entity, self.state[entity["name"]] if entity["name"] in self.state else None
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
                if topic == "homeassistant/status":
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
            await self.subscribe("homeassistant/status")
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
