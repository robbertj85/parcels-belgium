"""
Fetch all PostNL pickup locations in the configured country (Belgium: PostNL
partner points, mostly shops of type 404).

API: https://productprijslokatie.postnl.nl/location-widget/api/locations
     (the public location widget on postnl.be/postnl.nl; no key).
     Bounding-box search. A large box is truncated (~100 results for all of
     Belgium), so the country is tiled and any tile that comes back near the
     cap is split into four until it is under it.

In the Dutch viewer PostNL is fetched live per municipality; here it is a
nationwide cache like every other carrier, so batch_generate does no network
calls.

Usage:
    python scripts/postnl_fetch_all.py
"""

import json
import sys
import time
from collections import Counter
from datetime import datetime
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from country_config import CONFIG, carrier_cache_file, in_bbox  # noqa: E402
from api_client import normalize_hours_postnl  # noqa: E402

API_URL = "https://productprijslokatie.postnl.nl/location-widget/api/locations"
TILE_LAT = 0.25
TILE_LON = 0.35
# A tile at or above this count may be truncated and is split into four
SPLIT_AT = 90
MIN_TILE_DEG = 0.01
REQUEST_DELAY = 0.3

# properties.id -> puntType. 405 = pakket- en briefautomaat; the rest are staffed.
POSTNL_TYPE_MAPPING = {405: "automaat"}


def fetch_box(session, south, west, north, east):
    params = {
        "country": CONFIG["postnl"]["country"],
        "business": "false",
        "filters": "[]",
        # The Dutch viewer filters on productId 23; that filter returns nothing
        # for Belgium, so ask for every location.
        "productFilters": "[]",
        "defaultFilters": "[]",
        "bottomLeftLat": south,
        "bottomLeftLon": west,
        "topRightLat": north,
        "topRightLon": east,
        "lang": CONFIG["postnl"]["lang"],
    }
    for attempt in range(3):
        try:
            resp = session.get(API_URL, params=params, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            return data.get("items", []) if isinstance(data, dict) else data
        except (requests.RequestException, json.JSONDecodeError) as e:
            if attempt == 2:
                raise RuntimeError(f"PostNL box {south},{west},{north},{east}: {e}")
            time.sleep(2 * (attempt + 1))


def tiles():
    south, west, north, east = CONFIG["bbox"]
    lat = south
    while lat < north:
        lon = west
        while lon < east:
            yield (lat, lon, min(lat + TILE_LAT, north), min(lon + TILE_LON, east))
            lon += TILE_LON
        lat += TILE_LAT


def crawl():
    session = requests.Session()
    session.headers["User-Agent"] = "pakketpunten_belgie/1.0"
    found = {}
    queue = list(tiles())
    calls = 0

    while queue:
        south, west, north, east = queue.pop(0)
        items = fetch_box(session, south, west, north, east)
        calls += 1

        if len(items) >= SPLIT_AT and (north - south) > MIN_TILE_DEG:
            mid_lat, mid_lon = (south + north) / 2, (west + east) / 2
            queue.extend([
                (south, west, mid_lat, mid_lon), (south, mid_lon, mid_lat, east),
                (mid_lat, west, north, mid_lon), (mid_lat, mid_lon, north, east),
            ])
            print(f"   [{calls:3d}] {len(items):3d} punten → opsplitsen")
        else:
            new = 0
            for item in items:
                key = item.get("partnerLocationId") or (
                    item["coordinates"]["latitude"], item["coordinates"]["longitude"], item.get("locationName"))
                if key not in found:
                    found[key] = item
                    new += 1
            if items:
                print(f"   [{calls:3d}] {len(items):3d} punten, {new:3d} nieuw (totaal {len(found)})")
        time.sleep(REQUEST_DELAY)

    return list(found.values()), calls


def normalize(item):
    coords = item.get("coordinates", {})
    addr = item.get("internationalAddress", {}) or {}
    props = item.get("properties", {}) or {}
    street_nr = str(addr.get("buildingNumber") or "")
    if addr.get("buildingNumberExtension"):
        street_nr += addr["buildingNumberExtension"]
    return {
        "id": f"postnl-{item.get('partnerLocationId')}",
        "locatieNaam": item.get("locationName", ""),
        "straatNaam": addr.get("streetName", ""),
        "straatNr": street_nr,
        "postcode": addr.get("postalCode", ""),
        "city": addr.get("cityName", ""),
        "countryCode": addr.get("countryCode", ""),
        "latitude": coords.get("latitude"),
        "longitude": coords.get("longitude"),
        "puntType": POSTNL_TYPE_MAPPING.get(props.get("id"), "servicepunt"),
        "canPickup": True,
        "canDropoff": True,
        "openingstijden": normalize_hours_postnl(item.get("openingTimeWindow"), item.get("criteria")),
    }


def main():
    print("=" * 80)
    print("POSTNL COMPLETE LOCATION FETCH")
    print("=" * 80)
    print(f"Time: {datetime.now():%Y-%m-%d %H:%M:%S}")
    print(f"Country: {CONFIG['postnl']['country']}\n")

    items, calls = crawl()
    locations = [
        loc for loc in (normalize(i) for i in items if i.get("locationActive", True))
        # Records without a country code are Dutch "BBN_" entries with broken
        # coordinates (a Rotterdam address placed in Brabant); drop them.
        if loc["countryCode"] == CONFIG["iso2"] and in_bbox(loc["latitude"], loc["longitude"])
    ]
    print(f"\n✅ {len(locations)} PostNL-locaties uit {calls} zoekopdrachten")
    for punt_type, count in Counter(loc["puntType"] for loc in locations).most_common():
        print(f"   {punt_type:15s}: {count:5d}")

    if not locations:
        print("❌ Geen locaties opgehaald")
        return 1

    from cache_guard import safe_save
    safe_save(
        carrier="PostNL",
        new_locations=locations,
        output_path=carrier_cache_file("PostNL"),
        metadata={
            "method": "bbox-tiles",
            "source": API_URL,
            "country": CONFIG["name"],
            "search_calls": calls,
        },
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
