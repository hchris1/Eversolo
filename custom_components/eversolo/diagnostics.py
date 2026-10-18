"""Diagnostics support for Eversolo."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers.redact import async_redact_data

from .const import CONF_NET_MAC
from .coordinator import EversoloDataUpdateCoordinator

TO_REDACT = {CONF_HOST, CONF_NET_MAC, "net_mac", "wif_mac", "ip"}


async def async_get_config_entry_diagnostics(
    _hass: HomeAssistant,
    entry: ConfigEntry[EversoloDataUpdateCoordinator],
) -> dict[str, Any]:
    """Return a redacted diagnostic snapshot."""
    coordinator = entry.runtime_data
    playback = coordinator.data.get("music_control_state") or {}
    volume = playback.get("volumeData") or {}
    state_summary = {
        "state": playback.get("state"),
        "play_type": playback.get("playType"),
        "loop_mode": playback.get("loopModel"),
        "has_queue": playback.get("hasPlayQueue"),
        "has_play_mode": playback.get("hasPlayMode"),
        "has_favorites": playback.get("hasFavor"),
        "dsp_active": playback.get("dspActive"),
        "eq_active": playback.get("eqActive"),
        "volume": {
            "minimum": volume.get("minVolume"),
            "maximum": volume.get("maxVolume"),
            "muted": volume.get("isMute"),
            "enabled": volume.get("isVolumeEnable"),
            "locked": volume.get("isLock"),
        },
    }
    io_state = coordinator.data.get("input_output_state") or {}
    library = {
        "inputs": [
            {"title": source.get("title"), "tag": source.get("tag")}
            for source in io_state.get("transformed_sources") or []
        ],
        "input_index": io_state.get("inputIndex"),
        "favorites": [
            favorite.get("title") or favorite.get("name")
            for favorite in coordinator.data.get("favorites") or []
        ],
        "playlists": [
            playlist.get("name") or playlist.get("title")
            for playlist in coordinator.data.get("song_lists") or []
        ],
        "apps": [
            app.get("label") for app in coordinator.data.get("streaming_apps") or []
        ],
    }
    return async_redact_data(
        {
            "entry": {
                "title": entry.title,
                "version": entry.version,
                "data": dict(entry.data),
                "options": dict(entry.options),
            },
            "coordinator": coordinator.diagnostics_summary,
            "state": state_summary,
            "library": library,
        },
        TO_REDACT,
    )
