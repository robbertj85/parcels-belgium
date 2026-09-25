

import requests
import os
import pandas as pd, geopandas as gpd
from typing import Any, Dict, Iterable, Optional
import re, json, ast
from geopy.geocoders import Nominatim
from geopy.distance import geodesic
from pathlib import Path
from datetime import datetime


# ---------- loading data ----------

from country_config import CONFIG, MUNICIPALITY_POLYGONS_FILE

# Gemeentegrenzen komen uit een lokaal bestand dat scripts/build_municipalities.py
# eenmalig (en na elke gemeentefusie opnieuw) opbouwt. Geen Overpass-call per
# gemeente meer: sneller, reproduceerbaar, en nodig om later ook ~7.900 Italiaanse
# comuni aan te kunnen.
_gemeente_polygon_cache = {}
_polygon_index = None


def _load_polygon_index() -> dict:
    """Naam, slug, NIS-code en aliassen -> shapely geometry."""
    global _polygon_index
    if _polygon_index is not None:
        return _polygon_index

    if not MUNICIPALITY_POLYGONS_FILE.exists():
        raise FileNotFoundError(
            f"{MUNICIPALITY_POLYGONS_FILE} ontbreekt. Draai eerst: python scripts/build_municipalities.py"
        )

    from shapely.geometry import shape

    with open(MUNICIPALITY_POLYGONS_FILE, 'r', encoding='utf-8') as f:
        collection = json.load(f)

    municipalities_file = MUNICIPALITY_POLYGONS_FILE.parent / "municipalities_all.json"
    aliases = {}
    if municipalities_file.exists():
        with open(municipalities_file, 'r', encoding='utf-8') as f:
            for m in json.load(f):
                aliases[m['slug']] = m.get('aliases', [])

    index = {}
    for feature in collection['features']:
        props = feature['properties']
        geom = shape(feature['geometry'])
        if not geom.is_valid:
            geom = geom.buffer(0)
        keys = [props['gemeente'], props['slug'], props.get('code')] + aliases.get(props['slug'], [])
        for key in keys:
            if key:
                index.setdefault(key.lower(), (props['gemeente'], geom))
    _polygon_index = index
    return index


# Initialize Nominatim geolocator (with user agent)
_nominatim_geolocator = Nominatim(user_agent="pakketpunten_belgie")


def get_lat_lon(gemeente_naam: str) -> tuple:
    """
    Get latitude and longitude for a municipality using Nominatim geocoding.

    Args:
        gemeente_naam: Name of the municipality

    Returns:
        tuple: (latitude, longitude)

    Raises:
        ValueError: If geocoding fails
    """
    import time

    # Land toevoegen voor een eenduidig resultaat
    query = f"{gemeente_naam}, {CONFIG['name']}"

    try:
        location = _nominatim_geolocator.geocode(query, timeout=10)
        if location:
            # Rate limit compliance - 1 request per second
            time.sleep(1)
            return (location.latitude, location.longitude)
        else:
            raise ValueError(f"Could not geocode '{gemeente_naam}'")
    except Exception as e:
        raise ValueError(f"Geocoding failed for '{gemeente_naam}': {e}")

# Overpass mirrors, tried in order. overpass-api.de answers HTTP 406 to a
# request without a User-Agent, and every mirror rate-limits with 429, so the
# name and the backoff below are load-bearing rather than politeness: the
# Budbee OSM source silently returned nothing for weeks without them.
OVERPASS_SERVERS = (
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
)
OVERPASS_USER_AGENT = "pakketpunten_belgie/1.0"


