"""Eversolo API Client."""
from __future__ import annotations

import aiohttp
import async_timeout
import asyncio
import socket

from .const import LOGGER


class EversoloApiClientError(Exception):
    """Exception to indicate a general API error."""


class EversoloApiClientCommunicationError(EversoloApiClientError):
    """Exception to indicate a communication error."""


class EversoloApiClientAuthenticationError(EversoloApiClientError):
    """Exception to indicate an authentication error."""


class EversoloApiClient:
    """Eversolo API Client."""

    def __init__(
        self,
        host: str,
        port: int,
        session: aiohttp.ClientSession,
    ) -> None:
        """Eversolo API Client."""
        self._host = host
        self._port = port
        self._session = session

    async def async_get_data(self):
        """Get data from the API."""
        result = {
            "display_brightness": await self.async_get_display_brightness(),
            "input_output_state": await self.async_get_input_output_state(),
            "knob_brightness": await self.async_get_knob_brightness(),
            "music_control_state": await self.async_get_music_control_state(),
            "vu_mode_state": await self.async_get_vu_mode_state(),
        }
        LOGGER.debug("Fetched data from API: %s", result)
        return result

    async def async_get_music_control_state(self):
        """Return music control state."""
        result = await self._api_wrapper(
            method="get",
            url=f"http://{self._host}:{self._port}/ZidooMusicControl/v2/getState",
        )
        return result

    async def async_get_input_output_state(self):
        """Return input/output state."""
        result = await self._api_wrapper(
            method="get",
            url=f"http://{self._host}:{self._port}/ZidooMusicControl/v2/getInputAndOutputList",
        )
        return result

    async def async_get_vu_mode_state(self):
        """Return VU mode state."""
        result = await self._api_wrapper(
            method="get",
            url=f"http://{self._host}:{self._port}/SystemSettings/displaySettings/getVUModeList",
        )
        return result

    async def async_get_display_brightness(self) -> any:
        """Return the display brightness in range 0..255."""
        result = await self._api_wrapper(
            method="get",
            url=f"http://{self._host}:{self._port}/SystemSettings/displaySettings/getScreenBrightness",
        )
        current_value = result.get("currentValue", None)
        if current_value is None:
            LOGGER.debug('Key "currentValue" not found in response')
            return None

        # Max value for brightness is 115
        return round(current_value * (255 / 115))

    async def async_set_display_brightness(self, value) -> any:
        """Set the display brightness to a value in range 0..255."""
        # Max value for brightness is 115
        brightness = round(value * (115 / 255))
        return await self._api_wrapper(
            method="get",
            url=f"http://{self._host}:{self._port}/SystemSettings/displaySettings/setScreenBrightness?index={brightness}",
            parseJson=False,
        )

    async def async_get_knob_brightness(self) -> any:
        """Return the knob brightness in range 0..255."""
        result = await self._api_wrapper(
            method="get",
            url=f"http://{self._host}:{self._port}/SystemSettings/displaySettings/getKnobBrightness",
        )
        current_value = result.get("currentValue", None)
        if current_value is None:
            LOGGER.debug('Key "currentValue" not found in response')
            return None

        # Max value for brightness is 255
        return round(current_value)

    async def async_set_knob_brightness(self, value) -> any:
        """Set the knob brightness to a value in range 0..255."""
        # Max value for brightness is 255
        return await self._api_wrapper(
            method="get",
            url=f"http://{self._host}:{self._port}/SystemSettings/displaySettings/setKnobBrightness?index={value}",
            parseJson=False,
        )

    async def async_trigger_reboot(self) -> any:
        """Reboots the device."""
        await self._api_wrapper(
            method="get",
            url=f"http://{self._host}:{self._port}/ZidooMusicControl/v2/setPowerOption?tag=reboot",
            parseJson=False,
        )

    async def async_trigger_power_off(self) -> any:
        """Powers off the device."""
        await self._api_wrapper(
            method="get",
            url=f"http://{self._host}:{self._port}/ZidooMusicControl/v2/setPowerOption?tag=poweroff",
            parseJson=False,
        )

    async def async_trigger_toggle_screen(self) -> any:
        """Toggles screen on/off."""
        await self._api_wrapper(
            method="get",
            url=f"http://{self._host}:{self._port}/ZidooMusicControl/v2/setPowerOption?tag=screen",
            parseJson=False,
        )

    async def async_trigger_cycle_screen_mode(self) -> any:
        """Goes to the next screen."""
        await self._api_wrapper(
            method="get",
            url=f"http://{self._host}:{self._port}/ZidooMusicControl/v2/changVUDisplay",
            parseJson=False,
        )

    async def async_select_vu_mode_option(self, index) -> any:
        """Select the VU meter style."""
        await self._api_wrapper(
            method="get",
            url=f"http://{self._host}:{self._port}/SystemSettings/displaySettings/setVUMode?index={index}",
            parseJson=False,
        )

    async def async_mute(self) -> any:
        """Mutes the output."""
        await self._api_wrapper(
            method="get",
            url=f"http://{self._host}:{self._port}/ZidooMusicControl/v2/setMuteVolume?isMute=1",
            parseJson=False,
        )

    async def async_unmute(self) -> any:
        """Unmutes the output."""
        await self._api_wrapper(
            method="get",
            url=f"http://{self._host}:{self._port}/ZidooMusicControl/v2/setMuteVolume?isMute=0",
            parseJson=False,
        )

    async def async_volume_down(self) -> any:
        """Decreases the volume by one step."""
        await self._api_wrapper(
            method="get",
            url=f"http://{self._host}:{self._port}/ZidooControlCenter/RemoteControl/sendkey?key=Key.VolumeDown",
            parseJson=False,
        )

    async def async_volume_up(self) -> any:
        """Increases the volume by one step."""
        await self._api_wrapper(
            method="get",
            url=f"http://{self._host}:{self._port}/ZidooControlCenter/RemoteControl/sendkey?key=Key.VolumeUp",
            parseJson=False,
        )

    async def async_toggle_play_pause(self) -> any:
        """Toggles between play and pause."""
        await self._api_wrapper(
            method="get",
            url=f"http://{self._host}:{self._port}/ZidooMusicControl/v2/playOrPause",
            parseJson=False,
        )

    async def async_previous_title(self) -> any:
        """Plays the previous title."""
        await self._api_wrapper(
            method="get",
            url=f"http://{self._host}:{self._port}/ZidooMusicControl/v2/playLast",
            parseJson=False,
        )

    async def async_next_title(self) -> any:
        """Plays the next title."""
        await self._api_wrapper(
            method="get",
            url=f"http://{self._host}:{self._port}/ZidooMusicControl/v2/playNext",
            parseJson=False,
        )

    async def async_seek_time(self, time) -> any:
        """Seeks to a time given in milliseconds."""
        await self._api_wrapper(
            method="get",
            url=f"http://{self._host}:{self._port}/ZidooMusicControl/v2/seekTo?time={time}",
            parseJson=False,
        )

    async def async_set_volume(self, volume) -> any:
        """Set the volume."""
        await self._api_wrapper(
            method="get",
            url=f"http://{self._host}:{self._port}/ZidooMusicControl/v2/setDevicesVolume?volume={volume}",
            parseJson=False,
        )

    async def async_set_input(self, index, tag) -> any:
        """Set the input/source."""
        await self._api_wrapper(
            method="get",
            url=f"http://{self._host}:{self._port}/ZidooMusicControl/v2/setInputList?tag={tag}&index={index}",
            parseJson=False,
        )

    async def async_set_output(self, index, tag) -> any:
        """Set the output."""
        await self._api_wrapper(
            method="get",
            url=f"http://{self._host}:{self._port}/ZidooMusicControl/v2/setOutInputList?tag={tag}&index={index}",
            parseJson=False,
        )

    def create_internal_image_url(self, song_id) -> any:
        """Create url to fetch album covers when using the internal player."""
        return f"http://{self._host}:{self._port}/ZidooMusicControl/v2/getImage?id={song_id}&target=16"

    async def _api_wrapper(
        self,
        method: str,
        url: str,
        data: dict | None = None,
        headers: dict | None = None,
        parseJson: bool = True,
    ) -> any:
        """Get information from the API."""
        try:
            async with async_timeout.timeout(10):
                response = await self._session.request(
                    method=method,
                    url=url,
                    headers=headers,
                    json=data,
                )
                if response.status in (401, 403):
                    raise EversoloApiClientAuthenticationError(
                        "Invalid credentials",
                    )
                response.raise_for_status()
                if parseJson:
                    return await response.json(content_type=None)
                else:
                    return await response.read()

        except asyncio.TimeoutError as exception:
            raise EversoloApiClientCommunicationError(
                "Timeout error fetching information",
            ) from exception
        except (aiohttp.ClientError, socket.gaierror) as exception:
            raise EversoloApiClientCommunicationError(
                "Error fetching information",
            ) from exception
        except Exception as exception:  # pylint: disable=broad-except
            raise EversoloApiClientError(
                "Something really wrong happened!"
            ) from exception
