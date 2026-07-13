"""Asynchronous client for the local Eversolo/Zidoo HTTP API."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Mapping
import json
import socket
from typing import Any

import aiohttp
from yarl import URL

from .const import LOGGER

API_TIMEOUT = aiohttp.ClientTimeout(total=5)
MAX_CONCURRENT_REQUESTS = 2
FAVORITES_APP_PACKAGE = "com.eversolo.mycollection.app"
APP_FRIENDLY_NAMES = {
    "com.amazon.mp3": "Amazon Music",
    "com.apple.android.music": "Apple Music",
    "com.aspiro.tidal": "TIDAL",
    "com.audials": "Audials Play",
    "com.bbc.sounds": "BBC Sounds",
    "com.earthflare.anddroid.radioparadisewidget": "Radio Paradise",
    "com.eversolo.mycollection.app": "My Favorites",
    "com.prestomusic.app": "Presto Music",
    "com.qobuz.music": "Qobuz",
    "com.rhapsody.napster": "Napster",
    "com.spotify.music": "Spotify",
    "com.tunein.player": "TuneIn Radio",
    "com.yuriy.openradio": "Open Radio",
    "deezer.android.app": "Deezer",
    "net.programmierecke.radiodroid2": "RadioDroid 2",
}
MUSIC_APP_HINTS = (
    "amazon music",
    "apple music",
    "calm radio",
    "deezer",
    "favorite",
    "highresaudio",
    "idagio",
    "kkbox",
    "music",
    "presto",
    "qobuz",
    "radio paradise",
    "soundcloud",
    "sony",
    "spotify",
    "tidal",
    "tunein",
)


class EversoloApiClientError(Exception):
    """Base exception for Eversolo API failures."""


class EversoloApiClientCommunicationError(EversoloApiClientError):
    """Raised when the device cannot be reached."""


class EversoloApiClientAuthenticationError(EversoloApiClientError):
    """Raised when the device rejects authentication."""


class EversoloApiClientResponseError(EversoloApiClientError):
    """Raised when the device returns an invalid response."""


class EversoloApiClientUnsupportedError(EversoloApiClientError):
    """Raised when a model or firmware does not support an endpoint."""


class EversoloApiClient:
    """Communicate with an Eversolo device over its local HTTP API."""

    def __init__(
        self,
        host: str,
        port: int,
        session: aiohttp.ClientSession,
    ) -> None:
        """Initialize the client."""
        self._host = host
        self._port = port
        self._session = session
        self._request_semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)

    @property
    def host(self) -> str:
        """Return the configured host."""
        return self._host

    @property
    def port(self) -> int:
        """Return the configured port."""
        return self._port

    def _url(self, path: str) -> URL:
        """Build a safe local API URL, including IPv6 hosts."""
        return URL.build(scheme="http", host=self._host, port=self._port).with_path(
            path
        )

    async def async_get_music_control_state(self) -> dict[str, Any]:
        """Return the complete real-time playback state."""
        return await self._request_json("/ZidooMusicControl/v2/getState")

    async def async_get_settings_data(
        self, previous_data: Mapping[str, Any] | None = None
    ) -> dict[str, Any]:
        """Fetch slower-changing settings without failing the real-time poll."""
        previous = dict(previous_data or {})
        fetchers: dict[str, Callable[[], Awaitable[Any]]] = {
            "display_brightness": self.async_get_display_brightness,
            "input_output_state": self.async_get_input_output_state,
            "knob_brightness": self.async_get_knob_brightness,
            "vu_mode_state": self.async_get_vu_mode_state,
            "spectrum_mode_state": self.async_get_spectrum_state,
            "power_options": self.async_get_power_options,
            "streaming_apps": self.async_get_streaming_apps,
        }

        results = await asyncio.gather(
            *(fetcher() for fetcher in fetchers.values()),
            return_exceptions=True,
        )
        updated = previous
        for (key, _fetcher), result in zip(fetchers.items(), results, strict=True):
            if isinstance(result, EversoloApiClientUnsupportedError):
                LOGGER.debug("Endpoint for %s is not supported", key)
                updated.pop(key, None)
            elif isinstance(result, EversoloApiClientError):
                LOGGER.debug("Could not refresh %s: %s", key, result)
            elif isinstance(result, Exception):
                LOGGER.exception(
                    "Unexpected error while refreshing %s", key, exc_info=result
                )
            else:
                updated[key] = result

        try:
            if await self.async_has_knob_color():
                updated["knob_color_state"] = await self.async_get_knob_color_state()
            else:
                updated.pop("knob_color_state", None)
        except EversoloApiClientError as err:
            LOGGER.debug("Could not refresh knob color support: %s", err)

        updated["is_display_on"] = self.extract_is_screen_on(
            updated.get("power_options", {})
        )
        return updated

    @staticmethod
    def transform_sources(
        input_output_state: Mapping[str, Any],
    ) -> list[dict[str, Any]]:
        """Normalize inputs while preserving the device-provided tag and index."""
        return [
            {
                "index": int(source.get("index", index)),
                "title": str(
                    source.get("name") or source.get("title") or source.get("tag")
                ),
                "tag": str(source.get("tag", "")),
            }
            for index, source in enumerate(input_output_state.get("inputData") or [])
            if isinstance(source, Mapping) and source.get("tag")
        ]

    @staticmethod
    def transform_outputs(
        input_output_state: Mapping[str, Any],
    ) -> list[dict[str, Any]]:
        """Normalize enabled outputs without renumbering their device index."""
        return [
            {
                "index": int(output.get("index", index)),
                "title": str(
                    output.get("name") or output.get("title") or output.get("tag")
                ),
                "tag": str(output.get("tag", "")),
            }
            for index, output in enumerate(input_output_state.get("outputData") or [])
            if isinstance(output, Mapping)
            and output.get("tag")
            and bool(output.get("enable", True))
        ]

    async def async_get_input_output_state(self) -> dict[str, Any]:
        """Return inputs, outputs, and the current selections."""
        result = await self._request_json("/ZidooMusicControl/v2/getInputAndOutputList")
        result["transformed_sources"] = self.transform_sources(result)
        result["transformed_outputs"] = self.transform_outputs(result)
        return result

    async def async_get_vu_mode_state(self) -> dict[str, Any]:
        """Return the available VU display modes."""
        return await self._request_json("/SystemSettings/displaySettings/getVUModeList")

    async def async_get_spectrum_state(self) -> dict[str, Any]:
        """Return the available spectrum display modes."""
        return await self._request_json(
            "/SystemSettings/displaySettings/getSpPlayModeList"
        )

    async def async_get_power_options(self) -> dict[str, Any]:
        """Return power actions supported by the device."""
        return await self._request_json("/ZidooMusicControl/v2/getPowerOption")

    @staticmethod
    def extract_is_screen_on(power_options: Mapping[str, Any]) -> bool | None:
        """Infer screen state from the action exposed by current firmware."""
        screen_option = next(
            (
                item
                for item in power_options.get("data") or []
                if isinstance(item, Mapping) and item.get("tag") == "screen"
            ),
            None,
        )
        if not screen_option:
            return None

        for key in ("isOn", "isOpen", "enabled", "checked"):
            if key in screen_option:
                return bool(screen_option[key])

        action_name = str(screen_option.get("name", "")).casefold()
        turn_off_labels = (
            "screen off",
            "turn off screen",
            "bildschirm aus",
            "éteindre l'écran",
            "ecran éteint",
            "tela desligada",
            "关闭屏幕",
            "關閉螢幕",
            "画面をオフ",
        )
        if any(label in action_name for label in turn_off_labels):
            return True
        return None

    async def async_get_display_brightness(self) -> int | None:
        """Return display brightness in Home Assistant's 0..255 range."""
        result = await self._request_json(
            "/SystemSettings/displaySettings/getScreenBrightness"
        )
        value = result.get("currentValue")
        return None if value is None else round(int(value) * (255 / 115))

    async def async_set_display_brightness(self, value: int) -> None:
        """Set display brightness from Home Assistant's 0..255 range."""
        brightness = round(max(0, min(255, value)) * (115 / 255))
        await self._request_bytes(
            "/SystemSettings/displaySettings/setScreenBrightness",
            {"index": brightness},
        )

    async def async_get_knob_brightness(self) -> int | None:
        """Return knob brightness in the 0..255 range."""
        result = await self._request_json(
            "/SystemSettings/displaySettings/getKnobBrightness"
        )
        value = result.get("currentValue")
        return None if value is None else max(0, min(255, int(value)))

    async def async_set_knob_brightness(self, value: int) -> None:
        """Set knob brightness."""
        await self._request_bytes(
            "/SystemSettings/displaySettings/setKnobBrightness",
            {"index": max(0, min(255, value))},
        )

    async def async_trigger_reboot(self) -> None:
        """Reboot the device."""
        await self.async_set_power_option("reboot")

    async def async_trigger_power_off(self) -> None:
        """Power off the device."""
        await self.async_set_power_option("poweroff")

    async def async_trigger_standby(self) -> None:
        """Put the device in standby."""
        await self.async_set_power_option("standby")

    async def async_set_power_option(self, tag: str) -> None:
        """Run a device power action by tag."""
        await self._request_bytes("/ZidooMusicControl/v2/setPowerOption", {"tag": tag})

    async def async_trigger_toggle_screen(self) -> None:
        """Toggle the screen."""
        await self.async_set_power_option("screen")

    async def async_trigger_turn_screen_on(self) -> None:
        """Turn the screen on."""
        await self.async_send_key("Key.Screen.ON")

    async def async_trigger_turn_screen_off(self) -> None:
        """Turn the screen off."""
        await self.async_send_key("Key.Screen.OFF")

    async def async_send_key(self, key: str) -> None:
        """Send a documented remote-control key."""
        await self._request_bytes(
            "/ZidooControlCenter/RemoteControl/sendkey", {"key": key}
        )

    async def async_trigger_cycle_screen_mode(
        self, should_show_spectrum: bool = False
    ) -> None:
        """Cycle the front-panel visualization mode."""
        await self._request_bytes(
            "/ZidooMusicControl/v2/changVUDisplay",
            {"openType": int(should_show_spectrum)},
        )

    async def async_select_vu_mode_option(self, index: int, _tag: str) -> None:
        """Select a VU meter style."""
        await self._request_bytes(
            "/SystemSettings/displaySettings/setVUMode", {"index": index}
        )

    async def async_select_spectrum_mode_option(self, index: int, _tag: str) -> None:
        """Select a spectrum style."""
        await self._request_bytes(
            "/SystemSettings/displaySettings/setSpPlayModeList", {"index": index}
        )

    async def async_has_knob_color(self) -> bool:
        """Return whether knob color control is advertised by the device."""
        try:
            result = await self._request_json(
                "/SystemSettings/displaySettings/getKnobSettingOption"
            )
        except EversoloApiClientUnsupportedError:
            return False
        return any(
            isinstance(item, Mapping)
            and item.get("tag") == "SettingsItemTagKnobLightColorList"
            for item in result.get("items") or []
        )

    async def async_get_knob_color_state(self) -> dict[str, Any]:
        """Return knob colors and the current selection."""
        result = await self._request_json(
            "/SystemSettings/displaySettings/getKnobLightColorList"
        )
        if "data" not in result and isinstance(result.get("items"), list):
            result["data"] = result["items"]
        return result

    async def async_select_knob_color_option(self, index: int, _tag: str) -> None:
        """Select the knob light color."""
        await self._request_bytes(
            "/SystemSettings/displaySettings/setKnobLightColor", {"index": index}
        )

    async def async_set_mute(self, mute: bool) -> None:
        """Set mute state."""
        await self._request_bytes(
            "/ZidooMusicControl/v2/setMuteVolume", {"isMute": int(mute)}
        )

    async def async_mute(self) -> None:
        """Mute output."""
        await self.async_set_mute(True)

    async def async_unmute(self) -> None:
        """Unmute output."""
        await self.async_set_mute(False)

    async def async_volume_down(self) -> None:
        """Decrease volume by one hardware step."""
        await self.async_send_key("Key.VolumeDown")

    async def async_volume_up(self) -> None:
        """Increase volume by one hardware step."""
        await self.async_send_key("Key.VolumeUp")

    async def async_toggle_play_pause(self) -> None:
        """Toggle play/pause."""
        await self._request_bytes("/ZidooMusicControl/v2/playOrPause")

    async def async_previous_title(self) -> None:
        """Play the previous queue item."""
        await self._request_bytes("/ZidooMusicControl/v2/playLast")

    async def async_next_title(self) -> None:
        """Play the next queue item."""
        await self._request_bytes("/ZidooMusicControl/v2/playNext")

    async def async_seek_time(self, time_ms: int) -> None:
        """Seek to a position in milliseconds."""
        await self._request_bytes(
            "/ZidooMusicControl/v2/seekTo", {"time": max(0, time_ms)}
        )

    async def async_set_volume(self, volume: int) -> None:
        """Set the device volume."""
        await self._request_bytes(
            "/ZidooMusicControl/v2/setDevicesVolume", {"volume": max(0, volume)}
        )

    async def async_set_input(self, index: int, tag: str) -> None:
        """Set an input using values returned by the device."""
        await self._request_bytes(
            "/ZidooMusicControl/v2/setInputList", {"tag": tag, "index": index}
        )

    async def async_set_output(self, index: int, tag: str) -> None:
        """Set an output using values returned by the device."""
        await self._request_bytes(
            "/ZidooMusicControl/v2/setOutInputList", {"tag": tag, "index": index}
        )

    async def async_set_loop_mode(self, mode: int) -> None:
        """Set repeat/shuffle mode."""
        await self._request_bytes("/ZidooMusicControl/v2/setLoopMode", {"mode": mode})

    async def async_get_device_model(self) -> dict[str, Any]:
        """Fetch device identity and feature flags across firmware variants."""
        last_error: EversoloApiClientError | None = None
        for path in (
            "/ZidooControlCenter/connect",
            "/ZidooControlCenter/getModel",
            "/ControlCenter/getModel",
        ):
            try:
                return await self._request_json(path)
            except (
                EversoloApiClientResponseError,
                EversoloApiClientUnsupportedError,
            ) as err:
                last_error = err
        raise last_error or EversoloApiClientResponseError(
            "No device information endpoint succeeded"
        )

    async def async_get_play_queue(self) -> list[dict[str, Any]]:
        """Return the current play queue."""
        return await self._request_items("/ZidooMusicControl/v2/getPlayQueue")

    async def async_play_queue_item(self, index: int) -> None:
        """Play a queue item by index."""
        await self._request_bytes(
            "/ZidooMusicControl/v2/playQueueMusic", {"index": index}
        )

    async def async_get_favorites(self) -> list[dict[str, Any]]:
        """Return local-library favorite tracks."""
        return await self._request_items(
            "/ZidooMusicControl/v2/getFavorites",
            {"start": 0, "count": 200, "sort": 0},
        )

    async def async_get_song_lists(self) -> list[dict[str, Any]]:
        """Return local playlists."""
        return await self._request_items("/ZidooMusicControl/v2/getSongLists")

    async def async_get_song_list_musics(
        self, playlist_id: str | int
    ) -> list[dict[str, Any]]:
        """Return tracks in a local playlist."""
        return await self._request_items(
            "/ZidooMusicControl/v2/getSongListMusics",
            {"id": playlist_id, "start": 0, "count": 500, "sort": 0},
        )

    async def async_search_music(self, query: str) -> list[dict[str, Any]]:
        """Search the local music library."""
        return await self._request_items(
            "/ZidooMusicControl/v2/searchMusicV2",
            {"key": query, "start": 0, "count": 100},
        )

    async def async_get_streaming_apps(self) -> list[dict[str, Any]]:
        """Return installed music applications across firmware generations."""
        results = await asyncio.gather(
            self._request_items(
                "/ZidooMusicControl/v2/getStreamMediaAppList",
                {"start": 0, "count": 100, "showMusicApp": "true", "sort": 4},
            ),
            self._request_items("/ControlCenter/Apps/getApps"),
            self._request_items("/ZidooControlCenter/Apps/getApps"),
            return_exceptions=True,
        )
        normalized: dict[str, dict[str, Any]] = {}
        errors: list[EversoloApiClientError] = []
        for source_index, result in enumerate(results):
            if isinstance(result, EversoloApiClientError):
                errors.append(result)
                continue
            if isinstance(result, Exception):
                raise result
            for app in result:
                package_name = str(
                    app.get("packageName")
                    or app.get("package")
                    or app.get("package_name")
                    or ""
                )
                label = str(
                    app.get("label")
                    or app.get("appName")
                    or app.get("name")
                    or package_name
                )
                if not package_name or not label or app.get("isCanOpen") is False:
                    continue
                searchable = f"{label} {package_name}".casefold()
                is_streaming_result = source_index == 0
                is_favorites = package_name == FAVORITES_APP_PACKAGE
                is_music_app = package_name.casefold() in APP_FRIENDLY_NAMES or any(
                    hint in searchable for hint in MUSIC_APP_HINTS
                )
                if not (is_streaming_result or is_favorites or is_music_app):
                    continue
                label = self._friendly_app_label(label, package_name)
                normalized[package_name] = {
                    **normalized.get(package_name, {}),
                    **app,
                    "label": label,
                    "packageName": package_name,
                    "isFavorites": is_favorites,
                }

        if not normalized and len(errors) == len(results):
            raise errors[0]
        return sorted(
            normalized.values(),
            key=lambda app: (
                not bool(app.get("isFavorites")),
                str(app["label"]).casefold(),
            ),
        )

    @staticmethod
    def _friendly_app_label(label: str, package_name: str) -> str:
        """Replace raw Android package identifiers with readable app names."""
        mapped = APP_FRIENDLY_NAMES.get(package_name.casefold())
        if mapped:
            return mapped
        if label.casefold() != package_name.casefold() and "." not in label:
            return label
        useful_parts = [
            part
            for part in package_name.split(".")
            if part.casefold()
            not in {"android", "app", "application", "com", "music", "net"}
        ]
        return (
            (useful_parts[-1] if useful_parts else package_name)
            .replace("_", " ")
            .title()
        )

    async def async_open_app(self, package_name: str) -> None:
        """Open an installed application on the Eversolo display."""
        last_error: EversoloApiClientError | None = None
        opened = False
        for path in (
            "/ZidooControlCenter/Apps/openApp",
            "/ControlCenter/Apps/openApp",
        ):
            try:
                await self._request_bytes(path, {"packageName": package_name})
                opened = True
            except EversoloApiClientError as err:
                last_error = err
        if opened:
            return
        raise last_error or EversoloApiClientResponseError(
            "No application-launch endpoint succeeded"
        )

    async def async_play_library_item(
        self,
        item: Mapping[str, Any],
        *,
        context_id: str | int | None = None,
        track_index: int = 0,
    ) -> None:
        """Play a local-library item using identifiers returned by the device."""
        music_id = item.get("musicId", item.get("id"))
        if music_id is None:
            raise EversoloApiClientResponseError("Library item has no music identifier")
        item_type = int(item.get("musicType", item.get("type", 1)))
        await self._request_bytes(
            "/ZidooMusicControl/v2/playMusic",
            {
                "type": int(item.get("type", item_type)),
                "id": context_id if context_id is not None else music_id,
                "musicId": music_id,
                "musicType": item_type,
                "trackIndex": track_index,
                "sort": 0,
            },
        )

    def create_image_url_by_song_id(self, song_id: str | int) -> str:
        """Create a local album-art URL for an internal-library track."""
        return str(
            self._url("/ZidooMusicControl/v2/getImage").with_query(
                {"id": song_id, "target": 16}
            )
        )

    def create_image_url_by_path(self, path: str) -> str:
        """Create a local image URL from a device-provided path."""
        base = URL.build(scheme="http", host=self._host, port=self._port)
        return str(base.join(URL(path)))

    async def async_get_app_icon(
        self, package_name: str
    ) -> tuple[bytes | None, str | None]:
        """Fetch an installed application's icon across firmware variants."""
        last_error: EversoloApiClientError | None = None
        for path in (
            "/ControlCenter/Apps/getAppIcon",
            "/ZidooControlCenter/Apps/getAppIcon",
        ):
            try:
                return await self._request_raw(
                    self._url(path), {"packageName": package_name}
                )
            except EversoloApiClientError as err:
                last_error = err
        raise last_error or EversoloApiClientResponseError(
            "No application-icon endpoint succeeded"
        )

    async def async_get_image(self, url: str) -> tuple[bytes | None, str | None]:
        """Fetch a device-hosted image for Home Assistant's artwork proxy."""
        parsed = URL(url)
        expected = URL.build(scheme="http", host=self._host, port=self._port)
        if parsed.host != expected.host or parsed.port != expected.port:
            raise EversoloApiClientResponseError("Refusing to fetch a non-device URL")
        data, content_type = await self._request_raw(parsed)
        return data, content_type

    @staticmethod
    def _extract_items(
        response: Mapping[str, Any] | list[Any],
    ) -> list[dict[str, Any]]:
        """Extract collection items from firmware-specific response wrappers."""
        if isinstance(response, list):
            return [dict(item) for item in response if isinstance(item, Mapping)]
        for key in (
            "array",
            "items",
            "musics",
            "apps",
            "appList",
            "appData",
            "data",
            "list",
            "result",
        ):
            value = response.get(key)
            if isinstance(value, list):
                return [dict(item) for item in value if isinstance(item, Mapping)]
            if isinstance(value, Mapping):
                nested = EversoloApiClient._extract_items(value)
                if nested:
                    return nested
        return []

    async def _request_items(
        self, path: str, params: Mapping[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        """Return collection items from an object wrapper or a root JSON array."""
        return self._extract_items(await self._request_json_value(path, params))

    async def _request_json(
        self, path: str, params: Mapping[str, Any] | None = None
    ) -> dict[str, Any]:
        """Run a GET request and validate its JSON object response."""
        decoded = await self._request_json_value(path, params)
        if not isinstance(decoded, dict):
            raise EversoloApiClientResponseError(
                f"Device returned a non-object response for {path}"
            )
        return decoded

    async def _request_json_value(
        self, path: str, params: Mapping[str, Any] | None = None
    ) -> dict[str, Any] | list[Any]:
        """Run a GET request and accept firmware JSON objects or arrays."""
        raw, _content_type = await self._request_raw(self._url(path), params)
        try:
            decoded = json.loads(raw)
        except (UnicodeDecodeError, json.JSONDecodeError) as err:
            raise EversoloApiClientResponseError(
                f"Device returned invalid JSON for {path}"
            ) from err
        if not isinstance(decoded, (dict, list)):
            raise EversoloApiClientResponseError(
                f"Device returned an unsupported JSON response for {path}"
            )
        if isinstance(decoded, dict):
            self._raise_for_device_status(decoded)
        return decoded

    async def _request_bytes(
        self, path: str, params: Mapping[str, Any] | None = None
    ) -> bytes:
        """Run a GET command and return its raw response."""
        raw, content_type = await self._request_raw(self._url(path), params)
        if (content_type and "json" in content_type) or raw.lstrip().startswith(b"{"):
            try:
                decoded = json.loads(raw)
            except UnicodeDecodeError:
                return raw
            except json.JSONDecodeError:
                return raw
            if isinstance(decoded, dict):
                self._raise_for_device_status(decoded)
        return raw

    async def _request_raw(
        self, url: URL, params: Mapping[str, Any] | None = None
    ) -> tuple[bytes, str | None]:
        """Run a bounded, timed local HTTP GET request."""
        try:
            async with (
                self._request_semaphore,
                self._session.get(url, params=params, timeout=API_TIMEOUT) as response,
            ):
                if response.status in (401, 403):
                    raise EversoloApiClientAuthenticationError(
                        "Device rejected authentication"
                    )
                response.raise_for_status()
                return await response.read(), response.content_type
        except EversoloApiClientError:
            raise
        except TimeoutError as err:
            raise EversoloApiClientCommunicationError(
                f"Timed out contacting {self._host}:{self._port}"
            ) from err
        except (aiohttp.ClientError, socket.gaierror) as err:
            raise EversoloApiClientCommunicationError(
                f"Could not contact {self._host}:{self._port}"
            ) from err

    @staticmethod
    def _raise_for_device_status(response: Mapping[str, Any]) -> None:
        """Map firmware status codes to stable integration exceptions."""
        status = response.get("status")
        if status in (None, 200, "200"):
            return
        message = str(response.get("msg") or response.get("message") or "")
        try:
            code = int(status)
        except (TypeError, ValueError) as err:
            raise EversoloApiClientResponseError(
                f"Unexpected device status {status!r}"
            ) from err
        if code in (405, 804):
            raise EversoloApiClientUnsupportedError(
                f"Endpoint unsupported by this model or firmware ({code}): {message}"
            )
        if code in (401, 403):
            raise EversoloApiClientAuthenticationError(
                message or "Authentication failed"
            )
        raise EversoloApiClientResponseError(
            f"Device returned status {code}: {message or 'unknown error'}"
        )