def overpass_post(
    query: str,
    *,
    timeout: float = 90,
    max_retries: int = 3,
    retry_delay: float = 2,
    servers: Optional[Iterable[str]] = None,
) -> Dict[str, Any]:
    """
    POST een Overpass QL query en geef de gedecodeerde JSON terug.

    Loopt de mirrors in volgorde af en probeert een mirror opnieuw bij
    429/503/504 met exponentiele backoff voordat de volgende aan de beurt is.

    Raises
    ------
    ValueError
        Wanneer alle mirrors gefaald hebben.
    """
    import time

    errors = []

    for server in (servers or OVERPASS_SERVERS):
        for attempt in range(max_retries):
            try:
                response = requests.post(
                    server,
                    data={"data": query},
                    headers={"User-Agent": OVERPASS_USER_AGENT},
                    timeout=timeout,
                )
                response.raise_for_status()
                return response.json()

            except requests.exceptions.HTTPError as e:
                status = e.response.status_code if e.response is not None else None
                if status in (429, 503, 504) and attempt < max_retries - 1:
                    wait_time = retry_delay * (2 ** attempt)
                    print(f"   ⏳ {server} HTTP {status}, retry in {wait_time:.0f}s "
                          f"(poging {attempt + 1}/{max_retries})...")
                    time.sleep(wait_time)
                    continue
                errors.append(f"{server}: HTTP {status}")
                break

            except (requests.RequestException, ValueError) as e:
                if attempt < max_retries - 1:
                    wait_time = retry_delay * (2 ** attempt)
                    print(f"   ⏳ {server} gaf een fout ({e}), retry in {wait_time:.0f}s "
                          f"(poging {attempt + 1}/{max_retries})...")
                    time.sleep(wait_time)
                    continue
                errors.append(f"{server}: {e}")
                break

    raise ValueError("Overpass API onbereikbaar - " + "; ".join(errors))


def get_gemeente_polygon(gemeente_naam: str, country_hint: str = None):
    """
    Geef de gemeentegrens als GeoDataFrame (EPSG:4326).

    Zoekt op naam, slug, NIS-code of alias in data/municipality_polygons.geojson.

    Raises
    ------
    ValueError
        Wanneer de gemeente niet in het grenzenbestand staat.
    """
    key = gemeente_naam.lower()
    if key in _gemeente_polygon_cache:
        return _gemeente_polygon_cache[key]

    entry = _load_polygon_index().get(key)
    if entry is None:
        raise ValueError(f"Gemeente '{gemeente_naam}' niet gevonden in {MUNICIPALITY_POLYGONS_FILE.name}.")

    name, geom = entry
    gdf = gpd.GeoDataFrame({'gemeente': [name]}, geometry=[geom], crs="EPSG:4326")
    _gemeente_polygon_cache[key] = gdf
    return gdf


def _extract_geometry_from_overpass(relation):
    """
    Extracts GeoJSON geometry from an Overpass API relation response.

    Overpass returns relations with members (ways) that need to be connected
    end-to-end to form the complete municipality boundary polygon.
    """
    from shapely.geometry import Polygon, MultiPolygon, LineString, mapping
    from shapely.ops import linemerge, unary_union, polygonize

    # Collect all outer and inner ways
    outer_ways = []
    inner_ways = []

    for member in relation.get('members', []):
        if member['type'] != 'way':
            continue

        role = member.get('role', '')
        geometry = member.get('geometry', [])

        if not geometry:
            continue

        # Convert coordinate list to coordinates
        coords = [(point['lon'], point['lat']) for point in geometry]

        if role == 'outer':
            outer_ways.append(coords)
        elif role == 'inner':
            inner_ways.append(coords)

    if not outer_ways:
        raise ValueError("Geen outer ways gevonden in relation.")

    # Connect outer ways end-to-end to form continuous rings
    # OSM relations split boundaries into multiple ways that connect
    outer_lines = [LineString(coords) for coords in outer_ways if len(coords) >= 2]

    if not outer_lines:
        raise ValueError("Geen geldige outer ways gevonden.")

    # Merge connected linestrings into continuous lines
    merged = linemerge(outer_lines)

    # Convert merged lines to polygon(s)
    if merged.geom_type == 'LineString':
        # Single ring - create one polygon
        if not merged.is_closed:
            # Close the ring
            coords = list(merged.coords)
            coords.append(coords[0])
            merged = LineString(coords)

        geom = Polygon(merged)

    elif merged.geom_type == 'MultiLineString':
        # Multiple rings - try to polygonize
        polygons = list(polygonize(merged))

        if not polygons:
            # If polygonize fails, try creating polygons from closed rings
            polygons = []
            for line in merged.geoms:
                if line.is_closed or line.coords[0] == line.coords[-1]:
                    try:
                        polygons.append(Polygon(line))
                    except:
                        continue

        if len(polygons) == 0:
            raise ValueError("Kon geen polygons maken uit outer ways.")
        elif len(polygons) == 1:
            geom = polygons[0]
        else:
            geom = MultiPolygon(polygons)
    else:
        raise ValueError(f"Unexpected geometry type after merge: {merged.geom_type}")

    # Convert to GeoJSON
    return mapping(geom)


