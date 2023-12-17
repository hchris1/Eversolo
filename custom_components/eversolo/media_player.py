"""Media Player platform for eversolo."""
from __future__ import annotations

import datetime as dt

from homeassistant.components.media_player import (
    MediaPlayerDeviceClass,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
)

from .const import DOMAIN, LOGGER
from .coordinator import EversoloDataUpdateCoordinator
from .entity import EversoloEntity

SUPPORT_FEATURES = (
    MediaPlayerEntityFeature.TURN_OFF
    | MediaPlayerEntityFeature.SELECT_SOURCE
    | MediaPlayerEntityFeature.PLAY
    | MediaPlayerEntityFeature.PAUSE
    | MediaPlayerEntityFeature.VOLUME_SET
    | MediaPlayerEntityFeature.VOLUME_MUTE
    | MediaPlayerEntityFeature.VOLUME_STEP
    | MediaPlayerEntityFeature.PREVIOUS_TRACK
    | MediaPlayerEntityFeature.NEXT_TRACK
    | MediaPlayerEntityFeature.SEEK
)


async def async_setup_entry(hass, entry, async_add_devices):
    """Set up the Media Player platform."""
    coordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_devices([EversoloMediaPlayer(coordinator, entry)])


class EversoloMediaPlayer(EversoloEntity, MediaPlayerEntity):
    """Eversolo Media Player."""

    def __init__(self, coordinator: EversoloDataUpdateCoordinator, config_entry):
        """Initialize the Media Player."""
        super().__init__(coordinator)
        self._attr_device_class = MediaPlayerDeviceClass.RECEIVER
        self._attr_supported_features = SUPPORT_FEATURES
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_media_player"
        self._config_entry = config_entry
        self._name = "Eversolo"
        self._state = None

    @property
    def name(self):
        """Return name."""
        return self._name

    @property
    def state(self):
        """Return Media Player state."""
        music_control_state = self.coordinator.data.get("music_control_state", None)

        if music_control_state is None:
            self._state = None
            return self._state

        state = int(music_control_state.get("state", -1))

        if state == 0:
            self._state = MediaPlayerState.IDLE
        elif state == 3:
            self._state = MediaPlayerState.PLAYING
            self._attr_media_position_updated_at = dt.datetime.now()
        elif state == 4:
            self._state = MediaPlayerState.PAUSED
        else:
            LOGGER.debug("Unknown state: %s", state)
            self._state = None

        return self._state

    @property
    def device_info(self):
        """Return Media Player device info."""
        return {}

    @property
    def volume_level(self):
        """Volume level of the Media Player in range 0..1."""
        music_control_state = self.coordinator.data.get("music_control_state", None)

        if music_control_state is None:
            return None

        current_volume = music_control_state.get("volumeData", {}).get(
            "currenttVolume", None
        )
        max_volume = music_control_state.get("volumeData", {}).get("maxVolume", None)

        if current_volume is None or max_volume is None:
            LOGGER.debug(
                "Current volume or max volume invalid in music control state: %s",
                music_control_state,
            )
            return None

        return float(current_volume) / float(max_volume)

    @property
    def is_volume_muted(self):
        """Return muted state."""
        music_control_state = self.coordinator.data.get("music_control_state", None)

        if music_control_state is None:
            return None

        return music_control_state.get("volumeData", {}).get("isMute", None)

    @property
    def source(self):
        """Return the current input source."""
        input_output_state = self.coordinator.data.get("input_output_state", None)

        if input_output_state is None:
            return None

        sources = self.coordinator.data.get("input_output_state", {}).get(
            "transformed_sources", None
        )

        if sources is None:
            return None

        input_index = input_output_state.get("inputIndex", -1)
        if input_index < 0 or input_index >= len(sources):
            LOGGER.debug("Input index %s is out of range", input_index)
            return None

        return list(sources.values())[input_index]

    @property
    def source_list(self):
        """List of available input sources."""
        # NoneType object has no values
        sources = self.coordinator.data.get("input_output_state", {}).get(
            "transformed_sources", None
        )

        if sources is None:
            return None

        return list(sources.values())

    @property
    def media_title(self):
        """Title of current playing media."""
        music_control_state = self.coordinator.data.get("music_control_state", None)

        if music_control_state is None:
            return None

        play_type = music_control_state.get("playType", None)

        # Bluetooth or Spotify Connect
        if play_type == 4 or play_type == 6:
            return (
                music_control_state.get("everSoloPlayInfo", {})
                .get("everSoloPlayAudioInfo", {})
                .get("songName", None)
            )

        # Internal Player
        if play_type == 5:
            return music_control_state.get("playingMusic", {}).get("title", None)

        return None

    @property
    def media_artist(self):
        """Artist of current playing media."""
        music_control_state = self.coordinator.data.get("music_control_state", None)

        if music_control_state is None:
            return None

        play_type = music_control_state.get("playType", None)

        # Bluetooth or Spotify Connect
        if play_type == 4 or play_type == 6:
            return (
                music_control_state.get("everSoloPlayInfo", {})
                .get("everSoloPlayAudioInfo", {})
                .get("artistName", None)
            )

        # Internal Player
        if play_type == 5:
            return music_control_state.get("playingMusic", {}).get("artist", None)

        return None

    @property
    def media_album_name(self):
        """Album of current playing media."""
        music_control_state = self.coordinator.data.get("music_control_state", None)

        if music_control_state is None:
            return None

        play_type = music_control_state.get("playType", None)

        # Bluetooth or Spotify Connect
        if play_type == 4 or play_type == 6:
            return (
                music_control_state.get("everSoloPlayInfo", {})
                .get("everSoloPlayAudioInfo", {})
                .get("albumName", None)
            )

        # Internal Player
        if play_type == 5:
            return music_control_state.get("playingMusic", {}).get("album", None)

        return None

    @property
    def media_image_url(self):
        """Image url of current playing media."""
        music_control_state = self.coordinator.data.get("music_control_state", None)

        if music_control_state is None:
            return None

        play_type = music_control_state.get("playType", None)

        # Bluetooth or Spotify Connect
        if play_type == 6:
            album_url = music_control_state.get("everSoloPlayInfo", {}).get(
                "icon", None
            )

            if album_url is None or album_url == "":
                return None

            if not album_url.startswith("http"):
                album_url = self.coordinator.client.create_image_url_by_path(album_url)

            return album_url

        # Internal Player
        if play_type == 5:
            song_id = music_control_state.get("playingMusic", {}).get("id", None)
            if song_id is not None:
                return self.coordinator.client.create_image_url_by_song_id(song_id)

        return None

    @property
    def media_duration(self):
        """Duration of current playing media in seconds."""
        music_control_state = self.coordinator.data.get("music_control_state", None)

        if music_control_state is None:
            return None

        duration = music_control_state.get("duration", None)

        if duration is None or duration == 0:
            return None

        return duration / 1000

    @property
    def media_position(self):
        """Position of current playing media in seconds."""
        music_control_state = self.coordinator.data.get("music_control_state", None)

        if music_control_state is None:
            return None

        position = music_control_state.get("position", None)

        if position is None or position == 0:
            return None

        return position / 1000

    async def async_media_seek(self, position: float):
        """Seek the media to a specific location."""
        await self.coordinator.client.async_seek_time(round(position * 1000))
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self):
        """Turn off Media Player."""
        await self.coordinator.client.async_trigger_power_off()
        await self.coordinator.async_request_refresh()

    async def async_set_volume_level(self, volume: float) -> None:
        """Set volume level, range 0..1."""
        music_control_state = self.coordinator.data.get("music_control_state", None)

        if music_control_state is None:
            return

        converted_volume = round(
            volume * int(music_control_state.get("volumeData", {}).get("maxVolume", 0))
        )
        await self.coordinator.client.async_set_volume(converted_volume)
        await self.coordinator.async_request_refresh()

    async def async_volume_up(self):
        """Volume up the Media Player."""
        await self.coordinator.client.async_volume_up()
        await self.coordinator.async_request_refresh()

    async def async_volume_down(self):
        """Volume down Media Player."""
        await self.coordinator.client.async_volume_down()
        await self.coordinator.async_request_refresh()

    async def async_mute_volume(self, mute):
        """Send mute command."""
        await self.coordinator.client.async_mute()
        await self.coordinator.async_request_refresh()

    async def async_select_source(self, source):
        """Set the input source."""
        sources = self.coordinator.data.get("input_output_state", {}).get(
            "transformed_sources", None
        )

        if sources is None:
            return

        try:
            index, tag = next(
                (index, key)
                for index, key in enumerate(sources)
                if sources[key] == source or key == source
            )
        except StopIteration:
            raise ValueError(f"Source {source} not found")

        await self.coordinator.client.async_set_input(index, tag)

    async def async_media_play_pause(self):
        """Simulate play pause Media Player."""
        await self.coordinator.client.async_toggle_play_pause()
        await self.coordinator.async_request_refresh()

    async def async_media_play(self):
        """Send play command."""
        if self._state is not MediaPlayerState.PLAYING:
            await self.coordinator.client.async_toggle_play_pause()
            await self.coordinator.async_request_refresh()

    async def async_media_pause(self):
        """Send pause command."""
        if self._state is MediaPlayerState.PLAYING:
            await self.coordinator.client.async_toggle_play_pause()
            await self.coordinator.async_request_refresh()

    async def async_media_next_track(self):
        """Send next track command."""
        await self.coordinator.client.async_next_title()
        await self.coordinator.async_request_refresh()

    async def async_media_previous_track(self):
        """Send the previous track command."""
        await self.coordinator.client.async_previous_title()
        await self.coordinator.async_request_refresh()
