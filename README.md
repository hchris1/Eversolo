# Eversolo Integration

[![GitHub Release][releases-shield]][releases]
[![GitHub Activity][commits-shield]][commits]
[![License][license-shield]](LICENSE)

[![hacs][hacsbadge]][hacs]
![Project Maintenance][maintenance-shield]

[![Community Forum][forum-shield]][forum]

_Integration for [Eversolo Digital Streamers](https://www.eversolo.com/)._

## Description

This custom component integrates Eversolo Digital Streamers into [Home Assistant](https://www.home-assistant.io/).

It provides the following entities:

| Platform      | Name                         | Description                                                                   |
|---------------|------------------------------|-------------------------------------------------------------------------------|
| Button        | Cycle Screen Mode            | Goes to next screen mode (menu, song info, VU meter with info, VU meter only) |
| Button        | Cycle Screen Mode (Spectrum) | Same as Cycle Screen Mode with spectrum instead of VU                         |
| Button        | Power Off                    | Turns off device                                                              |
| Button        | Reboot                       | Reboots device                                                                |
| Button        | Toggle Screen On/Off         | Turns display on/off                                                          |
| Light         | Display                      | Controls display brightness                                                   |
| Light         | Knob                         | Controls knob brightness                                                      |
| Media Player  | Eversolo                     | Media controls                                                                |
| Select        | Output Mode                  | Selects between available outputs                                             |
| Select        | VU Style                     | Selects between the 4 available VU styles                                     |
| Select        | Spectrum Style               | Selects between the 4 available Specrum styles                                |
| Sensor        | Version                      | Provides firmware version                                                     |

> [!IMPORTANT]
> This integration is only tested on the **Eversolo DMP-A6**. Tests and contributions to verify and support more Eversolo devices are welcome!

## Installation

### Install with HACS (recommended)

In case you have [HACS](https://hacs.xyz/) installed already, add this repository as a custom repository and install it. Restart Home Assistant afterwards to load the added integration. HACS will keep track of updates so you can install component updates when available.

### Install manually

Copy the `eversolo` folder from `Eversolo/custom_components` into your `custom_components` folder. Restart Home Assistant afterwards to load the added integration.

## Configuration

You can configure the component using the `Add integration` dialog. Search for `Eversolo` and enter the host IP of your Eversolo streamer.

[commits-shield]: https://img.shields.io/github/commit-activity/y/hchris1/eversolo.svg?style=for-the-badge
[commits]: https://github.com/hchris1/eversolo/commits/main
[hacs]: https://github.com/hacs/integration
[hacsbadge]: https://img.shields.io/badge/HACS-Custom-orange.svg?style=for-the-badge
[forum-shield]: https://img.shields.io/badge/community-forum-brightgreen.svg?style=for-the-badge
[forum]: https://community.home-assistant.io/
[license-shield]: https://img.shields.io/github/license/hchris1/eversolo.svg?style=for-the-badge
[maintenance-shield]: https://img.shields.io/badge/maintainer-Christian%20%40hchris1-blue.svg?style=for-the-badge
[releases-shield]: https://img.shields.io/github/release/hchris1/eversolo.svg?style=for-the-badge
[releases]: https://github.com/hchris1/eversolo/releases