# MQTT House

A pure python project for easy deployment of HomeAssistant MQTT entities via Raspberry Pi Picos.

[![PyPI - Version](https://img.shields.io/pypi/v/mqtt-house.svg)](https://pypi.org/project/mqtt-house)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/mqtt-house.svg)](https://pypi.org/project/mqtt-house)
[![Test workflow status](https://github.com/scmmmh/mqtt-house/actions/workflows/tests.yml/badge.svg)](https://github.com/scmmmh/mqtt-house/actions/workflows/tests.yml)
[![Test coverage](https://img.shields.io/endpoint?url=https://gist.githubusercontent.com/scmmmh/5d987fef5ad47e17d68138644e5331b5/raw/coverage.json)](https://github.com/scmmmh/mqtt-house/actions/workflows/tests.yml)

-----

**Table of Contents**

- [Installation](#installation)
- [License](#license)

## Installation

The recommended installation method is via [pipx](https://github.com/pypa/pipx):

```console
pipx install mqtt-house
```

## License

`mqtt-house` is distributed under the terms of the [MIT](https://spdx.org/licenses/MIT.html) license.

`mqtt-house` includes specific versions of the following libraries:

* [microdot](https://github.com/miguelgrinberg/microdot)
* [micropython-mqtt](https://github.com/peterhinch/micropython-mqtt)
* Onewire
* DS18x20
* [BME280](https://github.com/robert-hh/BME280)