def get_gemeente_geometry(gemeente_naam: str, mode: str = "bbox", country_hint: str = None):
    """
    Haalt geometrische info van een gemeente uit OpenStreetMap via admin_level=8 boundary.

    Deze functie haalt de EXACTE gemeentegrens (admin_level=8) op en berekent daaruit
    de bbox of circle, zodat de zoekparameters consistent zijn met de boundary filtering.

    Falls back to Nominatim geocoding if Overpass API fails (e.g., timeout, rate limit).

    Parameters
    ----------
    gemeente_naam : str
        Naam van de gemeente, bv. "Utrecht".
    mode : str
        "bbox"   -> retourneert (lat_min, lon_min, lat_max, lon_max)
        "circle" -> retourneert (center_lat, center_lon, radius_meters)
    country_hint : str
        Niet meer gebruikt (grenzen komen uit het lokale bestand).

    Returns
    -------
    tuple
        Afhankelijk van mode:
        - bbox   -> (lat_min, lon_min, lat_max, lon_max)
        - circle -> (center_lat, center_lon, radius_meters)
    """
    # Try to get the exact municipality boundary (admin_level=8) from Overpass API
    try:
        gdf = get_gemeente_polygon(gemeente_naam, country_hint)
    except (ValueError, Exception) as e:
        # Overpass API failed - fall back to Nominatim geocoding with generous search radius
        print(f"  ⚠️  Overpass API unavailable for '{gemeente_naam}': {e}")
        print(f"  🔄 Falling back to Nominatim geocoding with generous search area")

        # Use Nominatim to get approximate center point
        lat, lon = get_lat_lon(gemeente_naam)

        if mode == "bbox":
            # Create a generous bbox around the center point (~20km radius)
            # 1 degree ≈ 111 km, so 0.18 degrees ≈ 20 km
            bbox_radius_deg = 0.18
            return (
                lat - bbox_radius_deg,  # bottom_left_lat
                lon - bbox_radius_deg,  # bottom_left_lon
                lat + bbox_radius_deg,  # top_right_lat
                lon + bbox_radius_deg   # top_right_lon
            )
        elif mode == "circle":
            # Return center with 20km radius (generous to capture all points)
            return lat, lon, 20000  # 20 km in meters
        else:
            raise ValueError(f"Onbekende mode: {mode}")

    # Extract bounds from the polygon
    bounds = gdf.total_bounds  # [minx, miny, maxx, maxy]
    west, south, east, north = bounds

    bottom_left_lat = south
    bottom_left_lon = west
    top_right_lat = north
    top_right_lon = east

    if mode == "bbox":
        return bottom_left_lat, bottom_left_lon, top_right_lat, top_right_lon

    elif mode == "circle":
        # Middelpunt
        center_lat = (south + north) / 2.0
        center_lon = (west + east) / 2.0
        center = (center_lat, center_lon)

        # Hoeken
        corners = [(south, west), (south, east), (north, west), (north, east)]

        # Radius = verste hoek
        radius_m = max(geodesic(center, c).meters for c in corners)

        return center_lat, center_lon, int(radius_m)

    else:
        raise ValueError("mode moet 'bbox' of 'circle' zijn.")

# ---------- helper functions for api calls ----------

def ensure_no_proxy(domains: Iterable[str]) -> None:
    """
    Voeg domeinen toe aan NO_PROXY zodat requests ze niet via een proxy stuurt.
    """
    no_proxy = os.environ.get("NO_PROXY", "")
    current = {d.strip() for d in no_proxy.split(",") if d.strip()}
    for d in domains:
        if d not in current:
            current.add(d)
    os.environ["NO_PROXY"] = ",".join(sorted(current))

