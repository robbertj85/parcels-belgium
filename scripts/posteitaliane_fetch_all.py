"""
Fetch all Poste Italiane pickup locations: Uffici Postali, Punto Poste (mostly
tabaccherie and supermarkets) and Punto Poste Lockers.

API: POST https://mapcollection.poste.it/v2/map/geoListByComune
     {"tipoPunto": [...], "comune": "<NAME>", "limit": 50, "offset": N}
     The map on poste.it; no key. At most 50 points per page, paged with
     offset. The bounding-box endpoint (/v2/map/geoList) always returns the 10
     nearest points, so it cannot cover the country.

Strategy: one search per comune (from data/municipalities_all.json, written by
scripts/build_municipalities.py), paged until a short page. The province is
optional and left out: points of same-named comuni elsewhere are harmless,
because batch_generate clips every point to its own comune's outline.

Poste spells names its own way: "CANTU'" finds more than "CANTÙ", and a
bilingual name ("Bolzano - Bozen") finds nothing. Each comune is searched under
a few spellings and the results merged on id.

Usage:
    python scripts/posteitaliane_fetch_all.py
"""

import json
import re
import sys
import threading
import time
import unicodedata
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from country_config import CONFIG, MUNICIPALITIES_FILE, carrier_cache_file, in_bbox  # noqa: E402

API_URL = "https://mapcollection.poste.it/v2/map/geoListByComune"
POINT_TYPES = {
    "UfficioPostale": "postkantoor",
    "PuntoPoste": "servicepunt",
    "PuntoPosteLocker": "automaat",
}
PAGE_SIZE = 50
WORKERS = 4
REQUEST_DELAY = 0.2
MAX_ATTEMPTS = 4

DAYS = {
    "lunedì": "ma", "martedì": "di", "mercoledì": "wo", "giovedì": "do",
    "venerdì": "vr", "sabato": "za", "domenica": "zo",
}

HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json",
    "Origin": "https://www.poste.it",
    "Referer": "https://www.poste.it/",
    "User-Agent": "pakketpunten/1.0 (parcel point viewer)",
}

_local = threading.local()
_failed = []
_failed_lock = threading.Lock()


def session():
    if not hasattr(_local, "session"):
        _local.session = requests.Session()
        _local.session.headers.update(HEADERS)
    return _local.session


def fetch_page(comune, offset):
    body = {"tipoPunto": list(POINT_TYPES), "comune": comune, "limit": PAGE_SIZE, "offset": offset}
    for attempt in range(MAX_ATTEMPTS):
        try:
            resp = session().post(API_URL, data=json.dumps(body), timeout=30)
            if resp.status_code == 429 or resp.status_code >= 500:
                raise requests.HTTPError(f"HTTP {resp.status_code}")
            resp.raise_for_status()
            data = resp.json()
            if data.get("status") != "SUCCESS":
                raise ValueError(f"status {data.get('status')}")
            return (data.get("data") or {}).get("listaPunti") or []
        except (requests.RequestException, ValueError) as e:
            if attempt == MAX_ATTEMPTS - 1:
                raise RuntimeError(f"{comune} offset {offset}: {e}")
            time.sleep(3 * (attempt + 1))


def fetch_comune(comune):
    points = []
    offset = 0
    while True:
        page = fetch_page(comune, offset)
        points.extend(page)
        time.sleep(REQUEST_DELAY)
        if len(page) < PAGE_SIZE:
            return points
        offset += PAGE_SIZE


def spellings(municipality):
    """Search names for one comune, most likely first."""
    names = [municipality["name"]] + municipality.get("aliases", [])
    variants = []
    for name in names:
        # Bilingual names: "Bolzano - Bozen", "Aosta / Aoste"
        for part in re.split(r"\s+-\s+|\s*/\s*", name):
            upper = part.strip().upper()
            if not upper:
                continue
            variants.append(upper)
            # Poste writes a final accented vowel as vowel + apostrophe: CANTU'
            apostrophe = re.sub(r"([ÀÈÉÌÒÙ])$", lambda m: unicodedata.normalize("NFKD", m.group(1))[0] + "'", upper)
            variants.append(apostrophe)
    seen = []
    for v in variants:
        if v not in seen:
            seen.append(v)
    return seen


