"""Run the MQTT House application."""
from mqtt_house import config, version  # noqa: F401
from mqtt_house.base import app

if __name__ == "__main__":
    app()