def make_session(disable_env_proxy: bool = True) -> requests.Session:
    """
    Maak een requests.Session die (optioneel) geen omgevingsproxy’s gebruikt.
    """
    s = requests.Session()
    if disable_env_proxy:
        s.trust_env = False  # negeer systeem-/omgevingsproxy's
    return s

def fetch_json(
    url: str,
    *,
    params: Optional[Dict[str, Any]] = None,
    headers: Optional[Dict[str, str]] = None,
    no_proxy_domains: Optional[Iterable[str]] = None,
    timeout: float = 20.0,
    session: Optional[requests.Session] = None,
) -> Any:
    """
    Haal JSON op van een API-endpoint met nette defaults:
    - optioneel bepaalde domeinen aan NO_PROXY toevoegen
    - requests.Session herbruikbaar
    - expliciet geen proxy via proxies={"http": None, "https": None}
    """
    if no_proxy_domains:
        ensure_no_proxy(no_proxy_domains)

    sess = session or make_session(disable_env_proxy=True)
    hdrs = {"Accept": "application/json"}
    if headers:
        hdrs.update(headers)

    resp = sess.get(
        url,
        params=params,
        headers=hdrs,
        timeout=timeout,
        proxies={"http": None, "https": None}  # expliciet geen proxy
    )
    resp.raise_for_status()
    return resp.json()


# ---------- helper functions voor webscraping ----------

def extract_js_array(js_text, varname="locations"):
    "parsed 'var locations = [...]' uit de JS/HTML "
    m = re.search(rf'\b(var|let|const)\s+{re.escape(varname)}\s*=', js_text)
    if not m:
        m = re.search(rf'\b{re.escape(varname)}\s*=', js_text)
        if not m:
            raise ValueError(f"Kon '{varname} =' niet vinden.")
    i = m.end()
    while i < len(js_text) and js_text[i].isspace():
        i += 1
    if js_text[i] != "[":
        i = js_text.find("[", i)
    depth, start = 0, i
    in_str, quote, escape = False, "", False
    for j, ch in enumerate(js_text[i:], start=i):
        if in_str:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == quote:
                in_str = False
        else:
            if ch in ('"', "'"):
                in_str, quote = True, ch
            elif ch == "[":
                depth += 1
            elif ch == "]":
                depth -= 1
                if depth == 0:
                    return js_text[start:j+1]
    raise ValueError("Geen sluitende ] gevonden.")

def _slice_bracket_array(s: str, start_idx: int) -> str:
    depth = 0; in_str = False; esc = False; quote = ""
    for j in range(start_idx, len(s)):
        c = s[j]
        if in_str:
            if esc: esc = False
            elif c == "\\": esc = True
            elif c == quote: in_str = False
        else:
            if c in ("'", '"'):
                in_str = True; quote = c
            elif c == "[": depth += 1
            elif c == "]":
                depth -= 1
                if depth == 0:
                    return s[start_idx:j+1]
    raise ValueError("Geen sluitende ] gevonden.")

def _jsonish(a: str) -> str:
    # trailing comma's vóór ] of }
    a = re.sub(r',\s*([\]\}])', r'\1', a)
    # unicode line separators
    a = a.replace('\u2028','').replace('\u2029','')
    return a

def _parse_array_str(a: str):
    # 1) probeer JSON
    try:
        return json.loads(a)
    except json.JSONDecodeError:
        pass
    # 2) lichte schoonmaak en opnieuw
    a2 = _jsonish(a)
    try:
        return json.loads(a2)
    except json.JSONDecodeError:
        pass
    # 3) laatste redmiddel: Python literal
    a3 = a2.replace("true","True").replace("false","False").replace("null","None")
    return ast.literal_eval(a3)