def fetch_municipality(municipality):
    """All points found under any spelling of this comune's name."""
    found = {}
    for name in spellings(municipality):
        try:
            for point in fetch_comune(name):
                found[point["id"]] = point
        except RuntimeError as e:
            with _failed_lock:
                _failed.append(str(e))
    return municipality, found


def opening_hours(point):
    entries = point.get("orari") or point.get("orariPuntoPoste") or []
    week = {}
    for entry in entries:
        day = DAYS.get((entry.get("giorno") or "").strip().lower())
        hours = (entry.get("orario") or "").strip()
        if not day or not hours:
            continue
        if hours.upper() == "CHIUSO":
            week[day] = "gesloten"
        else:
            week[day] = re.sub(r"\s*-\s*", " - ", hours).replace("/", ",")
    if not week:
        return point.get("orarioApertura") or None
    for day in DAYS.values():
        week.setdefault(day, "gesloten")
    return week


def split_address(address):
    m = re.match(r"^(.*?)[,\s]+(\d+\S*)$", (address or "").strip())
    if m:
        return m.group(1).strip(), m.group(2)
    return (address or "").strip(), ""


def normalize(point):
    street, number = split_address(point.get("indirizzoPunto"))
    return {
        "id": f"poste-{point['id']}",
        "locatieNaam": point.get("nomePunto", ""),
        "straatNaam": street,
        "straatNr": number,
        "postcode": point.get("cap", ""),
        "city": point.get("citta", ""),
        "latitude": float(point["lat"]),
        "longitude": float(point["lon"]),
        "puntType": POINT_TYPES.get(point.get("tipoPunto"), "servicepunt"),
        "canPickup": True,
        "canDropoff": True,
        "openingstijden": opening_hours(point),
    }


def main():
    print("=" * 80)
    print("POSTE ITALIANE COMPLETE LOCATION FETCH")
    print("=" * 80)
    print(f"Time: {datetime.now():%Y-%m-%d %H:%M:%S}")

    with open(MUNICIPALITIES_FILE, encoding="utf-8") as f:
        municipalities = json.load(f)
    print(f"📍 {len(municipalities)} comuni, {WORKERS} parallel\n")

    points = {}
    empty = []
    started = time.time()
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        futures = [pool.submit(fetch_municipality, m) for m in municipalities]
        for i, future in enumerate(as_completed(futures), 1):
            municipality, found = future.result()
            if not found:
                empty.append(municipality["name"])
            points.update(found)
            if i % 250 == 0:
                rate = i / (time.time() - started)
                print(f"   [{i}/{len(municipalities)}] {len(points)} punti "
                      f"(~{(len(municipalities) - i) / rate / 60:.0f} min rimanenti)", flush=True)

    locations = []
    for point in points.values():
        try:
            loc = normalize(point)
        except (KeyError, TypeError, ValueError):
            continue
        if in_bbox(loc["latitude"], loc["longitude"]):
            locations.append(loc)

    print(f"\n✅ {len(locations)} Poste Italiane-locaties")
    for punt_type, count in Counter(loc["puntType"] for loc in locations).most_common():
        print(f"   {punt_type:15s}: {count:6d}")
    # Nearly every comune has a post office, so an empty result usually means
    # Poste spells the name differently
    print(f"   {len(empty)} comuni zonder resultaat: {', '.join(empty[:15])}")

    if _failed:
        print(f"❌ {len(_failed)} zoekopdrachten mislukt ({_failed[0]}); cache niet bijgewerkt")
        return 1
    if not locations:
        print("❌ Geen locaties opgehaald")
        return 1

    from cache_guard import safe_save
    safe_save(
        carrier="PosteItaliane",
        new_locations=locations,
        output_path=carrier_cache_file("PosteItaliane"),
        metadata={
            "method": "per-comune",
            "source": API_URL,
            "country": CONFIG["name"],
            "comuni_without_results": len(empty),
        },
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
