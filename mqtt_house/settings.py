"""Configuration file models."""

from typing import Literal

from pydantic import BaseModel


class GenericDeviceModel(BaseModel):
    type: Literal["generic"] = "generic"
    name: str
    domain: str


class EnviroDeviceModel(BaseModel):
    type: Literal["enviro"] = "enviro"
    name: str
    domain: str


class YukonDeviceModel(BaseModel):
    type: Literal["yukon"] = "yukon"
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
    device: GenericDeviceModel | EnviroDeviceModel | YukonDeviceModel
    mqtt: MQTTModel
    wifi: WiFiModel
    entities: list[EntityModel]
