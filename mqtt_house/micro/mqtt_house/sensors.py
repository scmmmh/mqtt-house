"""Sensor definitions for shared sensors."""

from machine import I2C, Pin

i2c = None
bme280 = None


def get_i2c(i2c_device, i2c_sda, i2c_sdl):
    """Get the shared I2C device."""
    global i2c

    if i2c is None:
        i2c = I2C(i2c_device, sda=Pin(i2c_sda), scl=Pin(i2c_sdl), freq=400000)

    return i2c

def get_bme280(i2c_device, i2c_sda, i2c_sdl, address):
    """Get the shared BME280 device."""
    global bme280
    if bme280 is None:

        from bme280_float import BME280

        bme280 = BME280(address=address, i2c=get_i2c(i2c_device, i2c_sda, i2c_sdl))

    return bme280
