"""Tests for the asynchronous Eversolo client."""

from __future__ import annotations

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import sys
from types import ModuleType
from unittest.mock import AsyncMock

import pytest

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "custom_components" / "eversolo"


def _load_api_module():
    """Load the API module without importing Home Assistant integration setup."""
    package_name = "_eversolo_api_tests"
    package = ModuleType(package_name)
    package.__path__ = [str(PACKAGE)]
    sys.modules[package_name] = package

    for module_name in ("const", "api"):
        qualified = f"{package_name}.{module_name}"
        spec = spec_from_file_location(qualified, PACKAGE / f"{module_name}.py")
        assert spec and spec.loader
        module = module_from_spec(spec)
        sys.modules[qualified] = module
        spec.loader.exec_module(module)

    api = sys.modules[f"{package_name}.api"]
    del sys.modules[package_name]
    del sys.modules[f"{package_name}.const"]
    del sys.modules[f"{package_name}.api"]
    return api


api = _load_api_module()


@pytest.fixture
def client():
    """Return a client whose transport can be mocked."""
    return api.EversoloApiClient("192.168.1.50", 9529, AsyncMock())


def test_transform_sources_preserves_device_indices(client) -> None:
    """Input tags and indexes must never be synthesized."""
    assert client.transform_sources(
        {
            "inputData": [
                {"tag": "XMOS", "name": "Internal", "index": 4},
                {"tag": "RCA/A", "name": "Line in", "index": 9},
            ]
        }
    ) == [
        {"tag": "XMOS", "title": "Internal", "index": 4},
        {"tag": "RCA/A", "title": "Line in", "index": 9},
    ]


def test_transform_outputs_filters_without_renumbering(client) -> None:
    """Disabled outputs must not shift indexes used by commands."""
    assert client.transform_outputs(
        {
            "outputData": [
                {"tag": "XLR", "name": "Balanced", "enable": True, "index": 2},
                {"tag": "USB", "name": "USB", "enable": False, "index": 3},
                {"tag": "RCA", "name": "Analog", "enable": 1, "index": 7},
            ]
        }
    ) == [
        {"tag": "XLR", "title": "Balanced", "index": 2},
        {"tag": "RCA", "title": "Analog", "index": 7},
    ]


@pytest.mark.parametrize(
    ("response", "expected"),
    [
        ({"data": [{"tag": "screen", "isOn": False}]}, False),
        ({"data": [{"tag": "screen", "name": "Screen off"}]}, True),
        ({"data": [{"tag": "standby", "name": "Standby"}]}, None),
    ],
)
def test_extract_screen_state(client, response, expected) -> None:
    """Screen state handles flags, localized action labels, and unknown data."""
    assert client.extract_is_screen_on(response) is expected


def test_extract_items_handles_firmware_wrappers(client) -> None:
    """Collections may be wrapped under several firmware-specific keys."""
    assert client._extract_items([{"id": 0}]) == [{"id": 0}]
    assert client._extract_items({"data": {"array": [{"id": 1}]}}) == [{"id": 1}]
    assert client._extract_items({"items": [{"id": 2}]}) == [{"id": 2}]
    assert client._extract_items({"data": "invalid"}) == []


@pytest.mark.parametrize(
    ("status", "error"),
    [
        (405, api.EversoloApiClientUnsupportedError),
        (804, api.EversoloApiClientUnsupportedError),
        (401, api.EversoloApiClientAuthenticationError),
        (805, api.EversoloApiClientResponseError),
        ("bad", api.EversoloApiClientResponseError),
    ],
)
def test_device_status_errors(client, status, error) -> None:
    """Device status codes map to stable exception types."""
    with pytest.raises(error):
        client._raise_for_device_status({"status": status, "msg": "failure"})


def test_success_statuses_are_accepted(client) -> None:
    """Firmware responses may omit status or serialize it as a string."""
    client._raise_for_device_status({})
    client._raise_for_device_status({"status": 200})
    client._raise_for_device_status({"status": "200"})


@pytest.mark.asyncio
async def test_device_info_endpoint_fallback(client) -> None:
    """Older firmware identity endpoints are tried after modern ones."""
    client._request_json = AsyncMock(
        side_effect=[
            api.EversoloApiClientUnsupportedError(),
            api.EversoloApiClientUnsupportedError(),
            {"model": "DMP-A6"},
        ]
    )
    assert await client.async_get_device_model() == {"model": "DMP-A6"}
    assert client._request_json.await_count == 3


