"""
Laadt de pakketpunten per gemeente uit de landelijke caches.

Elke vervoerder heeft een fetch-script in scripts/ dat alle locaties van het
land in data/<vervoerder>_all_locations.json zet (via cache_guard.safe_save).
Hier worden die caches één keer per run ingelezen, naar één schema omgezet
en per gemeente op de gemeentegrens geknipt. Er gaan hier geen API-calls meer
uit, zodat batch_generate alleen nog geometrie doet.

Welke vervoerders meedoen staat in country_config.CARRIERS.
"""

import json
from functools import lru_cache

import pandas as pd, geopandas as gpd

from country_config import CARRIERS, carrier_cache_file
from utils import get_gemeente_polygon


# ---------- opening-hours normalization ----------
# Unified shape for `openingstijden` property:
#   - dict {ma, di, wo, do, vr, za, zo} with values like "09:00 - 18:00" or
#     "09:00 - 12:00, 13:00 - 18:00" or "gesloten" — for providers with per-day data
#   - plain string — for providers exposing only free-text or a single window
#   - None — when unknown

_DAYS_NL = ['ma', 'di', 'wo', 'do', 'vr', 'za', 'zo']


def _fmt_window(start, end):
    s = (start or '')[:5]
    e = (end or '')[:5]
    if not s or not e:
        return None
    return f"{s} - {e}"


def _empty_week():
    return {d: 'gesloten' for d in _DAYS_NL}


def normalize_hours_dhl(opening_times):
    """DHL: list of {weekDay: 1=Mon..7=Sun, timeFrom, timeTo}."""
    if not opening_times:
        return None
    by_day = {}
    for entry in opening_times:
        wd = entry.get('weekDay')
        if not isinstance(wd, int) or not 1 <= wd <= 7:
            continue
        win = _fmt_window(entry.get('timeFrom'), entry.get('timeTo'))
        if win:
            by_day.setdefault(wd, []).append(win)
    if not by_day:
        return None
    week = _empty_week()
    for wd, wins in by_day.items():
        week[_DAYS_NL[wd - 1]] = ', '.join(wins)
    return week


def normalize_hours_dpd(hours):
    """DPD: list of {day: 1=Mon..7=Sun, openMorning, closeMorning, openAfternoon, closeAfternoon}."""
    if not hours:
        return None
    week = _empty_week()
    any_open = False
    for entry in hours:
        d = entry.get('day')
        if not isinstance(d, int) or not 1 <= d <= 7:
            continue
        windows = []
        m = _fmt_window(entry.get('openMorning'), entry.get('closeMorning'))
        a = _fmt_window(entry.get('openAfternoon'), entry.get('closeAfternoon'))
        if m:
            windows.append(m)
        if a:
            windows.append(a)
        if windows:
            week[_DAYS_NL[d - 1]] = ', '.join(windows)
            any_open = True
    return week if any_open else None


def normalize_hours_gls(opening_hours):
    """GLS: list of {dayOfWeek: 0=Sun..6=Sat, openTime, closeTime}."""
    if not opening_hours:
        return None
    by_day = {}
    for entry in opening_hours:
        dow = entry.get('dayOfWeek')
        if not isinstance(dow, int) or not 0 <= dow <= 6:
            continue
        win = _fmt_window(entry.get('openTime'), entry.get('closeTime'))
        if not win:
            continue
        # GLS 0=Sun..6=Sat → Dutch index 0=Mon..6=Sun
        nl_idx = 6 if dow == 0 else dow - 1
        by_day.setdefault(nl_idx, []).append(win)
    if not by_day:
        return None
    week = _empty_week()
    for nl_idx, wins in by_day.items():
        week[_DAYS_NL[nl_idx]] = ', '.join(wins)
    return week


def normalize_hours_viatim(hours):
    """ViaTim: list of {week, monday..sunday: [from, to]}. Use first non-empty week."""
    if not hours:
        return None
    en_to_nl = {
        'monday': 'ma', 'tuesday': 'di', 'wednesday': 'wo', 'thursday': 'do',
        'friday': 'vr', 'saturday': 'za', 'sunday': 'zo',
    }
    for wk in hours:
        if not isinstance(wk, dict):
            continue
        week = _empty_week()
        any_open = False
        for en, nl in en_to_nl.items():
            arr = wk.get(en) or []
            if len(arr) >= 2:
                win = _fmt_window(arr[0], arr[1])
                if win:
                    week[nl] = win
                    any_open = True
        if any_open:
            return week
    return None


