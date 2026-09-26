"""
Fetch all bpost pickup locations in Belgium: post offices, postpunten /
pakjespunten and parcel lockers (pakjesautomaten, incl. Cubee-hosted bpost boxes).

API: https://pudo.bpost.be/Locator (Geo6 "TaxipostLocator", XML, no key; the
     public partner id 999999 is the one bpost's own widget uses).

     Function=search&Zone=<postcode>&Type=7&Limit=1000 returns every point
     within 20 km of the postcode. Type is a bitmask:
       1 = postkantoor, 2 = postpunt / pakjespunt, 4 = pakjesautomaat.

Strategy: the API only accepts a postcode as search centre, so the script
crawls outward from a few seed postcodes. Each response reveals new postcodes
(with coordinates from their points); a postcode is queried only when no
earlier search centre lies within COVER_KM of it, which keeps the whole
country covered by overlapping 20 km circles in ~150 calls.

Usage:
    python scripts/bpost_fetch_all.py
"""

import math
import sys
import time
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from country_config import CONFIG, carrier_cache_file, in_bbox  # noqa: E402

API_URL = "https://pudo.bpost.be/Locator"
SEARCH_RADIUS_KM = 20
# A postcode is searched when no earlier centre is within this distance. Must
# stay well below SEARCH_RADIUS_KM, because a postcode's points can lie a few
# kilometres from where the API centres its search.
COVER_KM = 10
REQUEST_DELAY = 0.5

# Spread over all provinces so the crawl starts everywhere at once
SEED_POSTCODES = [
    "1000", "2000", "2300", "3000", "3500", "3600", "3900", "4000", "4700",
    "5000", "5500", "6000", "6600", "6700", "6800", "7000", "7500", "8000",
    "8500", "8900", "9000", "9100", "9300",
]

# Searches that failed three times; any of them leaves a possible hole
FAILED_POSTCODES = []

POINT_TYPES = {
    "1": "postkantoor",
    "2": "servicepunt",
    "4": "automaat",
}


def haversine_km(a, b):
    lat1, lon1 = a
    lat2, lon2 = b
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    h = (math.sin(dlat / 2) ** 2
         + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2)
    return 6371 * 2 * math.asin(math.sqrt(h))


def search(session, postcode):
    """All points within 20 km of `postcode`, as dicts."""
    params = {
        "Function": "search",
        "Partner": "999999",
        "Language": "NL",
        "Zone": postcode,
        "Type": "7",
        "Limit": "1000",
    }
    for attempt in range(3):
        try:
            resp = session.get(API_URL, params=params, timeout=60)
            resp.raise_for_status()
            root = ET.fromstring(resp.content)
            break
        except (requests.RequestException, ET.ParseError) as e:
            if attempt == 2:
                print(f"   ⚠️  {postcode}: {e}")
                FAILED_POSTCODES.append(postcode)
                return []
            time.sleep(2 * (attempt + 1))

    points = []
    for record in root.iter("Record"):
        get = lambda tag: (record.findtext(tag) or "").strip()  # noqa: E731
        try:
            lat = float(get("Latitude"))
            lon = float(get("Longitude"))
        except ValueError:
            continue
        points.append({
            "id": get("Id"),
            "type": get("Type"),
            "name": get("Name"),
            "street": get("Street"),
            "number": get("Number"),
            "zip": get("Zip"),
            "city": get("City"),
            "country": get("Country"),
            "latitude": lat,
            "longitude": lon,
        })
    return points


def crawl():
    session = requests.Session()
    session.headers["User-Agent"] = "pakketpunten_belgie/1.0"

    points = {}                    # (type, id) -> point
    zip_coords = defaultdict(list)  # postcode -> [(lat, lon)]
    centres = []                   # coordinates of searched postcodes
    queue = list(SEED_POSTCODES)
    queried = set()

    while queue:
        postcode = queue.pop(0)
        if postcode in queried:
            continue

        # Skip postcodes already inside a searched circle
        coords = zip_coords.get(postcode)
        if coords:
            centre = (sum(c[0] for c in coords) / len(coords), sum(c[1] for c in coords) / len(coords))
            if any(haversine_km(centre, c) < COVER_KM for c in centres):
                continue
        else:
            centre = None

        queried.add(postcode)
        results = search(session, postcode)
        new = 0
        for p in results:
            key = (p["type"], p["id"])
            if key not in points:
                points[key] = p
                new += 1
            if p["zip"]:
                zip_coords[p["zip"]].append((p["latitude"], p["longitude"]))

        if centre is None and zip_coords.get(postcode):
            coords = zip_coords[postcode]
            centre = (sum(c[0] for c in coords) / len(coords), sum(c[1] for c in coords) / len(coords))
        if centre:
            centres.append(centre)

        # Postcodes seen for the first time go to the back of the queue
        for z in {p["zip"] for p in results}:
            if z and z not in queried and z not in queue:
                queue.append(z)

        print(f"   [{len(queried):3d}] {postcode}: {len(results):4d} punten, {new:4d} nieuw "
              f"(totaal {len(points)}, wachtrij {len(queue)})")
        time.sleep(REQUEST_DELAY)

    return list(points.values()), len(queried)


def normalize(point):
    return {
        "id": f"bpost-{point['type']}-{point['id']}",
        "locatieNaam": point["name"].title(),
        "straatNaam": point["street"].title(),
        "straatNr": point["number"],
        "postcode": point["zip"],
        "city": point["city"].title(),
        "latitude": point["latitude"],
        "longitude": point["longitude"],
        "puntType": POINT_TYPES.get(point["type"], "servicepunt"),
        "canPickup": True,
        "canDropoff": True,
        # Openingstijden vragen één info-call per punt (~5.000); niet opgehaald.
        "openingstijden": None,
    }


def main():
    print("=" * 80)
    print("BPOST COMPLETE LOCATION FETCH")
    print("=" * 80)
    print(f"Time: {datetime.now():%Y-%m-%d %H:%M:%S}")
    print(f"Endpoint: {API_URL} (zoekstraal {SEARCH_RADIUS_KM} km per postcode)\n")

    raw, calls = crawl()
    locations = [
        normalize(p) for p in raw
        if p["country"] in ("", CONFIG["iso2"]) and in_bbox(p["latitude"], p["longitude"])
    ]

    print(f"\n✅ {len(locations)} bpost-locaties uit {calls} zoekopdrachten")
    for punt_type, count in Counter(loc["puntType"] for loc in locations).most_common():
        print(f"   {punt_type:15s}: {count:5d}")
    unknown = Counter(p["type"] for p in raw if p["type"] not in POINT_TYPES)
    if unknown:
        print(f"   ⚠️  Onbekende types (als servicepunt opgeslagen): {dict(unknown)}")

    if FAILED_POSTCODES:
        print(f"❌ {len(FAILED_POSTCODES)} zoekopdrachten mislukt ({', '.join(FAILED_POSTCODES[:10])}); "
              "cache niet bijgewerkt")
        return 1
    if not locations:
        print("❌ Geen locaties opgehaald")
        return 1

    from cache_guard import safe_save
    safe_save(
        carrier="bpost",
        new_locations=locations,
        output_path=carrier_cache_file("bpost"),
        metadata={
            "method": "postcode-crawl",
            "source": API_URL,
            "country": CONFIG["name"],
            "search_calls": calls,
        },
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
