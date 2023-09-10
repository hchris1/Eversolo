"""Support for Onkyo Receivers."""
from __future__ import annotations


from homeassistant.components.media_player import (
    MediaPlayerDeviceClass,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
)

from .const import DOMAIN
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
)

AVAILABLE_SOURCES = {
    'XMOS': 'Internal Player',
    'BT': 'Bluetooth',
    'USB': 'USB-C',
    'SPDIF': 'SPDIF',
    'RCA': 'Coaxial',
}


async def async_setup_entry(hass, entry, async_add_devices):
    """Set up the sensor platform."""
    coordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_devices([EversoloMediaPlayer(coordinator, entry)])


class EversoloMediaPlayer(EversoloEntity, MediaPlayerEntity):
    """Eversolo media player."""

    def __init__(self, coordinator: EversoloDataUpdateCoordinator, config_entry):
        """Initialize the media player."""
        super().__init__(coordinator)
        self._attr_device_class = MediaPlayerDeviceClass.RECEIVER
        self._attr_supported_features = SUPPORT_FEATURES
        self._attr_unique_id = f'{coordinator.config_entry.entry_id}_media_player'
        self._config_entry = config_entry
        self._name = 'Eversolo'
        self._state = None

    @property
    def name(self):
        return self._name

    @property
    def state(self):
        music_control_state = self.coordinator.data.get('music_control_state', None)

        if music_control_state is None:
            self._state = None
            return self._state

        if int(music_control_state['state']) == 0:
            self._state = MediaPlayerState.IDLE
        elif int(music_control_state['state']) == 3:
            self._state = MediaPlayerState.PLAYING
        elif int(music_control_state['state']) == 4:
            self._state = MediaPlayerState.PAUSED
        else:
            self._state = None

        return self._state

    @property
    def device_info(self):
        return {}

    @property
    def volume_level(self):
        """Volume level of the media player (0..1)."""
        music_control_state = self.coordinator.data.get('music_control_state', None)

        if music_control_state is None:
            return None

        return float(music_control_state['volumeData']['currenttVolume']) / float(
            music_control_state['volumeData']['maxVolume']
        )

    @property
    def is_volume_muted(self):
        music_control_state = self.coordinator.data.get('music_control_state', None)

        if music_control_state is None:
            return None

        return music_control_state['volumeData']['isMute']

    @property
    def source(self):
        """Return the current input source."""
        input_output_state = self.coordinator.data.get('input_output_state', None)

        if input_output_state is None:
            return None

        return list(AVAILABLE_SOURCES.values())[input_output_state['inputIndex']]

    @property
    def source_list(self):
        """List of available input sources."""
        return list(AVAILABLE_SOURCES.values())

    @property
    def media_title(self):
        """Title of current playing media."""
        music_control_state = self.coordinator.data.get('music_control_state', None)

        if music_control_state is None:
            return None

        # Bluetooth or Spotify Connect
        if music_control_state['playType'] == 4 or music_control_state['playType'] == 6:
            return music_control_state['everSoloPlayInfo']['everSoloPlayAudioInfo'][
                'songName'
            ]

        # Internal Player
        if music_control_state['playType'] == 5:
            return music_control_state['playingMusic']['title']

        return None

    @property
    def media_artist(self):
        """Artist of current playing media."""
        music_control_state = self.coordinator.data.get('music_control_state', None)

        if music_control_state is None:
            return None

        # Bluetooth or Spotify Connect
        if music_control_state['playType'] == 4 or music_control_state['playType'] == 6:
            return music_control_state['everSoloPlayInfo']['everSoloPlayAudioInfo'][
                'artistName'
            ]

        # Internal Player
        if music_control_state['playType'] == 5:
            return music_control_state['playingMusic']['artist']

        return None

    @property
    def media_album_name(self):
        """Album of current playing media."""
        music_control_state = self.coordinator.data.get('music_control_state', None)

        if music_control_state is None:
            return None

        # Bluetooth or Spotify Connect
        if music_control_state['playType'] == 4 or music_control_state['playType'] == 6:
            return music_control_state['everSoloPlayInfo']['everSoloPlayAudioInfo'][
                'albumName'
            ]

        # Internal Player
        if music_control_state['playType'] == 5:
            return music_control_state['playingMusic']['album']

        return None

    @property
    def media_image_url(self):
        """Image url of current playing media."""
        music_control_state = self.coordinator.data.get('music_control_state', None)

        if music_control_state is None:
            return None

        # Bluetooth or Spotify Connect
        if music_control_state['playType'] == 6:
            return music_control_state['everSoloPlayInfo']['everSoloPlayAudioInfo'][
                'albumUrl'
            ].replace('\\/', '/')

        # Internal Player
        if music_control_state['playType'] == 5:
            return self.coordinator.client.create_internal_image_url(
                music_control_state['playingMusic']['id']
            )

        return None

    @property
    def media_duration(self):
        """Duration of current playing media in seconds."""
        music_control_state = self.coordinator.data.get('music_control_state', None)

        if music_control_state is None:
            return None

        position = music_control_state['duration']

        if position == 0:
            return None
        return position

    @property
    def media_position(self):
        """Position of current playing media in seconds."""
        music_control_state = self.coordinator.data.get('music_control_state', None)

        if music_control_state is None:
            return None

        position = music_control_state['position']

        if position == 0:
            return None
        return position

    async def async_turn_off(self):
        """Turn off media player."""
        await self.coordinator.client.async_trigger_power_off()
        await self.coordinator.async_request_refresh()

    async def async_set_volume_level(self, volume: float) -> None:
        """Set volume level, range 0..1."""
        music_control_state = self.coordinator.data.get('music_control_state', None)

        if music_control_state is None:
            return

        converted_volume = round(
            volume * int(music_control_state['volumeData']['maxVolume'])
        )
        await self.coordinator.client.async_set_volume(converted_volume)
        await self.coordinator.async_request_refresh()

    async def async_volume_up(self):
        """Volume up the media player."""
        await self.coordinator.client.async_volume_up()
        await self.coordinator.async_request_refresh()

    async def async_volume_down(self):
        """Volume down media player."""
        await self.coordinator.client.async_volume_down()
        await self.coordinator.async_request_refresh()

    async def async_mute_volume(self, mute):
        """Send mute command."""
        await self.coordinator.client.async_mute()
        await self.coordinator.async_request_refresh()

    async def async_select_source(self, source):
        """Set the input source."""
        index = 0
        for key, value in AVAILABLE_SOURCES.items():
            if value == source:
                await self.coordinator.client.async_set_input(index, key)
                break
            index += 1

    async def async_media_play_pause(self):
        """Simulate play pause media player."""
        await self.coordinator.client.async_toggle_play_pause()
        await self.coordinator.async_request_refresh()

    async def async_media_play(self):
        """Send play command."""
        if self._state is not MediaPlayerState.PLAYING:
            await self.coordinator.client.async_toggle_play_pause()
            await self.coordinator.async_request_refresh()

    async def async_media_pause(self):
        """Send media pause command."""
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