def normalize_hours_postnl(window, criteria):
    """PostNL: single `openingTimeWindow` string + criteria flags. Returns a short string."""
    if not window:
        return None
    txt = window.replace('-', ' - ') if '-' in window and ' - ' not in window else window
    flags = []
    for c in criteria or []:
        name = c.get('name') if isinstance(c, dict) else None
        if name:
            flags.append(name)
    if flags:
        return f"{txt} ({'; '.join(flags)})"
    return txt


# ---------- per-vervoerder mapping naar het gedeelde schema ----------
#
# Schema per punt: locatieNaam, straatNaam, straatNr, latitude, longitude,
# puntType, vervoerder, canPickup, canDropoff, openingstijden.
#
# DHL en DPD bewaren de ruwe API-objecten (zoals in de Nederlandse viewer);
# de overige fetchers schrijven al genormaliseerde records.

def _row_dhl(loc):
    geo = loc.get('geoLocation', {})
    addr = loc.get('address', {})
    service_types = loc.get('serviceTypes', [])
    return {
        'locatieNaam': loc.get('name', ''),
        'straatNaam': addr.get('street', ''),
        'straatNr': str(addr.get('number', '')) + (addr.get('addition', '') or ''),
        'latitude': geo.get('latitude'),
        'longitude': geo.get('longitude'),
        'puntType': loc.get('shopType', ''),
        # parcel-last-mile = ophalen, parcel-first-mile = versturen
        'canPickup': 'parcel-last-mile' in service_types,
        'canDropoff': 'parcel-first-mile' in service_types,
        'openingstijden': normalize_hours_dhl(loc.get('openingTimes')),
    }


def _row_dpd(loc):
    return {
        'locatieNaam': loc.get('company', ''),
        'straatNaam': loc.get('street', ''),
        'straatNr': loc.get('house_number', ''),
        'latitude': loc.get('latitude'),
        'longitude': loc.get('longitude'),
        'puntType': loc.get('pickup_network_type', ''),
        'canPickup': bool(loc.get('pickup_allowed', 0)),
        'canDropoff': bool(loc.get('dropoff_allowed', 0)),
        'openingstijden': normalize_hours_dpd(loc.get('hours')),
    }


def _row_viatim(loc):
    return {
        'locatieNaam': loc.get('locatieNaam', ''),
        'straatNaam': loc.get('straatNaam', ''),
        'straatNr': loc.get('straatNr', ''),
        'latitude': loc.get('latitude'),
        'longitude': loc.get('longitude'),
        'puntType': 'servicepunt',
        'canPickup': True,
        'canDropoff': True,
        'openingstijden': normalize_hours_viatim(loc.get('hours')),
    }


def _row_inpost(loc):
    return {
        'locatieNaam': loc.get('locatieNaam', ''),
        'straatNaam': loc.get('straatNaam', ''),
        'straatNr': loc.get('straatNr', ''),
        'latitude': loc.get('latitude'),
        'longitude': loc.get('longitude'),
        'puntType': loc.get('puntType', 'servicepunt'),
        'canPickup': True,
        'canDropoff': True,
        'openingstijden': loc.get('opening_hours') or None,
    }


def _row_amazon(loc):
    return {
        'locatieNaam': loc.get('locatieNaam', loc.get('name', '')),
        'straatNaam': loc.get('straatNaam', loc.get('address', '')),
        'straatNr': loc.get('straatNr', ''),
        'latitude': loc.get('latitude'),
        'longitude': loc.get('longitude'),
        'puntType': loc.get('puntType', loc.get('type', '')),
        # Amazon: alleen ophalen, niet versturen
        'canPickup': True,
        'canDropoff': False,
        'openingstijden': loc.get('openingstijden') or None,
    }


