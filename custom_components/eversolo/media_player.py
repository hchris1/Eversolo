"""Media player platform for Eversolo."""

from __future__ import annotations

from collections.abc import Mapping
from html import escape
import json
from typing import Any

from homeassistant.components.media_player import (
    BrowseError,
    BrowseMedia,
    MediaClass,
    MediaPlayerDeviceClass,
    MediaPlayerEnqueue,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
    MediaType,
    RepeatMode,
    SearchMedia,
    SearchMediaQuery,
    SearchError,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .api import EversoloApiClientError
from .coordinator import EversoloDataUpdateCoordinator
from .entity import EversoloEntity

BASE_FEATURES = (
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
    | MediaPlayerEntityFeature.REPEAT_SET
    | MediaPlayerEntityFeature.SHUFFLE_SET
    | MediaPlayerEntityFeature.BROWSE_MEDIA
    | MediaPlayerEntityFeature.SEARCH_MEDIA
    | MediaPlayerEntityFeature.PLAY_MEDIA
)

APP_ICON_STYLES = {
    "com.amazon.mp3": ("#00A8E1", "AM"),
    "com.apple.android.music": ("#FA243C", "♫"),
    "com.aspiro.tidal": ("#111111", "T"),
    "com.audials": ("#F26A21", "A"),
    "com.bbc.sounds": ("#F54997", "BBC"),
    "com.earthflare.anddroid.radioparadisewidget": ("#111111", "RP"),
    "com.eversolo.mycollection.app": ("#E33F50", "♥"),
    "com.prestomusic.app": ("#6F3FA0", "P"),
    "com.qobuz.music": ("#0070EF", "Q"),
    "com.rhapsody.napster": ("#2856FF", "N"),
    "com.spotify.music": ("#1DB954", "S"),
    "com.tunein.player": ("#14D8CC", "TI"),
    "com.yuriy.openradio": ("#617187", "OR"),
    "deezer.android.app": ("#A238FF", "D"),
    "net.programmierecke.radiodroid2": ("#EA4335", "R"),
}


async def async_setup_entry(
    _hass: HomeAssistant,
    entry: ConfigEntry[EversoloDataUpdateCoordinator],
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Eversolo media player."""
    async_add_entities([EversoloMediaPlayer(entry.runtime_data)])


class EversoloMediaPlayer(EversoloEntity, MediaPlayerEntity):
    """Expose an Eversolo streamer as one rich Home Assistant media player."""

    _attr_device_class = MediaPlayerDeviceClass.RECEIVER
    _attr_name = None
    _attr_media_content_type = MediaType.MUSIC
    _attr_media_image_remotely_accessible = False

    def __init__(self, coordinator: EversoloDataUpdateCoordinator) -> None:
        """Initialize the media player."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_media_player"

    @property
    def supported_features(self) -> MediaPlayerEntityFeature:
        """Return features supported by the current device."""
        features = BASE_FEATURES
        if self.coordinator.can_wake:
            features |= MediaPlayerEntityFeature.TURN_ON
        return features

    @property
    def available(self) -> bool:
        """Keep an offline player available only when Home Assistant can wake it."""
        return self.coordinator.can_wake or super().available

    @property
    def state(self) -> MediaPlayerState | None:
        """Return playback state."""
        if not self.coordinator.last_update_success:
            return MediaPlayerState.OFF if self.coordinator.can_wake else None
        raw = self._playback.get("state")
        try:
            state = int(raw)
        except TypeError:
            return MediaPlayerState.ON
        except ValueError:
            return MediaPlayerState.ON
        if state in (0, 1):
            return MediaPlayerState.IDLE
        if state == 3:
            return MediaPlayerState.PLAYING
        if state == 4:
            return MediaPlayerState.PAUSED
        return MediaPlayerState.ON

    @property
    def _playback(self) -> dict[str, Any]:
        """Return cached playback state."""
        return self.coordinator.data.get("music_control_state") or {}

    @property
    def _playing_music(self) -> dict[str, Any]:
        """Return cached local-library metadata."""
        return self._playback.get("playingMusic") or {}

    @property
    def _play_info(self) -> dict[str, Any]:
        """Return cached source-specific metadata."""
        return self._playback.get("everSoloPlayInfo") or {}

    @property
    def _audio_info(self) -> dict[str, Any]:
        """Return cached generic audio metadata."""
        return self._play_info.get("everSoloPlayAudioInfo") or {}

    @property
    def volume_level(self) -> float | None:
        """Return normalized volume."""
        volume = self._playback.get("volumeData") or {}
        current = volume.get("currenttVolume")
        maximum = volume.get("maxVolume")
        if current is None or not maximum:
            return None
        return max(0.0, min(1.0, float(current) / float(maximum)))

    @property
    def is_volume_muted(self) -> bool | None:
        """Return mute state."""
        return (self._playback.get("volumeData") or {}).get("isMute")

    @property
    def source(self) -> str | None:
        """Return the active input name using the device index."""
        io_state = self.coordinator.data.get("input_output_state") or {}
        sources = io_state.get("inputData") or []
        index = io_state.get("inputIndex")
        if isinstance(index, int) and 0 <= index < len(sources):
            source = sources[index]
            if isinstance(source, Mapping):
                return str(source.get("name") or source.get("tag"))
        return None

    @property
    def source_list(self) -> list[str] | None:
        """Return available input names."""
        sources = (self.coordinator.data.get("input_output_state") or {}).get(
            "transformed_sources"
        ) or []
        return [str(source["title"]) for source in sources] or None

    @property
    def media_title(self) -> str | None:
        """Return current title across local and streamed playback."""
        return self._metadata_value("title", "songName", "audioTitle")

    @property
    def media_artist(self) -> str | None:
        """Return current artist."""
        return self._metadata_value("artist", "artistName", "audioArtist")

    @property
    def media_album_name(self) -> str | None:
        """Return current album."""
        return self._metadata_value("album", "albumName", "audioAlbum")

    def _metadata_value(
        self, local_key: str, audio_key: str, bt_key: str
    ) -> str | None:
        """Read metadata from firmware-specific structures."""
        value = self._playing_music.get(local_key) or self._audio_info.get(audio_key)
        if not value:
            value = (self._play_info.get("everSoloBtInInfo") or {}).get(bt_key)
        return str(value) if value else None

    @property
    def media_image_url(self) -> str | None:
        """Return a device-local artwork URL for Home Assistant to proxy."""
        album_url = self._play_info.get("icon") or self._playing_music.get("albumArt")
        if album_url:
            album_url = str(album_url)
            if album_url.startswith("http"):
                return album_url
            return self.coordinator.client.create_image_url_by_path(album_url)
        song_id = self._playing_music.get("id")
        if song_id is not None:
            return self.coordinator.client.create_image_url_by_song_id(song_id)
        return None

    @property
    def media_duration(self) -> float | None:
        """Return duration in seconds."""
        duration = self._playback.get("duration")
        return float(duration) / 1000 if duration else None

    @property
    def media_position(self) -> float | None:
        """Return position in seconds."""
        position = self._playback.get("position")
        return float(position) / 1000 if position is not None else None

    @property
    def media_position_updated_at(self):
        """Return the UTC timestamp of the last real-time update."""
        if self.state is MediaPlayerState.PLAYING:
            return self.coordinator.last_realtime_update
        return None

    @property
    def media_track(self) -> int | None:
        """Return one-based queue position."""
        index = self._playback.get("trackIndex")
        return index + 1 if isinstance(index, int) and index >= 0 else None

    @property
    def repeat(self) -> RepeatMode:
        """Return repeat mode."""
        mode = self._playback.get("loopModel")
        if mode == 1:
            return RepeatMode.ONE
        if mode == 0:
            return RepeatMode.ALL
        return RepeatMode.OFF

    @property
    def shuffle(self) -> bool:
        """Return whether queue shuffle is active."""
        return self._playback.get("loopModel") == 2

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose useful audiophile metadata without creating entity clutter."""
        output = self._play_info.get("everSoloPlayOutputInfo") or {}
        volume = self._playback.get("volumeData") or {}
        attributes = {
            "audio_format": self._playing_music.get("extension"),
            "sample_rate": self._playing_music.get("sampleRate"),
            "bit_depth": self._playing_music.get("bits"),
            "bitrate": self._playing_music.get("bitrate"),
            "channels": self._playing_music.get("channels"),
            "output_codec": output.get("outPutDecodec"),
            "output_sample_rate": output.get("outPutSampleRate"),
            "output_bit_depth": output.get("outPutBits"),
            "volume_display": volume.get("display"),
            "playback_source": self._play_info.get("playTypeSubtitle"),
            "dsp_active": self._playback.get("dspActive"),
            "eq_active": self._playback.get("eqActive"),
            "mqa_mode": self._playback.get("mqaMode"),
        }
        return {key: value for key, value in attributes.items() if value is not None}

    async def async_media_seek(self, position: float) -> None:
        """Seek to a position."""
        await self.coordinator.client.async_seek_time(round(position * 1000))
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self) -> None:
        """Power off or enter standby according to the integration option."""
        await self.coordinator.async_power_off()

    async def async_turn_on(self) -> None:
        """Wake the device."""
        await self.coordinator.async_send_wol()

    async def async_set_volume_level(self, volume: float) -> None:
        """Set normalized volume."""
        maximum = int((self._playback.get("volumeData") or {}).get("maxVolume", 200))
        await self.coordinator.client.async_set_volume(round(volume * maximum))
        await self.coordinator.async_request_refresh()

    async def async_volume_up(self) -> None:
        """Increase volume."""
        await self.coordinator.client.async_volume_up()
        await self.coordinator.async_request_refresh()

    async def async_volume_down(self) -> None:
        """Decrease volume."""
        await self.coordinator.client.async_volume_down()
        await self.coordinator.async_request_refresh()

    async def async_mute_volume(self, mute: bool) -> None:
        """Mute or unmute."""
        await self.coordinator.client.async_set_mute(mute)
        await self.coordinator.async_request_refresh()

    async def async_select_source(self, source: str) -> None:
        """Select an input by its device-provided tag and index."""
        sources = (self.coordinator.data.get("input_output_state") or {}).get(
            "transformed_sources"
        ) or []
        selected = next(
            (
                item
                for item in sources
                if source in (str(item.get("title")), str(item.get("tag")))
            ),
            None,
        )
        if selected is None:
            raise HomeAssistantError(
                translation_domain="eversolo",
                translation_key="source_not_found",
                translation_placeholders={"source": source},
            )
        await self.coordinator.client.async_set_input(
            int(selected["index"]), str(selected["tag"])
        )
        await self.coordinator.async_refresh_settings()

    async def async_media_play_pause(self) -> None:
        """Toggle play/pause."""
        await self.coordinator.client.async_toggle_play_pause()
        await self.coordinator.async_request_refresh()

    async def async_media_play(self) -> None:
        """Resume playback."""
        if self.state is not MediaPlayerState.PLAYING:
            await self.async_media_play_pause()

    async def async_media_pause(self) -> None:
        """Pause playback."""
        if self.state is MediaPlayerState.PLAYING:
            await self.async_media_play_pause()

    async def async_media_next_track(self) -> None:
        """Play next track."""
        await self.coordinator.client.async_next_title()
        await self.coordinator.async_request_refresh()

    async def async_media_previous_track(self) -> None:
        """Play previous track."""
        await self.coordinator.client.async_previous_title()
        await self.coordinator.async_request_refresh()

    async def async_set_repeat(self, repeat: RepeatMode | str) -> None:
        """Set repeat mode."""
        mode = {RepeatMode.OFF: 3, RepeatMode.ONE: 1, RepeatMode.ALL: 0}.get(
            RepeatMode(repeat), 3
        )
        await self.coordinator.client.async_set_loop_mode(mode)
        await self.coordinator.async_request_refresh()

    async def async_set_shuffle(self, shuffle: bool) -> None:
        """Enable or disable shuffle."""
        await self.coordinator.client.async_set_loop_mode(2 if shuffle else 0)
        await self.coordinator.async_request_refresh()

    async def async_browse_media(
        self,
        media_content_type: str | None = None,
        media_content_id: str | None = None,
    ) -> BrowseMedia:
        """Browse queue, favorites, and local playlists."""
        del media_content_type
        try:
            request = self._decode_media_id(media_content_id)
            kind = request.get("kind", "root")
            if kind == "favorites":
                return self._tracks_browser(
                    "Favorites",
                    "favorites",
                    await self.coordinator.client.async_get_favorites(),
                )
            if kind == "queue":
                return self._tracks_browser(
                    "Play queue",
                    "queue",
                    await self.coordinator.client.async_get_play_queue(),
                )
            if kind == "apps":
                return self._apps_browser(
                    await self.coordinator.client.async_get_streaming_apps()
                )
            if kind == "playlists":
                return self._playlists_browser(
                    await self.coordinator.client.async_get_song_lists()
                )
            if kind == "playlist":
                playlist_id = request["id"]
                tracks = await self.coordinator.client.async_get_song_list_musics(
                    playlist_id
                )
                return self._tracks_browser(
                    str(request.get("title", "Playlist")),
                    "playlist_track",
                    tracks,
                    context_id=playlist_id,
                )
        except (EversoloApiClientError, KeyError, TypeError, ValueError) as err:
            raise BrowseError(f"Could not browse Eversolo library: {err}") from err
        return self._root_browser()

    async def async_search_media(self, query: SearchMediaQuery) -> SearchMedia:
        """Search the local Eversolo library."""
        if (
            query.media_filter_classes
            and MediaClass.MUSIC not in query.media_filter_classes
        ):
            return SearchMedia(result=[])
        try:
            tracks = await self.coordinator.client.async_search_music(
                query.search_query
            )
        except EversoloApiClientError as err:
            raise SearchError(f"Could not search Eversolo library: {err}") from err
        return SearchMedia(
            result=[
                self._track_item("library_track", track, index)
                for index, track in enumerate(tracks)
            ]
        )

    async def async_play_media(
        self,
        media_type: str,
        media_id: str,
        enqueue: MediaPlayerEnqueue | None = None,
        announce: bool | None = None,
        **kwargs: Any,
    ) -> None:
        """Play a queue, favorite, search, or playlist item."""
        del media_type, enqueue, announce, kwargs
        request = self._decode_media_id(media_id)
        try:
            if request.get("kind") == "app":
                await self.coordinator.client.async_open_app(request["package_name"])
            elif request.get("kind") == "queue_track":
                await self.coordinator.client.async_play_queue_item(
                    int(request["index"])
                )
            elif request.get("kind") == "playlist":
                tracks = await self.coordinator.client.async_get_song_list_musics(
                    request["id"]
                )
                if not tracks:
                    raise HomeAssistantError("The selected Eversolo playlist is empty")
                await self.coordinator.client.async_play_library_item(
                    tracks[0], context_id=request["id"], track_index=0
                )
            else:
                await self.coordinator.client.async_play_library_item(
                    request["item"],
                    context_id=request.get("context_id"),
                    track_index=int(request.get("index", 0)),
                )
        except (EversoloApiClientError, KeyError, TypeError, ValueError) as err:
            raise HomeAssistantError(f"Could not play Eversolo media: {err}") from err
        await self.coordinator.async_request_refresh()

    async def async_get_browse_image(
        self,
        media_content_type: str,
        media_content_id: str,
        media_image_id: str | None = None,
    ) -> tuple[bytes | None, str | None]:
        """Proxy local album art without accepting arbitrary URLs."""
        del media_content_type, media_content_id
        if media_image_id is None:
            return None, None
        if media_image_id.startswith("{"):
            image_request = self._decode_media_id(media_image_id)
            if image_request.get("kind") == "app_icon":
                package_name = str(image_request.get("package_name") or "")
                title = str(image_request.get("title") or package_name or "App")
                if package_name in APP_ICON_STYLES:
                    return self._generated_app_icon(package_name, title)
                icon_path = str(image_request.get("path") or "")
                if icon_path.startswith("/"):
                    try:
                        return await self.coordinator.client.async_get_image(
                            self.coordinator.client.create_image_url_by_path(icon_path)
                        )
                    except EversoloApiClientError:
                        pass
                if package_name:
                    try:
                        return await self.coordinator.client.async_get_app_icon(
                            package_name
                        )
                    except EversoloApiClientError:
                        pass
                return self._generated_app_icon(package_name, title)
        if media_image_id.startswith("app:"):
            package_name = media_image_id.removeprefix("app:")
            if not package_name:
                return None, None
            return await self.coordinator.client.async_get_app_icon(package_name)
        if media_image_id.startswith("path:"):
            icon_path = media_image_id.removeprefix("path:")
            if not icon_path:
                return None, None
            icon_url = (
                icon_path
                if icon_path.startswith(("http://", "https://"))
                else self.coordinator.client.create_image_url_by_path(icon_path)
            )
            return await self.coordinator.client.async_get_image(icon_url)
        if not media_image_id.isdigit():
            return None, None
        return await self.coordinator.client.async_get_image(
            self.coordinator.client.create_image_url_by_song_id(media_image_id)
        )

    def _root_browser(self) -> BrowseMedia:
        """Return the Eversolo library root."""
        return BrowseMedia(
            media_class=MediaClass.APP,
            media_content_id=self._encode_media_id({"kind": "root"}),
            media_content_type="eversolo",
            title="Eversolo",
            can_play=False,
            can_expand=True,
            can_search=True,
            children=[
                BrowseMedia(
                    media_class=MediaClass.DIRECTORY,
                    media_content_id=self._encode_media_id({"kind": kind}),
                    media_content_type="eversolo",
                    title=title,
                    can_play=False,
                    can_expand=True,
                )
                for kind, title in (
                    ("apps", "Music apps & service favorites"),
                    ("favorites", "Favorites"),
                    ("playlists", "Playlists"),
                    ("queue", "Play queue"),
                )
            ],
        )

    def _apps_browser(self, apps: list[dict[str, Any]]) -> BrowseMedia:
        """Return installed streaming applications and Eversolo favorites."""
        children = []
        for app in apps:
            package_name = str(app.get("packageName") or "")
            if not package_name:
                continue
            media_id = self._encode_media_id(
                {"kind": "app", "package_name": package_name}
            )
            icon_path = next(
                (
                    str(app[key])
                    for key in (
                        "icon",
                        "iconUrl",
                        "iconPath",
                        "appIcon",
                        "logo",
                        "image",
                    )
                    if app.get(key)
                ),
                None,
            )
            children.append(
                BrowseMedia(
                    media_class=MediaClass.MUSIC,
                    media_content_id=media_id,
                    media_content_type=MediaType.MUSIC,
                    title=str(app.get("label") or package_name),
                    can_play=True,
                    can_expand=False,
                    thumbnail=self.get_browse_image_url(
                        MediaType.MUSIC,
                        media_id,
                        self._encode_media_id(
                            {
                                "kind": "app_icon",
                                "package_name": package_name,
                                "title": str(app.get("label") or package_name),
                                "path": icon_path,
                            }
                        ),
                    ),
                )
            )
        return BrowseMedia(
            media_class=MediaClass.DIRECTORY,
            media_content_id=self._encode_media_id({"kind": "apps"}),
            media_content_type="eversolo",
            title="Music apps & service favorites",
            can_play=False,
            can_expand=True,
            children=children,
        )

    @staticmethod
    def _generated_app_icon(package_name: str, title: str) -> tuple[bytes, str]:
        """Create a clean deterministic fallback icon without external requests."""
        color, glyph = APP_ICON_STYLES.get(
            package_name,
            ("#34495E", "".join(word[:1] for word in title.split()[:2]).upper() or "♪"),
        )
        font_size = 92 if len(glyph) <= 2 else 64
        svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="256" height="256" viewBox="0 0 256 256">
<rect width="256" height="256" rx="48" fill="{color}"/>
<circle cx="128" cy="128" r="84" fill="#ffffff" fill-opacity="0.12"/>
<text x="128" y="151" text-anchor="middle" font-family="Arial, sans-serif" font-size="{font_size}" font-weight="700" fill="#ffffff">{escape(glyph)}</text>
</svg>"""
        return svg.encode(), "image/svg+xml"

    def _playlists_browser(self, playlists: list[dict[str, Any]]) -> BrowseMedia:
        """Return a playlist directory."""
        children = []
        for playlist in playlists:
            playlist_id = playlist.get("id", playlist.get("songListId"))
            if playlist_id is None:
                continue
            title = str(playlist.get("name") or playlist.get("title") or playlist_id)
            children.append(
                BrowseMedia(
                    media_class=MediaClass.PLAYLIST,
                    media_content_id=self._encode_media_id(
                        {"kind": "playlist", "id": playlist_id, "title": title}
                    ),
                    media_content_type=MediaType.PLAYLIST,
                    title=title,
                    can_play=True,
                    can_expand=True,
                )
            )
        return BrowseMedia(
            media_class=MediaClass.DIRECTORY,
            media_content_id=self._encode_media_id({"kind": "playlists"}),
            media_content_type="eversolo",
            title="Playlists",
            can_play=False,
            can_expand=True,
            children=children,
        )

    def _tracks_browser(
        self,
        title: str,
        kind: str,
        tracks: list[dict[str, Any]],
        *,
        context_id: str | int | None = None,
    ) -> BrowseMedia:
        """Return a track directory."""
        return BrowseMedia(
            media_class=MediaClass.DIRECTORY,
            media_content_id=self._encode_media_id(
                {"kind": "playlist", "id": context_id, "title": title}
                if context_id is not None
                else {"kind": kind}
            ),
            media_content_type="eversolo",
            title=title,
            can_play=False,
            can_expand=True,
            children=[
                self._track_item(kind, track, index, context_id=context_id)
                for index, track in enumerate(tracks)
            ],
        )

    def _track_item(
        self,
        kind: str,
        track: dict[str, Any],
        index: int,
        *,
        context_id: str | int | None = None,
    ) -> BrowseMedia:
        """Build a playable media-browser track."""
        song_id = track.get("musicId", track.get("id"))
        media_id = (
            {"kind": "queue_track", "index": index}
            if kind == "queue"
            else {
                "kind": "library_track",
                "item": track,
                "index": index,
                "context_id": context_id,
            }
        )
        title = str(track.get("title") or track.get("name") or f"Track {index + 1}")
        artist = track.get("artist") or track.get("artistName")
        if artist:
            title = f"{title} — {artist}"
        return BrowseMedia(
            media_class=MediaClass.MUSIC,
            media_content_id=self._encode_media_id(media_id),
            media_content_type=MediaType.MUSIC,
            title=title,
            can_play=True,
            can_expand=False,
            thumbnail=(
                self.get_browse_image_url(
                    MediaType.MUSIC,
                    self._encode_media_id(media_id),
                    str(song_id),
                )
                if song_id is not None and str(song_id).isdigit()
                else None
            ),
        )

    @staticmethod
    def _encode_media_id(value: Mapping[str, Any]) -> str:
        """Encode a self-contained media browser identifier."""
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))

    @staticmethod
    def _decode_media_id(media_id: str | None) -> dict[str, Any]:
        """Decode a media browser identifier."""
        if not media_id:
            return {"kind": "root"}
        decoded = json.loads(media_id)
        if not isinstance(decoded, dict):
            raise TypeError("Invalid media identifier")
        return decoded
