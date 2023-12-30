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


class WiFiModel(BaseModel):
    ssid: str
    password: str


class ConfigModel(BaseModel):
    device: DeviceModel
    mqtt: MQTTModel
    wifi: WiFiModel
    entities: list[dict]
