import logging
import aiohttp
import async_timeout

import voluptuous as vol

from homeassistant.const import CONF_NAME
from homeassistant.helpers import config_validation as cv
from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    PLATFORM_SCHEMA,
    LightEntity,
)

_LOGGER = logging.getLogger(__name__)

DOMAIN = "eversolo"
DEFAULT_NAME = "Eversolo Light"
DEFAULT_TIMEOUT = 10

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Required("ip_address"): cv.string,
    }
)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    name = config[CONF_NAME]
    ip_address = config["ip_address"]

    eversolo_light = EversoloLight(name, ip_address)

    async_add_entities([eversolo_light], update_before_add=True)


class EversoloLight(LightEntity):
    def __init__(self, name, ip_address):
        self._name = name
        self._ip_address = ip_address
        self._brightness = None

    @property
    def unique_id(self):
        return self._ip_address

    @property
    def name(self):
        return self._name

    @property
    def is_on(self):
        return self._brightness is not None and self._brightness > 0

    @property
    def brightness(self):
        return self._brightness

    async def async_turn_on(self, **kwargs):
        brightness = kwargs.get(ATTR_BRIGHTNESS, 255)  # Default to maximum brightness

        await self._set_brightness(brightness)

    async def async_turn_off(self, **kwargs):
        await self._set_brightness(0)

    async def async_update(self):
        try:
            async with async_timeout.timeout(DEFAULT_TIMEOUT):
                async with aiohttp.ClientSession() as session:
                    # Make a GET request to the endpoint that returns current brightness
                    response = await session.get(
                        f"http://{self._ip_address}:9529/SystemSettings/displaySettings/getScreenBrightness"
                    )

                    if response.status == 200:
                        data = await response.json()
                        self._brightness = data["currentValue"] * 255 / data["maxValue"]
                    else:
                        _LOGGER.error("Error fetching data from Eversolo device")
                        self._brightness = None
        except Exception as e:
            _LOGGER.error("Error updating Eversolo light: %s", str(e))
            self._brightness = None

    async def _set_brightness(self, brightness):
        try:
            async with async_timeout.timeout(DEFAULT_TIMEOUT):
                async with aiohttp.ClientSession() as session:
                    response = await session.get(
                        f"http://{self._ip_address}:9529/SystemSettings/displaySettings/setScreenBrightness?index={brightness * (115/255)}"
                    )

                    if response.status != 200:
                        _LOGGER.error("Error setting brightness on Eversolo device")
        except Exception as e:
            _LOGGER.error("Error setting brightness on Eversolo light: %s", str(e))
