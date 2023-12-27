"""The main microcontroller script."""
import asyncio
import json
import re

from machine import Pin, reset
from microdot import Microdot
from mqtt_as import MQTTClient, config

server = Microdot()


@server.get("/about")
def get_about(request):
    """Return information about this device."""
    return {"version": "0.0.1"}


@server.post("/reset")
def post_reset(request):
    """Request that the device reset itself."""

    async def reset_task():
        """Wait one second and then reset."""
        await asyncio.sleep(1)
        reset()

    asyncio.create_task(reset_task())
    return None, 202


@server.put("/update/file")
async def put_update_file(request):
    """Update a file on the device."""
    size = int(request.headers["Content-Length"])
    with open(request.headers["X-Filename"], "wb") as out_f:
        while size > 0:
            chunk = await request.stream.read(min(size, 1024))
            out_f.write(chunk)
            size -= len(chunk)
    return None, 204


def slugify(name):
    """Slugify a name."""
    name = name.lower()
    return re.sub("[^a-z0-9]", "-", name)


class Entity:
    """Represents a single Entity."""

    def __init__(self, device, entity):
        """Initialise the entity with the device and entity settings."""
        self._device = device
        self._entity = entity
        self._state = None

    def mqtt_topic(self, topic):
        """Return the correct MQTT topic for this entity."""
        return f"homeassistant/{self._entity['device_class']}/{self._device.identifier}-{slugify(self._entity['name'])}/{topic}"

    async def discover(self):
        """Unused."""
        pass

    async def publish_state(self):
        """Publish the Entity's current state."""
        await self._device.client.publish(
            self.mqtt_topic("state"),
            json.dumps(self._state),
        )

    async def message(self, topic, message):
        """Unused."""
        pass


class Light(Entity):
    """A simple Light Entity."""

    def __init__(self, device, entity):
        """Initialise the Light, setting up the control pin."""
        super().__init__(device, entity)
        self._pin = Pin(entity["pin"], Pin.OUT)

    async def discover(self):
        """Discover this Light Entity by publishing it to the MQTT server."""
        await super().discover()
        await self._device.client.subscribe(self.mqtt_topic("set"))
        await self._device.client.publish(
            self.mqtt_topic("config"),
            json.dumps(
                {
                    "name": self._entity["name"],
                    "device_class": self._entity["device_class"],
                    "schema": "json",
                    "state_topic": self.mqtt_topic("state"),
                    "command_topic": self.mqtt_topic("set"),
                    "unique_id": slugify(f"{self._device.identifier}-{self._entity['name']}"),
                    "device": {
                        "name": self._device.name,
                        "identifiers": [self._device.identifier],
                    },
                }
            ),
        )
        if self._state is None:
            if "initial_state" in self._entity:
                await self.message(self.mqtt_topic("set"), self._entity["initial_state"])
            else:
                self._state = {"state": "OFF"}
                self._pin.off()

    async def message(self, topic, message):
        """Receive a message from the MQTT server."""
        if topic.endswith("/set"):
            if message["state"] == "ON":
                self._pin.on()
                self._state = {"state": "ON"}
            else:
                self._pin.off()
                self._state = {"state": "OFF"}
            await self.publish_state()


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
        self.client = MQTTClient(config)

        self._activity_counter = 0
        self._activity_led = Pin("LED", Pin.OUT)

        self.name = settings["device"]["name"]
        self.identifier = slugify(self.name)

        self._entitites = []
        for entity in entities:
            if entity["device_class"] == "light":
                self._entitites.append(Light(self, entity))
            else:
                print(entity)

        self._server = server

    def start_activity(self):
        """Signal starting a new activity."""
        self._bu_activity_countery_counter = self._activity_counter + 1
        self._activity_led.off()

    def stop_activity(self):
        """Signal that an activity has concluded."""
        self._activity_counter = max(self._activity_counter - 1, 0)
        if self._activity_counter == 0:
            self._activity_led.on()

    async def discover(self):
        """Run the discovery process for all entities and then publish their states."""
        for entity in self._entitites:
            await entity.discover()
        await asyncio.sleep(5)
        for entity in self._entitites:
            await entity.publish_state()

    async def messages(self):
        """Handle incoming MQTT messages."""
        async for topic, message, retained in self.client.queue:
            self.start_activity()
            try:
                topic = topic.decode()
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
            self.stop_activity()

    async def connection_monitor(self):
        """Monitor the connection, running the discovery when needed."""
        while True:
            await self.client.up.wait()
            self.client.up.clear()
            self.start_activity()
            await self.client.subscribe("homeassistant/status")
            await self.discover()
            self.stop_activity()

    async def start(self):
        """Start the controller."""
        try:
            while True:
                try:
                    self._activity_led.on()
                    await self.client.connect()
                    asyncio.create_task(self.connection_monitor())
                    asyncio.create_task(self.messages())
                    self._server.run(port=80)
                except OSError as e:
                    print(e)
                    await asyncio.sleep(5)
        finally:
            self.client.close()
            self._activity_led.off()


with open("config.json") as settings_f:
    with open("entities.json") as entities_f:
        settings = json.load(settings_f)
        entities = json.load(entities_f)
        controller = Device(settings, entities, server)
        asyncio.run(controller.start())