def _row_normalized(loc):
    """Records die de fetcher al in het gedeelde schema schreef (bpost, PostNL, GLS, VintedGo)."""
    return {
        'locatieNaam': loc.get('locatieNaam', ''),
        'straatNaam': loc.get('straatNaam', ''),
        'straatNr': loc.get('straatNr', ''),
        'latitude': loc.get('latitude'),
        'longitude': loc.get('longitude'),
        'puntType': loc.get('puntType', ''),
        'canPickup': loc.get('canPickup', True),
        'canDropoff': loc.get('canDropoff', True),
        'openingstijden': loc.get('openingstijden') or None,
    }


ROW_MAPPERS = {
    'DHL': _row_dhl,
    'DPD': _row_dpd,
    'ViaTim': _row_viatim,
    'InPost': _row_inpost,
    'Amazon': _row_amazon,
}

COLUMNS = [
    "locatieNaam",
    "straatNaam",
    "straatNr",
    "latitude",
    "longitude",
    "geometry",
    "puntType",
    "vervoerder",
    "canPickup",
    "canDropoff",
    "openingstijden",
]


def _empty_gdf():
    return gpd.GeoDataFrame(columns=COLUMNS, geometry='geometry', crs='EPSG:4326')


@lru_cache(maxsize=None)
def load_carrier(carrier):
    """
    Lees de landelijke cache van één vervoerder als GeoDataFrame (EPSG:4326).

    Eén keer per proces: batch_generate vraagt dezelfde cache voor alle 565
    gemeenten op. Ontbreekt de cache, dan is dat een fout, zodat
    carrier_status in summary.json het laat zien.
    """
    cache_file = carrier_cache_file(carrier)
    if not cache_file.exists():
        raise FileNotFoundError(f"{cache_file.name} ontbreekt; draai het fetch-script voor {carrier}")

    with open(cache_file, 'r', encoding='utf-8') as f:
        cache_data = json.load(f)
    locations = cache_data.get('locations', []) if isinstance(cache_data, dict) else cache_data

    mapper = ROW_MAPPERS.get(carrier, _row_normalized)
    rows = []
    for loc in locations:
        row = mapper(loc)
        row['vervoerder'] = carrier
        rows.append(row)

    if not rows:
        return _empty_gdf()

    df = pd.DataFrame(rows).dropna(subset=['latitude', 'longitude'])
    gdf = gpd.GeoDataFrame(
        df, geometry=gpd.points_from_xy(df['longitude'], df['latitude']), crs='EPSG:4326'
    )
    print(f"  📦 {carrier}: {len(gdf)} punten uit cache geladen")
    return gdf


# ---------- maak 1 dataset van alle gevonden pakketpunten ----------

def get_data_pakketpunten(gemeente, return_carrier_status=False):
    """Alle pakketpunten binnen de grens van `gemeente`, voor alle vervoerders uit CARRIERS."""
    gemeente_geom = get_gemeente_polygon(gemeente).geometry.iloc[0]
    minx, miny, maxx, maxy = gemeente_geom.bounds

    carrier_status = {}
    parts = []

    for carrier in CARRIERS:
        try:
            gdf_all = load_carrier(carrier)
            # Snelle bbox-voorselectie, daarna exact op de gemeentegrens
            candidates = gdf_all.cx[minx:maxx, miny:maxy]
            inside = candidates[candidates.geometry.within(gemeente_geom)]
            parts.append(inside)
            carrier_status[carrier] = {'success': True, 'count': len(inside), 'error': None}
        except Exception as e:
            print(f"  ⚠️  {carrier} laden mislukt: {e}")
            carrier_status[carrier] = {'success': False, 'count': 0, 'error': str(e)}

    parts = [p for p in parts if not p.empty]
    if parts:
        gdf = gpd.GeoDataFrame(pd.concat(parts, ignore_index=True), crs='EPSG:4326')
    else:
        gdf = _empty_gdf()

    for col in ['canPickup', 'canDropoff']:
        if col not in gdf.columns:
            gdf[col] = True
    if 'openingstijden' not in gdf.columns:
        gdf['openingstijden'] = None

    gdf = gdf[COLUMNS]
    print(f"  ✅ {len(gdf)} pakketpunten binnen gemeentegrens '{gemeente}'")

    if return_carrier_status:
        return gdf, carrier_status
    return gdf
