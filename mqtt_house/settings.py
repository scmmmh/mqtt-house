"""Configuration file models."""

from typing import Literal

from pydantic import BaseModel


class DeviceModel(BaseModel):
    type: Literal["generic"] | Literal["enviro"] = "generic"
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
    debug: bool = False
    device: DeviceModel
    mqtt: MQTTModel
    wifi: WiFiModel
    entities: list[EntityModel]