def parse_locations_any(text: str, key: str = "locations"):
    s = text.strip()

    # Case 1: volledige assignment aanwezig
    m = re.search(rf'\b(var|let|const)\s+{re.escape(key)}\s*=', s)
    if not m:
        m = re.search(rf'\b{re.escape(key)}\s*=', s)
    if m:
        lb = s.find('[', m.end())
        if lb == -1:
            raise ValueError(f"Geen '[' na {key}= gevonden.")
        arr_txt = _slice_bracket_array(s, lb)
        return _parse_array_str(arr_txt)

    # Case 2: “losse rijen” – wrap tot een array van arrays
    wrapped = "[" + s.strip().strip(",") + "]"
    return _parse_array_str(wrapped)

def extract_points_array(text: str) -> list:
    """
    Zoekt in Next.js Flight (RSC) push-blokken naar een "points":[ ... ] JSON-array
    en geeft die terug als Python-lijst met dicts.
    """
    # 1) Vind alle Flight-snippers: self.__next_f.push([1,"..."])
    pattern = re.compile(r'self\.__next_f\.push\(\[1,"(.*?)"\]\)', re.DOTALL)
    matches = pattern.findall(text)

    # 2) Unescape de JS-string via JSON-decoder (behandelt \" en \uXXXX)
    decoded_chunks = []
    for m in matches:
        try:
            decoded_chunks.append(json.loads(f'"{m}"'))
        except json.JSONDecodeError:
            pass  # niet erg; ga door

    # 3) Zoek in elke gedecodeerde chunk naar "points":[ ... ] en pak de array
    for chunk in decoded_chunks:
        idx = chunk.find('"points"')
        if idx == -1:
            continue
        # zoek de eerste '[' na "points"
        lb = chunk.find('[', idx)
        if lb == -1:
            continue

        # balans-parser over de array (strings/escapes correct afhandelen)
        depth = 0
        in_str = False
        esc = False
        end = None
        for j in range(lb, len(chunk)):
            c = chunk[j]
            if in_str:
                if esc:
                    esc = False
                elif c == '\\':
                    esc = True
                elif c == '"':
                    in_str = False
            else:
                if c == '"':
                    in_str = True
                elif c == '[':
                    depth += 1
                elif c == ']':
                    depth -= 1
                    if depth == 0:
                        end = j + 1
                        break
        if end:
            arr_txt = chunk[lb:end]
            try:
                return json.loads(arr_txt)  
            except json.JSONDecodeError:
                # soms zitten er JS-achtige trailing commas of \u2028; probeer lichte schoonmaak
                cleaned = arr_txt.replace('\u2028', '').replace('\u2029', '')
                return json.loads(cleaned)

    raise ValueError("Kon geen 'points' array vinden in de RSC payload.")


# ---------- cleaning / transforming ----------

def json_to_dataframe(data) -> pd.DataFrame:
    """
    Zet API JSON-data om naar een Pandas DataFrame.
    
    Werking:
    - Detecteert of de response een dict of een list is.
    - Zoekt in dicts naar bekende sleutels ('data', 'items', 'results', 'locations').
    - Vindt de eerste lijst met records.
    - Normaliseert nested JSON naar een platte tabel.
    
    Parameters
    ----------
    data : dict of list
        JSON-data uit een API-response
    
    Returns
    -------
    pd.DataFrame
        DataFrame met de genormaliseerde records
    """
    if isinstance(data, dict):
        items = (
            data.get("data")
            or data.get("items")
            or data.get("results")
            or data.get("locations")
            or data
        )
        # Als items nog steeds een dict is, probeer een lijst te vinden
        if isinstance(items, dict):
            list_candidates = [v for v in items.values() if isinstance(v, list)]
            items = list_candidates[0] if list_candidates else []
    elif isinstance(data, list):
        items = data
    else:
        items = []

    if not isinstance(items, list) or len(items) == 0:
        raise RuntimeError(
            "Geen locaties gevonden in de API-respons. Controleer de structuur van de JSON."
        )

    # DataFrame maken (vlakken geneste velden af)
    df = pd.json_normalize(items)
    return df

