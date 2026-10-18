# Eversolo for Home Assistant

<p align="center">
  <img src="custom_components/eversolo/brand/logo.png" alt="Eversolo integration" width="420">
</p>

A local-first Home Assistant integration for Eversolo streamers, DACs, transports, and amplifiers.

This fork modernizes the original [hchris1/Eversolo](https://github.com/hchris1/Eversolo) project with a richer media player, capability-driven controls, lower API load, diagnostics, discovery, translations, and local-library browsing.

## Highlights

- One rich media player for playback, volume, mute, seeking, source selection, repeat, shuffle, and power
- `media_player.select_source` switches to hardware inputs, device favorites, local playlists, and installed music apps by name
- Album artwork proxied through Home Assistant
- Audiophile metadata: format, sample rate, bit depth, bitrate, channels, output codec, DSP, EQ, and MQA state
- Browse and play the current queue, favorites, and local playlists
- Launch installed streaming apps and Eversolo's cross-service **My Favorites** view
- Search the Eversolo local music library
- Dynamic input/output lists supplied by the device—nothing is hard-coded per model
- Configurable power-off behavior: full shutdown or standby
- Wake-on-LAN on the Eversolo-documented UDP port, with legacy fallback
- Display brightness, knob brightness, VU style, spectrum style, output, and knob color controls
- Automatic _eversolo._tcp discovery when advertised by the device
- English and French translations
- Redacted diagnostics and bundled light/dark branding

## Compatibility

The integration uses the local HTTP API on port 9529. Capability detection is preferred over model-name checks, so unsupported controls remain hidden or unavailable.

Streaming applications are discovered from the device at runtime. Apple Music, Qobuz, TIDAL, TuneIn, Amazon Music, and other services therefore appear only when installed or exposed by the current firmware. Provider credentials remain on the Eversolo; Home Assistant never receives them.

Community API evidence covers:

- DMP-A6 and DMP-A6 Gen 2 / Master Edition
- DMP-A8
- DMP-A10
- Eversolo Play
- Newer transports and DACs that expose the same Zidoo/Eversolo API family

Hardware and firmware vary. The playback and I/O endpoints are documented by Zidoo; display controls, favorites, playlists, and search are experimental across models. Library endpoints are requested under both `/ZidooMusicControl/v2` and `/MusicControl/v2`, because firmware generations differ, and the prefix that answers is remembered. Please include model, firmware, and diagnostics in bug reports.

## Requirements

- Home Assistant 2026.7.0 or newer
- HACS, or a manual custom-component installation
- The Home Assistant host and Eversolo device must be able to reach each other on the local network
- TCP port 9529 must be reachable locally
- Wake-on-LAN requires the wired MAC address and network support for UDP broadcast

The Eversolo API is unencrypted and normally unauthenticated. Do not expose port 9529 to the internet.

## Installation

### HACS

1. Open HACS.
2. Add https://github.com/TheFab21/Eversolo as a custom integration repository.
3. Install **Eversolo Integration**.
4. Restart Home Assistant.
5. Open **Settings → Devices & services → Add integration → Eversolo**.

### Manual

Copy custom_components/eversolo into the Home Assistant custom_components directory, restart Home Assistant, and add the integration from the UI.

## Main entity

The media player is the primary control surface. It provides:

- play, pause, next, previous, seek
- volume, step volume, mute and unmute
- dynamic input selection, extended with favorites, playlists, and music apps
- repeat one, repeat all, and shuffle
- power off, configurable standby, and Wake-on-LAN
- artwork and detailed audio attributes
- queue, favorites, playlists, and search in the Home Assistant media browser

The legacy command buttons keep their existing unique IDs for automation compatibility. Redundant power and screen buttons are disabled by default on new installations; they can be enabled from the entity registry.

## Selecting favorites

Hardware inputs, the play queue, the device favorites, local playlists, and installed music apps share one source list, the way the Sonos and HEOS integrations expose their favorites. A dashboard or script can therefore start a favorite by name:

    action: media_player.select_source
    target:
      entity_id: media_player.eversolo
    data:
      source: Radio Paradise

On the internet-radio source the queue is where the stations live — the firmware exposes no favorites endpoint for them — so a station is selected by the title the device gives it.

Names are matched ignoring case and surrounding spaces, and an input can also be selected by its device tag. When a name is unknown, the error lists the sources the device currently offers. Favorites that the firmware does not expose over HTTP cannot be selected; the probe below reports what a given device serves.

## Options and reconfiguration

Open the integration menu to:

- change the device host or API port without deleting the integration
- choose whether media_player.turn_off powers down or enters standby

Standby is used only when the device advertises support. Otherwise, the integration safely falls back to full shutdown.

## Diagnostics

Download diagnostics from the integration or device page before reporting a bug. Host addresses and MAC addresses are redacted automatically.

Useful report details:

- Eversolo model
- firmware version
- playback source that was active
- whether the issue concerns playback, I/O, display controls, or library browsing
- a short reproduction sequence

## Probing the device API

Eversolo does not publish its control API, so a firmware may serve endpoints this integration does not use yet. The bundled probe reports which ones answer:

    python3 scripts/probe_eversolo_api.py 192.168.1.50 --output eversolo-api.json

Start an internet-radio favorite on the device first: the playback state then shows the identifiers the firmware reports for a station. Only read-only endpoints are requested, and file-browser endpoints are skipped because they can echo stored share credentials. Review the report before attaching it to an issue.

## Development

Install the current development environment and run the checks:

    python -m pip install -r requirements.txt
    python -m ruff check .
    python -m ruff format --check .
    python -m pytest

The client limits concurrent requests to two. Playback state is polled every two seconds; slower settings are refreshed every thirty seconds or immediately after a related command.

Brand images are generated reproducibly with:

    python scripts/generate_brand.py

## API references

- [Official Eversolo developer page](https://eversolo.com/Support/developer/)
- [Official Eversolo TCP command sheet](https://music.eversolo.com/dmp/instruction/Eversolo_DMP-A6_TCP_en_v1.0.pdf)
- [Official Zidoo network API](https://apidoc.zidoo.tv/)
- [Community Eversolo SDK](https://github.com/tomekceszke/eversolo-sdk)
- [Community API research](https://github.com/Amandrs/eversolo_tui)

## Credits

Created by [Christian](https://github.com/hchris1) and modernized in the [TheFab21 fork](https://github.com/TheFab21/Eversolo). All product names and trademarks belong to their respective owners.
