"""
Fetch all Vinted Go pickup points and lockers in the configured country.

Source: https://vintedgo.com/nl/carrier-locations (the public map page). The
points sit in the Next.js RSC payload, which utils.extract_points_array parses.
Bounding-box search capped at 500 points per response, so the country is tiled
and any tile near the cap is split into four.

In the Dutch viewer VintedGo is fetched live per municipality; here it is a
nationwide cache like every other carrier.

Usage:
    python scripts/vintedgo_fetch_all.py
"""

import json
import re
import sys
import time
import urllib.parse
from collections import Counter
from datetime import datetime
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from country_config import CONFIG, carrier_cache_file, in_bbox  # noqa: E402
from utils import extract_points_array  # noqa: E402

PAGE_URL = "https://vintedgo.com/nl/carrier-locations"
TILE_LAT = 0.25
TILE_LON = 0.35
# Responses are capped at 500 points; a tile near that is split
SPLIT_AT = 450
MIN_TILE_DEG = 0.01
REQUEST_DELAY = 1.0


def fetch_box(session, south, west, north, east):
    bounds = json.dumps({"south": south, "west": west, "north": north, "east": east}, separators=(",", ":"))
    url = (f"{PAGE_URL}?lat={(south + north) / 2}&lng={(west + east) / 2}"
           f"&bounds={urllib.parse.quote(bounds)}&region=europe")
    for attempt in range(3):
        try:
            resp = session.get(url, timeout=30)
            resp.raise_for_status()
            payload = extract_points_array(resp.text)
            # The page payload is [.., .., null, {"points": [...]}]; find the dict
            # instead of trusting the index, which the NL fetcher hardcodes.
            for part in payload:
                if isinstance(part, dict) and "points" in part:
                    return part["points"] or []
            return []
        except (requests.RequestException, ValueError) as e:
            if attempt == 2:
                raise RuntimeError(f"VintedGo box {south},{west},{north},{east}: {e}")
            time.sleep(3 * (attempt + 1))


def tiles():
    south, west, north, east = CONFIG["bbox"]
    lat = south
    while lat < north:
        lon = west
        while lon < east:
            yield (lat, lon, min(lat + TILE_LAT, north), min(lon + TILE_LON, east))
            lon += TILE_LON
        lat += TILE_LAT


def split_address(address):
    """'Jubelfeestlaan 46' -> ('Jubelfeestlaan', '46')."""
    m = re.match(r"^(.*?)[,\s]+(\d+\s*[a-zA-Z]?(?:[-/]\S+)?)$", (address or "").strip())
    if m:
        return m.group(1).strip(), m.group(2).replace(" ", "")
    return (address or "").strip(), ""


def normalize(point):
    street, number = split_address(point.get("address"))
    return {
        "id": f"vintedgo-{point.get('id')}",
        "locatieNaam": point.get("name", ""),
        "straatNaam": street,
        "straatNr": number,
        "postcode": point.get("postal_code", ""),
        "city": point.get("city", ""),
        "latitude": point.get("lat"),
        "longitude": point.get("lng"),
        "puntType": point.get("point_type", "parcel_shop"),
        "canPickup": True,
        "canDropoff": True,
        "openingstijden": None,
    }


def main():
    print("=" * 80)
    print("VINTED GO COMPLETE LOCATION FETCH")
    print("=" * 80)
    print(f"Time: {datetime.now():%Y-%m-%d %H:%M:%S}\n")

    country = CONFIG["vintedgo"]["country"].upper()
    session = requests.Session()
    session.headers["User-Agent"] = "Mozilla/5.0 (compatible; pakketpunten_belgie/1.0)"

    found = {}
    queue = list(tiles())
    calls = 0
    while queue:
        south, west, north, east = queue.pop(0)
        points = fetch_box(session, south, west, north, east)
        calls += 1
        if len(points) >= SPLIT_AT and (north - south) > MIN_TILE_DEG:
            mid_lat, mid_lon = (south + north) / 2, (west + east) / 2
            queue.extend([
                (south, west, mid_lat, mid_lon), (south, mid_lon, mid_lat, east),
                (mid_lat, west, north, mid_lon), (mid_lat, mid_lon, north, east),
            ])
            print(f"   [{calls:3d}] {len(points):3d} punten → opsplitsen")
        else:
            new = 0
            for p in points:
                if p.get("country_code") == country and p.get("active", True) and p.get("id") not in found:
                    found[p["id"]] = p
                    new += 1
            if points:
                print(f"   [{calls:3d}] {len(points):3d} punten, {new:3d} nieuw (totaal {len(found)})")
        time.sleep(REQUEST_DELAY)

    locations = [
        loc for loc in (normalize(p) for p in found.values())
        if in_bbox(loc["latitude"], loc["longitude"])
    ]
    print(f"\n✅ {len(locations)} Vinted Go-locaties uit {calls} zoekopdrachten")
    for punt_type, count in Counter(loc["puntType"] for loc in locations).most_common():
        print(f"   {punt_type:15s}: {count:5d}")

    if not locations:
        print("❌ Geen locaties opgehaald")
        return 1

    from cache_guard import safe_save
    safe_save(
        carrier="VintedGo",
        new_locations=locations,
        output_path=carrier_cache_file("VintedGo"),
        metadata={
            "method": "bbox-tiles",
            "source": PAGE_URL,
            "country": CONFIG["name"],
            "search_calls": calls,
        },
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
