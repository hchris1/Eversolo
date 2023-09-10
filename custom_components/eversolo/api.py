"""Sample API Client."""
from __future__ import annotations

import aiohttp
import async_timeout
import asyncio
import logging
import socket

_LOGGER = logging.getLogger(__name__)


class EversoloApiClientError(Exception):
    """Exception to indicate a general API error."""


class EversoloApiClientCommunicationError(EversoloApiClientError):
    """Exception to indicate a communication error."""


class EversoloApiClientAuthenticationError(EversoloApiClientError):
    """Exception to indicate an authentication error."""


class EversoloApiClient:
    """Sample API Client."""

    def __init__(
        self,
        host: str,
        port: int,
        session: aiohttp.ClientSession,
    ) -> None:
        """Sample API Client."""
        self._host = host
        self._port = port
        self._session = session

    async def async_get_data(self):
        """Get data from the API."""
        return {
            'display_brightness': await self.async_get_display_brightness(),
            'input_output_state': await self.async_get_input_output_state(),
            'knob_brightness': await self.async_get_knob_brightness(),
            'music_control_state': await self.async_get_music_control_state(),
            'vu_mode_state': await self.async_get_vu_mode_state(),
        }
        # result = {}
        # result['display_brightness'] = await self.async_get_display_brightness()
        # result['knob_brightness'] = await self.async_get_knob_brightness()
        # result['music_control_state'] = await self.async_get_music_control_state()
        # result['input_output_state'] = await self.async_get_input_output_state()
        # result['vu_mode_state'] = await self.async_get_vu_mode_state()
        # return result

    async def async_get_music_control_state(self):
        result = await self._api_wrapper(
            method='get',
            url=f'http://{self._host}:{self._port}/ZidooMusicControl/v2/getState',
        )
        return result

    async def async_get_input_output_state(self):
        result = await self._api_wrapper(
            method='get',
            url=f'http://{self._host}:{self._port}/ZidooMusicControl/v2/getInputAndOutputList',
        )
        return result

    async def async_get_vu_mode_state(self):
        result = await self._api_wrapper(
            method='get',
            url=f'http://{self._host}:{self._port}/SystemSettings/displaySettings/getVUModeList',
        )
        return result

    async def async_get_display_brightness(self) -> any:
        result = await self._api_wrapper(
            method='get',
            url=f'http://{self._host}:{self._port}/SystemSettings/displaySettings/getScreenBrightness',
        )
        # Max value for brightness is 115
        return round(result['currentValue'] * (255 / 115))

    async def async_set_display_brightness(self, value) -> any:
        # Max value for brightness is 115
        brightness = round(value * (115 / 255))
        return await self._api_wrapper(
            method='get',
            url=f'http://{self._host}:{self._port}/SystemSettings/displaySettings/setScreenBrightness?index={brightness}',
            parseJson=False,
        )

    async def async_get_knob_brightness(self) -> any:
        result = await self._api_wrapper(
            method='get',
            url=f'http://{self._host}:{self._port}/SystemSettings/displaySettings/getKnobBrightness',
        )
        # Max value for brightness is 115
        return round(result['currentValue'] * (255 / 115))

    async def async_set_knob_brightness(self, value) -> any:
        # Max value for brightness is 115
        brightness = round(value * (115 / 255))
        return await self._api_wrapper(
            method='get',
            url=f'http://{self._host}:{self._port}/SystemSettings/displaySettings/setKnobBrightness?index={brightness}',
            parseJson=False,
        )

    async def async_trigger_reboot(self) -> any:
        await self._api_wrapper(
            method='get',
            url=f'http://{self._host}:{self._port}/ZidooMusicControl/v2/setPowerOption?tag=reboot',
            parseJson=False,
        )

    async def async_trigger_power_off(self) -> any:
        await self._api_wrapper(
            method='get',
            url=f'http://{self._host}:{self._port}/ZidooMusicControl/v2/setPowerOption?tag=poweroff',
            parseJson=False,
        )

    async def async_trigger_toggle_screen(self) -> any:
        await self._api_wrapper(
            method='get',
            url=f'http://{self._host}:{self._port}/ZidooMusicControl/v2/setPowerOption?tag=screen',
            parseJson=False,
        )

    async def async_trigger_cycle_screen_mode(self) -> any:
        await self._api_wrapper(
            method='get',
            url=f'http://{self._host}:{self._port}/ZidooMusicControl/v2/changVUDisplay',
            parseJson=False,
        )

    async def async_select_vu_mode_option(self, index) -> any:
        await self._api_wrapper(
            method='get',
            url=f'http://{self._host}:{self._port}/SystemSettings/displaySettings/setVUMode?index={index}',
            parseJson=False,
        )

    async def async_mute(self) -> any:
        await self._api_wrapper(
            method='get',
            url=f'http://{self._host}:{self._port}/ZidooMusicControl/v2/setMuteVolume?isMute=1',
            parseJson=False,
        )

    async def async_unmute(self) -> any:
        await self._api_wrapper(
            method='get',
            url=f'http://{self._host}:{self._port}/ZidooMusicControl/v2/setMuteVolume?isMute=0',
            parseJson=False,
        )

    async def async_volume_down(self) -> any:
        await self._api_wrapper(
            method='get',
            url=f'http://{self._host}:{self._port}/ZidooControlCenter/RemoteControl/sendkey?key=Key.VolumeDown',
            parseJson=False,
        )

    async def async_volume_up(self) -> any:
        await self._api_wrapper(
            method='get',
            url=f'http://{self._host}:{self._port}/ZidooControlCenter/RemoteControl/sendkey?key=Key.VolumeUp',
            parseJson=False,
        )

    async def async_toggle_play_pause(self) -> any:
        await self._api_wrapper(
            method='get',
            url=f'http://{self._host}:{self._port}/ZidooMusicControl/v2/playOrPause',
            parseJson=False,
        )

    async def async_previous_title(self) -> any:
        await self._api_wrapper(
            method='get',
            url=f'http://{self._host}:{self._port}/ZidooMusicControl/v2/playLast',
            parseJson=False,
        )

    async def async_next_title(self) -> any:
        await self._api_wrapper(
            method='get',
            url=f'http://{self._host}:{self._port}/ZidooMusicControl/v2/playNext',
            parseJson=False,
        )

    async def async_seek_time(self, time) -> any:
        await self._api_wrapper(
            method='get',
            url=f'http://{self._host}:{self._port}/ZidooMusicControl/v2/seekTo?time={time}',
            parseJson=False,
        )

    async def async_set_volume(self, volume) -> any:
        await self._api_wrapper(
            method='get',
            url=f'http://{self._host}:{self._port}/ZidooMusicControl/v2/setDevicesVolume?volume={volume}',
            parseJson=False,
        )

    async def async_set_input(self, index, tag) -> any:
        await self._api_wrapper(
            method='get',
            url=f'http://{self._host}:{self._port}/ZidooMusicControl/v2/setInputList?tag={tag}&index={index}',
            parseJson=False,
        )

    async def async_set_output(self, index, tag) -> any:
        await self._api_wrapper(
            method='get',
            url=f'http://{self._host}:{self._port}/ZidooMusicControl/v2/setOutInputList?tag={tag}&index={index}',
            parseJson=False,
        )

    def create_internal_image_url(self, song_id) -> any:
        return f'http://{self._host}:{self._port}/ZidooMusicControl/v2/getImage?id={song_id}&target=16'

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
                        'Invalid credentials',
                    )
                response.raise_for_status()
                if parseJson:
                    return await response.json(content_type=None)
                else:
                    return await response.read()

        except asyncio.TimeoutError as exception:
            raise EversoloApiClientCommunicationError(
                'Timeout error fetching information',
            ) from exception
        except (aiohttp.ClientError, socket.gaierror) as exception:
            raise EversoloApiClientCommunicationError(
                'Error fetching information',
            ) from exception
        except Exception as exception:  # pylint: disable=broad-except
            raise EversoloApiClientError(
                'Something really wrong happened!'
            ) from exception
