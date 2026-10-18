#!/usr/bin/env python3
"""Probe an Eversolo device and report which HTTP endpoints its firmware serves.

Eversolo does not publish its control API, so the integration has to know which
endpoints a given firmware answers before it can expose favorites or internet
radio stations. Run this on any machine that can reach the streamer:

    python3 scripts/probe_eversolo_api.py 172.22.22.238 --output eversolo-api.json

Start an internet-radio favorite on the device first: the playback state then
shows which identifiers the firmware reports for a station.

Only read-only endpoints are requested, and file-browser endpoints are skipped
because they can echo stored share credentials. Review the report before
sharing it.

The script uses the standard library only and runs on Python 3.9 or newer.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import ProxyHandler, build_opener

# The streamer is on the local network, so ignore any proxy in the environment.
OPENER = build_opener(ProxyHandler({}))

LIBRARY_PREFIXES = ("/ZidooMusicControl/v2", "/MusicControl/v2")
LIST_PARAMS = {"start": 0, "count": 20, "sort": 0}

# Endpoints the integration relies on today.
KNOWN_ENDPOINTS: tuple[tuple[str, dict[str, Any]], ...] = (
    ("/ZidooMusicControl/v2/getState", {}),
    ("/ZidooMusicControl/v2/getInputAndOutputList", {}),
    ("/ControlCenter/getModel", {}),
    ("/SystemSettings/getSystemSettings", {}),
    ("/ControlCenter/Apps/getApps", {}),
    ("/ZidooControlCenter/Apps/getApps", {}),
    (
        "/ZidooMusicControl/v2/getStreamMediaAppList",
        {"start": 0, "count": 20, "showMusicApp": "true", "sort": 4},
    ),
)

# Library endpoints, tried under both prefixes seen across firmware generations.
LIBRARY_ENDPOINTS: tuple[tuple[str, dict[str, Any]], ...] = (
    ("getFavorites", LIST_PARAMS),
    ("getSongLists", {}),
    ("getPlayQueue", LIST_PARAMS),
    ("getSingleMusics", LIST_PARAMS),
    ("getAlbums", LIST_PARAMS),
    ("getRecentlyPlayedMusicList", LIST_PARAMS),
)

# Candidate names for the favorites and internet-radio collections. None of
# these is documented; the report says which ones this firmware recognizes.
CANDIDATE_ENDPOINTS: tuple[tuple[str, dict[str, Any]], ...] = (
    ("getCollectList", LIST_PARAMS),
    ("getCollectionList", LIST_PARAMS),
    ("getMyCollection", LIST_PARAMS),
    ("getMyCollectionList", LIST_PARAMS),
    ("getFavoriteList", LIST_PARAMS),
    ("getFavoriteRadioList", LIST_PARAMS),
    ("getRadioList", LIST_PARAMS),
    ("getRadioFavoriteList", LIST_PARAMS),
    ("getInternetRadioList", LIST_PARAMS),
    ("getWebRadioList", LIST_PARAMS),
    ("getTuneinFavoriteList", LIST_PARAMS),
)


def request(url: str, timeout: float) -> dict[str, Any]:
    """Fetch one endpoint and summarize its answer."""
    try:
        with OPENER.open(url, timeout=timeout) as response:
            raw = response.read()
            status = response.status
            content_type = response.headers.get_content_type()
    except HTTPError as err:
        return {"url": url, "http_status": err.code, "error": err.reason}
    except OSError as err:  # URLError and TimeoutError are both OSError
        return {"url": url, "error": str(err)}

    result: dict[str, Any] = {
        "url": url,
        "http_status": status,
        "content_type": content_type,
        "bytes": len(raw),
    }
    try:
        decoded = json.loads(raw)
    except ValueError:  # JSON and decoding errors are both ValueError
        result["body_preview"] = raw[:200].decode("utf-8", "replace")
        return result

    if isinstance(decoded, dict):
        result["device_status"] = decoded.get("status")
        result["keys"] = sorted(decoded)
    result["sample"] = sample(decoded)
    return result


def sample(decoded: Any) -> Any:
    """Keep a readable slice of a response instead of the whole library."""
    if isinstance(decoded, list):
        return [sample(item) for item in decoded[:3]]
    if not isinstance(decoded, dict):
        return decoded
    return {
        key: (
            [sample(item) for item in value[:3]]
            if isinstance(value, list)
            else sample(value)
            if isinstance(value, dict)
            else value
        )
        for key, value in decoded.items()
    }


def collect_play_queue(base: str, timeout: float) -> list[dict[str, Any]]:
    """Return every queue entry, untruncated.

    On the internet-radio source the queue is where the stations live, each
    with the title `media_player.select_source` matches and its stream URL, so
    the report keeps all of them rather than a sample.
    """
    for prefix in LIBRARY_PREFIXES:
        result = request(
            f"{base}{prefix}/getPlayQueue?start=0&count=200&sort=0", timeout
        )
        if result.get("http_status") != 200:
            continue
        entries = result.get("sample", {})
        array = entries.get("array") if isinstance(entries, dict) else None
        if not isinstance(array, list):
            continue
        return [
            {
                "title": entry.get("title") or entry.get("fileName"),
                "url": entry.get("url") or entry.get("uri"),
                "sourceType": entry.get("sourceType"),
            }
            for entry in array
            if isinstance(entry, dict)
        ]
    return []


def probe(host: str, port: int, timeout: float) -> dict[str, Any]:
    """Probe every endpoint and group the results by category."""
    base = f"http://{host}:{port}"

    def run(path: str, params: dict[str, Any]) -> dict[str, Any]:
        query = f"?{urlencode(params)}" if params else ""
        print(f"  {path}{query}", flush=True)
        return request(f"{base}{path}{query}", timeout)

    report: dict[str, Any] = {"host": host, "port": port, "known": {}, "library": {}}
    print("Known endpoints:")
    for path, params in KNOWN_ENDPOINTS:
        report["known"][path] = run(path, params)

    print("Library endpoints:")
    for endpoint, params in LIBRARY_ENDPOINTS + CANDIDATE_ENDPOINTS:
        report["library"][endpoint] = {
            prefix: run(f"{prefix}/{endpoint}", params) for prefix in LIBRARY_PREFIXES
        }

    print("Play queue (full):")
    report["play_queue"] = collect_play_queue(base, timeout)
    return report


def summarize(report: dict[str, Any]) -> None:
    """Print the endpoints that answered, which is what the integration needs."""
    queue = report.get("play_queue") or []
    if queue:
        print("\nPlay queue — these titles are selectable with select_source:")
        for index, entry in enumerate(queue):
            print(f"  [{index}] {entry['title']}  ->  {entry['url']}")
    print("\nEndpoints that answered with data:")
    for path, result in report["known"].items():
        if result.get("http_status") == 200:
            print(f"  {path} ({result.get('bytes', 0)} bytes)")
    for endpoint, per_prefix in report["library"].items():
        for prefix, result in per_prefix.items():
            if result.get("http_status") == 200 and result.get("device_status") in (
                None,
                200,
                "200",
            ):
                print(f"  {prefix}/{endpoint} ({result.get('bytes', 0)} bytes)")


def main() -> None:
    """Run the probe from the command line."""
    # Station names are not ASCII, and a redirected console on Windows is.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("host", help="Eversolo IP address or hostname")
    parser.add_argument("--port", type=int, default=9529, help="API port (9529)")
    parser.add_argument("--timeout", type=float, default=5.0, help="Request timeout")
    parser.add_argument("--output", help="Write the full JSON report to this file")
    args = parser.parse_args()

    report = probe(args.host, args.port, args.timeout)
    summarize(report)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as handle:
            json.dump(report, handle, indent=2, ensure_ascii=False)
        print(f"\nFull report written to {args.output}")
    else:
        print("\n" + json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