@pytest.mark.asyncio
async def test_device_info_endpoint_fallback_after_malformed_response(client) -> None:
    """A broken legacy endpoint must not prevent trying the next variant."""
    client._request_json = AsyncMock(
        side_effect=[
            api.EversoloApiClientResponseError(),
            {"model": "DMP-A8"},
        ]
    )
    assert await client.async_get_device_model() == {"model": "DMP-A8"}
    assert client._request_json.await_count == 2


@pytest.mark.asyncio
async def test_settings_refresh_tolerates_optional_endpoints(client) -> None:
    """A missing cosmetic endpoint must not make the player unavailable."""
    client.async_get_display_brightness = AsyncMock(return_value=120)
    client.async_get_input_output_state = AsyncMock(return_value={"inputData": []})
    client.async_get_knob_brightness = AsyncMock(
        side_effect=api.EversoloApiClientUnsupportedError()
    )
    client.async_get_vu_mode_state = AsyncMock(return_value={"data": []})
    client.async_get_spectrum_state = AsyncMock(return_value={"data": []})
    client.async_get_power_options = AsyncMock(
        return_value={"data": [{"tag": "screen", "name": "Screen off"}]}
    )
    client.async_get_streaming_apps = AsyncMock(return_value=[])
    client.async_has_knob_color = AsyncMock(return_value=False)

    result = await client.async_get_settings_data({"knob_brightness": 33})

    assert result["display_brightness"] == 120
    assert result["is_display_on"] is True
    assert "knob_brightness" not in result


@pytest.mark.asyncio
async def test_input_output_normalization(client) -> None:
    """The I/O response is enriched in one place."""
    client._request_json = AsyncMock(
        return_value={
            "inputData": [{"tag": "XMOS", "name": "Internal", "index": 4}],
            "outputData": [{"tag": "RCA", "name": "Analog", "index": 7}],
        }
    )
    result = await client.async_get_input_output_state()
    assert result["transformed_sources"][0]["index"] == 4
    assert result["transformed_outputs"][0]["index"] == 7


@pytest.mark.asyncio
async def test_library_endpoints_and_play_command(client) -> None:
    """Library collection wrappers and playback parameters remain consistent."""
    client._request_json_value = AsyncMock(return_value={"array": [{"id": 42}]})
    client._request_bytes = AsyncMock(return_value=b"")

    assert await client.async_get_favorites() == [{"id": 42}]
    assert await client.async_get_song_lists() == [{"id": 42}]
    assert await client.async_get_song_list_musics(8) == [{"id": 42}]
    assert await client.async_search_music("jazz") == [{"id": 42}]
    assert await client.async_get_play_queue() == [{"id": 42}]

    await client.async_play_library_item(
        {"id": 42, "type": 1}, context_id=8, track_index=3
    )
    _, params = client._request_bytes.await_args.args
    assert params == {
        "type": 1,
        "id": 8,
        "musicId": 42,
        "musicType": 1,
        "trackIndex": 3,
        "sort": 0,
    }


@pytest.mark.asyncio
async def test_song_lists_accepts_root_json_array(client) -> None:
    """DMP-A6 firmware may return playlists as a root JSON array."""
    client._request_raw = AsyncMock(
        return_value=(b'[{"id": 42, "name": "Favorites"}]', "application/json")
    )

    assert await client.async_get_song_lists() == [{"id": 42, "name": "Favorites"}]


@pytest.mark.asyncio
async def test_streaming_apps_include_music_and_favorites(client) -> None:
    """Application discovery combines streaming and installed-app endpoints."""
    client._request_json_value = AsyncMock(
        side_effect=[
            {
                "data": [
                    {
                        "appName": "com.qobuz.music",
                        "packageName": "com.qobuz.music",
                        "isCanOpen": True,
                    }
                ]
            },
            {
                "apps": [
                    {
                        "label": "My Favorites",
                        "packageName": "com.eversolo.mycollection.app",
                        "isCanOpen": True,
                        "isSystemApp": True,
                    },
                    {
                        "label": "Apple Music",
                        "packageName": "com.apple.android.music",
                        "isCanOpen": True,
                    },
                    {
                        "label": "Chrome",
                        "packageName": "com.android.chrome",
                        "isCanOpen": True,
                    },
                ]
            },
            api.EversoloApiClientUnsupportedError(),
        ]
    )

    apps = await client.async_get_streaming_apps()

    assert [app["label"] for app in apps] == [
        "My Favorites",
        "Apple Music",
        "Qobuz",
    ]


