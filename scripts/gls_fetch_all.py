"""
Fetch all GLS ParcelShops and Parcel Lockers in the configured country.

API: https://api.gls-group.net/parcel-shop-management/v2/available-public-parcel-shops-pse-bulk
     GLS's pan-European parcel shop search, the backend of the depot/parcelshop
     finder on gls-group.com. It needs the public widget key that that page
     embeds (attribute `psmApiKey` on https://gls-group.com/BE/vl/depot-parcelshop/),
     not an account. Circle search (latitude, longitude, distance in km); calls
     with a large distance fail, so the country is covered by a grid of 20 km
     circles.

Belgian GLS lockers include the Cubee lockers GLS delivers to.

Usage:
    python scripts/gls_fetch_all.py
"""

import sys
import time
from collections import Counter
from datetime import datetime
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from country_config import CONFIG, carrier_cache_file, grid_points, in_bbox  # noqa: E402

API_URL = "https://api.gls-group.net/parcel-shop-management/v2/available-public-parcel-shops-pse-bulk"
# Public key from the GLS parcel shop finder; replace it here if GLS rotates it.
API_KEY = "LzEk1XV5Lw5zjZ1G6KpBKOF4PGGOwqTA"
SEARCH_DISTANCE_KM = 20
# Circles of 20 km on a 25 km grid overlap: the far corner of a cell is 17.7 km away
GRID_SPACING_KM = 25
REQUEST_DELAY = 1.0

HEADERS = {
    "apikey": API_KEY,
    "Origin": "https://gls-group.com",
    "Referer": "https://gls-group.com/",
    "Accept": "application/json",
    "User-Agent": "pakketpunten_belgie/1.0",
}

DAYS = {"MON": "ma", "TUE": "di", "WED": "wo", "THU": "do", "FRI": "vr", "SAT": "za", "SUN": "zo"}


def fetch_circle(session, lat, lon):
    params = {"latitude": lat, "longitude": lon, "distance": SEARCH_DISTANCE_KM}
    for attempt in range(5):
        resp = session.get(API_URL, params=params, timeout=30)
        if resp.status_code == 429 or resp.status_code >= 500:
            wait = 5 * (attempt + 1)
            print(f"   ⏳ HTTP {resp.status_code}, opnieuw over {wait}s")
            time.sleep(wait)
            continue
        resp.raise_for_status()
        return resp.json()
    raise RuntimeError(f"GLS ({lat}, {lon}) bleef falen")


def opening_hours(shop):
    """De bulk-API geeft alleen vandaag en morgen; toon die als tekst."""
    parts = []
    for key in ("today", "nextDay"):
        day = (shop.get("openingHours") or {}).get(key)
        if not day:
            continue
        windows = ", ".join(f"{h['openingTime']} - {h['closingTime']}" for h in day.get("hours", []))
        parts.append(f"{DAYS.get(day.get('weekday'), day.get('weekday'))}: {windows or 'gesloten'}")
    return "; ".join(parts) or None


def normalize(shop):
    return {
        "id": f"gls-{shop.get('parcelShopId')}",
        "locatieNaam": shop.get("name", ""),
        "straatNaam": (shop.get("street") or "").title(),
        "straatNr": shop.get("houseNumber") or "",
        "postcode": shop.get("zipCode", ""),
        "city": (shop.get("city") or "").title(),
        "partnerId": shop.get("partnerId"),
        "latitude": shop.get("latitude"),
        "longitude": shop.get("longitude"),
        "puntType": "locker" if shop.get("type") == "LOCKER" else "parcel_shop",
        "canPickup": bool(shop.get("offersParcelCollection", True)),
        "canDropoff": bool(shop.get("offersReturnDropOff") or shop.get("offersPrepaidParcelDropOff")),
        "openingstijden": opening_hours(shop),
    }


def main():
    print("=" * 80)
    print("GLS COMPLETE LOCATION FETCH")
    print("=" * 80)
    print(f"Time: {datetime.now():%Y-%m-%d %H:%M:%S}")

    partners = CONFIG["gls"]["partner_prefixes"]
    points = grid_points(GRID_SPACING_KM)
    print(f"📍 {len(points)} zoekcirkels van {SEARCH_DISTANCE_KM} km, partners {partners}\n")

    session = requests.Session()
    session.headers.update(HEADERS)
    shops = {}
    failed = 0

    for i, (lat, lon) in enumerate(points, 1):
        try:
            results = fetch_circle(session, lat, lon)
        except Exception as e:
            failed += 1
            print(f"   [{i:3d}/{len(points)}] ⚠️  {e}")
            continue
        new = 0
        for shop in results:
            if not str(shop.get("partnerId", "")).startswith(partners):
                continue
            key = shop.get("parcelShopId")
            if key not in shops:
                shops[key] = shop
                new += 1
        if results:
            print(f"   [{i:3d}/{len(points)}] {len(results):4d} resultaten, {new:4d} nieuw (totaal {len(shops)})")
        time.sleep(REQUEST_DELAY)

    locations = [
        loc for loc in (normalize(s) for s in shops.values())
        if in_bbox(loc["latitude"], loc["longitude"])
    ]
    print(f"\n✅ {len(locations)} GLS-locaties ({failed} zoekcirkels mislukt)")
    for punt_type, count in Counter(loc["puntType"] for loc in locations).most_common():
        print(f"   {punt_type:15s}: {count:5d}")

    if failed > len(points) * 0.1:
        print(f"❌ Te veel mislukte zoekcirkels ({failed}); cache niet bijgewerkt")
        return 1
    if not locations:
        print("❌ Geen locaties opgehaald")
        return 1

    from cache_guard import safe_save
    safe_save(
        carrier="GLS",
        new_locations=locations,
        output_path=carrier_cache_file("GLS"),
        metadata={
            "method": "grid-circles",
            "source": API_URL,
            "country": CONFIG["name"],
            "partners": list(partners),
            "search_calls": len(points),
        },
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
