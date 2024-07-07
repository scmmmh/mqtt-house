"""Configuration file models."""

from pydantic import BaseModel


class DeviceModel(BaseModel):
    name: str
    domain: str


class MQTTModel(BaseModel):
    server: str
    user: str
    password: str
    ssl: bool = True
    prefix: str = "homeassistant"


class WiFiModel(BaseModel):
    ssid: str
    password: str


class EntityModel(BaseModel):
    cls: str
    name: str
    options: dict


class ConfigModel(BaseModel):
    device: DeviceModel
    mqtt: MQTTModel
    wifi: WiFiModel
    entities: list[EntityModel]