def df_to_gdf(df: pd.DataFrame, vervoerder) -> gpd.GeoDataFrame:
    """
    Zet een DataFrame met latitude/longitude om naar een GeoDataFrame.
    Detecteert automatisch de juiste kolommen en hernoemt ze naar:
    - locatieNaam
    - straatNaam
    - latitude
    - longitude
    Voegt een extra kolom toe met vervoerder
    Output: GeoDataFrame met CRS=WGS84 (EPSG:4326)
    """
    # Kandidaten zoeken
    lat_col_candidates = [c for c in df.columns if c.lower().endswith(("lat","latitude"))]
    lon_col_candidates = [c for c in df.columns if c.lower().endswith(("lon","lng","longitude"))]

    if not lat_col_candidates or not lon_col_candidates:
        raise RuntimeError("Kon latitude/longitude kolommen niet automatisch vinden.")

    lat_col = lat_col_candidates[0]
    lon_col = lon_col_candidates[0]

    # Optionele kolommen 
    name_col_candidates = [c for c in df.columns if any(k in c.lower() for k in ["naam", "name","shopname","label","bedrijf","store"])]
    cap_col_candidates = [c for c in df.columns if any(k in c.lower() for k in ["allownrparcels", "operational_status.status"])]
    type_col_candidates = [c for c in df.columns if any(k in c.lower() for k in ["point_type", "shoptype", "type"])]
        
    # eerst specifiek zoeken naar 'straat' of 'street'
    street_candidates = [c for c in df.columns if any(k in c.lower() for k in ["street", "straat"])]
    nr_col_candidates = [c for c in df.columns if any(k in c.lower() for k in ["address.number", "number", "nummer", "nr"])]
    
    
    if street_candidates:
        addr_col_candidates = street_candidates 
    
    else:
        # pas als er geen 'straat' kolommen zijn, zoeken op bredere set
        addr_col_candidates = [c for c in df.columns if any(k in c.lower() for k in ["address", "adres", "vicinity"])]
        
    name_col = name_col_candidates[0] if name_col_candidates else None
    addr_col = addr_col_candidates[0] if addr_col_candidates else None
    cap_col = cap_col_candidates[0] if cap_col_candidates else None
    type_col = type_col_candidates[0] if type_col_candidates else None

    nr_col = None
    if nr_col_candidates:
        nr_col = nr_col_candidates[0]
        # uitzondering voor DHL
        if nr_col.lower() == "allownrparcels" and len(nr_col_candidates) > 1:
            nr_col = nr_col_candidates[1]
  

    # Subset + hernoemen
    rename_map = {}
    if name_col: rename_map[name_col] = "locatieNaam"
    if addr_col: rename_map[addr_col] = "straatNaam"
    if nr_col: rename_map[nr_col] = "straatNr"
    rename_map[lat_col] = "latitude"
    rename_map[lon_col] = "longitude"
    rename_map[cap_col] = "capaciteit"
    rename_map[type_col] = "puntType"

    # alleen kolommen behouden die in dataframe zitten
    valid_cols = [col for col in rename_map.keys() if col in df.columns]
    # selecteren en hernoemen
    df = df[valid_cols].rename(columns=rename_map)
    print(df.columns)


    # GeoDataFrame maken
    gdf = gpd.GeoDataFrame(
        df,
        geometry=gpd.points_from_xy(df["longitude"], df["latitude"]),
        crs="EPSG:4326"
    )

    # add name of vervoerder 
    gdf["vervoerder"] = vervoerder

    return gdf


# ---------- Output ----------

def save_output(kaartlagen, filename, format="gpkg"):
    output_dir = Path(__file__).resolve().parent / "output"
    output_dir.mkdir(exist_ok=True)
    
    if format == "gpkg":
        path = output_dir / f"{filename}.gpkg"
        for i, (name, gdf) in enumerate(kaartlagen.items()):
            mode = "w" if i == 0 else "a"
            gdf.to_file(path, layer=name, driver="GPKG", mode=mode)
        print(f"✅ Data opgeslagen als GeoPackage: {path}")

    elif format == "geojson":
        for name, gdf in kaartlagen.items():
            path = output_dir / f"{filename}_{name}.geojson"
            gdf.to_file(path, driver="GeoJSON")
            print(f"🌍 Data opgeslagen als GeoJSON: {path}")
    else:
        raise ValueError("Ongeldig formaat: kies 'gpkg' of 'geojson'")