@pytest.mark.asyncio
async def test_open_app_uses_structured_package_parameter(client) -> None:
    """Application package names are sent as encoded query parameters."""
    client._request_bytes = AsyncMock(return_value=b"")

    await client.async_open_app("com.apple.android.music")

    assert [call.args for call in client._request_bytes.await_args_list] == [
        (
            "/ZidooControlCenter/Apps/openApp",
            {"packageName": "com.apple.android.music"},
        ),
        (
            "/ControlCenter/Apps/openApp",
            {"packageName": "com.apple.android.music"},
        ),
    ]


@pytest.mark.asyncio
async def test_open_app_falls_back_to_newer_control_center(client) -> None:
    """One successful control-center endpoint is enough to launch an app."""
    client._request_bytes = AsyncMock(
        side_effect=[api.EversoloApiClientUnsupportedError(), b""]
    )

    await client.async_open_app("com.qobuz.music")

    assert client._request_bytes.await_args_list[1].args[0] == (
        "/ControlCenter/Apps/openApp"
    )


@pytest.mark.parametrize(
    ("package_name", "expected"),
    [
        ("com.amazon.mp3", "Amazon Music"),
        ("com.apple.android.music", "Apple Music"),
        ("com.qobuz.music", "Qobuz"),
        ("com.spotify.music", "Spotify"),
        ("deezer.android.app", "Deezer"),
        ("org.example.super_radio", "Super Radio"),
    ],
)
def test_friendly_app_labels(client, package_name, expected) -> None:
    """Known and unknown Android packages receive readable labels."""
    assert client._friendly_app_label(package_name, package_name) == expected


@pytest.mark.asyncio
async def test_control_commands_use_structured_parameters(client) -> None:
    """Control values are passed as query parameters, not interpolated URLs."""
    client._request_bytes = AsyncMock(return_value=b"")
    await client.async_set_mute(False)
    await client.async_set_input(9, "RCA/A")
    await client.async_set_output(7, "XLR/RCA")
    await client.async_set_loop_mode(2)
    await client.async_seek_time(-10)
    await client.async_set_volume(140)
    await client.async_send_key("Key.MediaPlay")
    await client.async_play_queue_item(4)

    calls = client._request_bytes.await_args_list
    assert calls[0].args[1] == {"isMute": 0}
    assert calls[1].args[1] == {"tag": "RCA/A", "index": 9}
    assert calls[2].args[1] == {"tag": "XLR/RCA", "index": 7}
    assert calls[4].args[1] == {"time": 0}


def test_artwork_urls_and_host_validation(client) -> None:
    """Artwork helpers keep requests pinned to the configured device."""
    assert "id=12" in client.create_image_url_by_song_id(12)
    assert (
        client.create_image_url_by_path("/art.jpg")
        == "http://192.168.1.50:9529/art.jpg"
    )
    assert (
        client.create_image_url_by_path("/ZidooMusicControl/v2/getImage?id=12")
        == "http://192.168.1.50:9529/ZidooMusicControl/v2/getImage?id=12"
    )


@pytest.mark.asyncio
async def test_image_proxy_rejects_other_hosts(client) -> None:
    """The artwork proxy cannot be abused as an arbitrary LAN fetcher."""
    with pytest.raises(api.EversoloApiClientResponseError):
        await client.async_get_image("http://192.168.1.99/private")


@pytest.mark.asyncio
async def test_brightness_conversion_and_clamping(client) -> None:
    """Brightness conversion follows the device's documented ranges."""
    client._request_json = AsyncMock(return_value={"currentValue": 115})
    client._request_bytes = AsyncMock(return_value=b"")
    assert await client.async_get_display_brightness() == 255
    assert await client.async_get_knob_brightness() == 115
    await client.async_set_display_brightness(999)
    await client.async_set_knob_brightness(-1)
    assert client._request_bytes.await_args_list[0].args[1] == {"index": 115}
    assert client._request_bytes.await_args_list[1].args[1] == {"index": 0}
