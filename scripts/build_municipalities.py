"""
Bouw de gemeentelijst en gemeentegrenzen voor het ingestelde land.

Bron grenzen: OpenStreetMap, op het admin_level uit country_config
(`boundaries`). Per land verschillen drie dingen, elk een hook hieronder:
  - ophalen: het hele land in één query ("national"; België, 565 gemeenten
    na de fusies van 1 januari 2025) of per regio ("per_region"; Italië,
    ~7.900 comuni is te veel voor één Overpass-query)
  - regio: uit de officiële code ("be_nis": NIS-prefix -> provincie) of
    ruimtelijk, de regio-relatie waarin de gemeente ligt ("spatial")
  - weergavenaam: België kiest per gewest de taal; standaard de OSM-naam

Bron inwoners, in volgorde van voorkeur:
  1. Statbel "Bevolking naar woonplaats" (TF_SOC_POP_STRUCT_<jaar>), alleen
     België, als dat bestand in data/raw/ staat. Statbel blokkeert
     geautomatiseerde downloads, dus dit bestand moet met de hand worden gedownload:
     https://statbel.fgov.be/nl/open-data/bevolking-naar-woonplaats-nationaliteit-burgerlijke-staat-leeftijd-en-geslacht-11
  2. Wikidata (P1082, meest recente waarde), via de wikidata-tag in OSM.

Output:
  data/municipalities_all.json          lijst voor batch_generate
  data/municipality_polygons.geojson    grenzen, gelezen door utils.get_gemeente_polygon
  webapp/public/municipalities.json     lijst voor de webapp (incl. landelijke rij)
  webapp/public/data/geo/municipality_polygons.geojson
                                        grof vereenvoudigde grenzen voor de webapp:
                                        /api/geocode bepaalt daarmee in welke
                                        gemeente een adres ligt

Draai opnieuw na een gemeentefusie (in België per 1 januari na
gemeenteraadsverkiezingen). Ander land:
    PAKKETPUNTEN_COUNTRY=IT python scripts/build_municipalities.py
"""

import csv
import glob
import io
import json
import re
import sys
import unicodedata
import zipfile
from pathlib import Path

import requests
from shapely.geometry import shape, mapping
from shapely.strtree import STRtree

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from country_config import (  # noqa: E402
    CONFIG, DATA_DIR, MUNICIPALITIES_FILE, MUNICIPALITY_POLYGONS_FILE, ROOT, WEBAPP_DATA_DIR,
)
from utils import overpass_post, _extract_geometry_from_overpass  # noqa: E402

BOUNDARIES = CONFIG["boundaries"]

# Vereenvoudiging van de grenzen in graden (~5 m). Houdt de bestanden klein
# genoeg voor de browser zonder dat een pakketpunt aan de grens van gemeente wisselt.
SIMPLIFY_TOLERANCE = 0.00005

# Grovere vereenvoudiging (~20 m) voor de webapp-kopie: alleen voor
# punt-in-gemeente bij adreszoeken, dus klein houden boven precies
WEBAPP_SIMPLIFY_TOLERANCE = 0.0002

# Onder dit aandeel van de verwachte gemeenten is het Overpass-antwoord onvolledig
EXPECTED_MUNICIPALITIES = {"BE": 565, "IT": 7896}
MIN_SHARE = 0.9

WIKIDATA_BATCH = 400

# België: provincie op basis van de eerste cijfers van de NIS-code
PROVINCES = [
    ("21", "Brussels Hoofdstedelijk Gewest"),
    ("23", "Vlaams-Brabant"),
    ("24", "Vlaams-Brabant"),
    ("25", "Waals-Brabant"),
    ("1", "Antwerpen"),
    ("3", "West-Vlaanderen"),
    ("4", "Oost-Vlaanderen"),
    ("5", "Henegouwen"),
    ("6", "Luik"),
    ("7", "Limburg"),
    ("8", "Luxemburg"),
    ("9", "Namen"),
]

# België: gewest op basis van de provincie
BE_REGIONS = {
    "Brussels Hoofdstedelijk Gewest": "Brussels Hoofdstedelijk Gewest",
    "Antwerpen": "Vlaams Gewest", "Vlaams-Brabant": "Vlaams Gewest",
    "West-Vlaanderen": "Vlaams Gewest", "Oost-Vlaanderen": "Vlaams Gewest",
    "Limburg": "Vlaams Gewest",
    "Waals-Brabant": "Waals Gewest", "Henegouwen": "Waals Gewest",
    "Luik": "Waals Gewest", "Luxemburg": "Waals Gewest", "Namen": "Waals Gewest",
}

# België: fusies van 1 januari 2025, nieuwe (of behouden) NIS-code -> NIS-codes
# van voor de fusie. Zo is een Statbel-bestand van vóór 2025 nog bruikbaar.
BE_MERGERS_2025 = {
    "11002": ["11002", "11007"],           # Antwerpen + Borsbeek
    "23106": ["23023", "23024", "23032"],  # Pajottegem: Galmaarden, Gooik, Herne
    "37021": ["37018", "37012"],           # Wingene + Ruiselede
    "37022": ["37015", "37007"],           # Tielt + Meulebeke
    "44086": ["44048", "44012"],           # Nazareth-De Pinte
    "44087": ["44034", "44073"],           # Lochristi + Wachtebeke
    "44088": ["44043", "44040"],           # Merelbeke-Melle
    "46029": ["46014", "44045"],           # Lokeren + Moerbeke
    "46030": ["46003", "46013", "11056"],  # Beveren-Kruibeke-Zwijndrecht
    "71071": ["71057", "71069"],           # Tessenderlo-Ham
    "71072": ["71022", "73040"],           # Hasselt + Kortessem
    "73110": ["73006", "73032"],           # Bilzen-Hoeselt
    "73111": ["73083", "73009"],           # Tongeren-Borgloon
    "82039": ["82003", "82005"],           # Bastogne + Bertogne
}

ALIAS_TAGS = ("name", "name:nl", "name:fr", "name:de", "name:it", "name:en", "alt_name")


def slugify(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    text = re.sub(r"[^a-zA-Z0-9]+", "-", text.lower())
    return text.strip("-")


def to_geometry(relation):
    geom = shape(_extract_geometry_from_overpass(relation))
    return geom if geom.is_valid else geom.buffer(0)


# ---------- hook: weergavenaam ----------

def be_display_name(tags: dict, province: str) -> str:
    """Naam zoals de (Nederlandstalige) Belgische viewer hem toont.

    Vlaanderen: de Nederlandse naam. Wallonië: de officiële lokale naam (Frans
    of Duits), want 'Luik' of 'Bergen' als gemeentenaam verwart meer dan het
    helpt; de Nederlandse naam blijft een zoekalias. Brussel: tweetalig.
    """
    name = tags.get("name", "")
    nl = tags.get("name:nl")
    fr = tags.get("name:fr")
    if province == "Brussels Hoofdstedelijk Gewest":
        if nl and fr and nl != fr:
            return f"{nl} ({fr})"
        return nl or name
    if BE_REGIONS[province] == "Vlaams Gewest":
        return nl or name
    return name


def display_name(tags: dict, region: str) -> str:
    if CONFIG["iso2"] == "BE":
        return be_display_name(tags, region)
    return tags.get("name", "")


# ---------- hook: ophalen ----------

def fetch_municipality_relations(area_filter: str):
    level = BOUNDARIES["admin_level"]
    query = f"""
    [out:json][timeout:600];
    {area_filter}->.searchArea;
    relation(area.searchArea)["admin_level"="{level}"]["boundary"="administrative"];
    out geom;
    """
    data = overpass_post(query, timeout=900)
    return [e for e in data.get("elements", []) if e.get("type") == "relation"]


def fetch_regions():
    """Regio-relaties (naam, id, geometrie) voor per-regio ophalen en ruimtelijke toewijzing."""
    iso2 = CONFIG["iso2"]
    level = BOUNDARIES["region_admin_level"]
    query = f"""
    [out:json][timeout:600];
    area["ISO3166-1"="{iso2}"]["admin_level"="2"]->.country;
    relation(area.country)["admin_level"="{level}"]["boundary"="administrative"];
    out geom;
    """
    data = overpass_post(query, timeout=900)
    regions = [
        {"id": rel["id"], "name": rel["tags"].get("name", str(rel["id"])), "geom": to_geometry(rel)}
        for rel in data.get("elements", []) if rel.get("type") == "relation"
    ]
    print(f"   {len(regions)} regio's ontvangen")
    return regions


def fetch_relations():
    """Alle gemeenterelaties; bij per-regio ophalen met de regio in `_region`."""
    iso2 = CONFIG["iso2"]
    print("🌍 Gemeentegrenzen ophalen via Overpass (kan enkele minuten duren)...")

    if BOUNDARIES["fetch"] == "national":
        relations = fetch_municipality_relations(f'area["ISO3166-1"="{iso2}"]["admin_level"="2"]')
    elif BOUNDARIES["fetch"] == "per_region":
        relations = []
        for region in fetch_regions():
            # Overpass area-id = 3600000000 + relation-id
            batch = fetch_municipality_relations(f"area({3600000000 + region['id']})")
            for rel in batch:
                rel["_region"] = region["name"]
            relations.extend(batch)
            print(f"   {region['name']}: {len(batch)} gemeenten")
    else:
        raise ValueError(f"Onbekende fetch-modus {BOUNDARIES['fetch']}")

    # Een gemeente op een regiogrens kan twee keer terugkomen
    unique = {rel["id"]: rel for rel in relations}
    print(f"   {len(unique)} gemeenten ontvangen")
    return list(unique.values())


# ---------- hook: regio ----------

def be_province(nis: str) -> str:
    for prefix, name in PROVINCES:
        if nis.startswith(prefix):
            return name
    raise ValueError(f"Onbekende NIS-code {nis}")


def assign_regions(relations, geometries):
    """Regio per gemeente volgens country_config `region_resolver`."""
    resolver = BOUNDARIES["region_resolver"]
    if resolver == "be_nis":
        return [be_province(rel["tags"][BOUNDARIES["code_tag"]]) for rel in relations]
    if resolver == "spatial":
        # Per-regio ophalen gaf de regio al mee
        if all("_region" in rel for rel in relations):
            return [rel["_region"] for rel in relations]
        regions = fetch_regions()
        tree = STRtree([r["geom"] for r in regions])
        result = []
        for geom in geometries:
            point = geom.representative_point()
            hits = [i for i in tree.query(point) if regions[i]["geom"].contains(point)]
            result.append(regions[hits[0]]["name"] if hits else CONFIG["all_regions_label"])
        return result
    raise ValueError(f"Onbekende region_resolver {resolver}")


# ---------- inwoners ----------

def load_statbel_population():
    """NIS -> inwoners uit een handmatig gedownload Statbel-bestand, als dat er is."""
    if CONFIG["iso2"] != "BE":
        return {}, None
    files = sorted(glob.glob(str(DATA_DIR / "raw" / "TF_SOC_POP_STRUCT_*")))
    if not files:
        return {}, None
    path = Path(files[-1])
    year = re.search(r"(\d{4})", path.name).group(1)
    if path.suffix == ".zip":
        with zipfile.ZipFile(path) as z:
            inner = next(n for n in z.namelist() if n.lower().endswith((".txt", ".csv")))
            text = z.read(inner).decode("utf-8-sig")
    else:
        text = path.read_text(encoding="utf-8-sig")
    delimiter = "|" if text.count("|") > text.count(";") else ";"
    population = {}
    for row in csv.DictReader(io.StringIO(text), delimiter=delimiter):
        nis = row.get("CD_REFNIS")
        count = row.get("MS_POPULATION")
        if nis and count:
            population[nis] = population.get(nis, 0) + int(count)
    print(f"👥 Statbel {year}: inwoners voor {len(population)} NIS-codes ({path.name})")

    if int(year) < 2025:
        # Oudere bestanden kennen de fusiegemeenten nog niet: tel de delen op
        for new_code, old_codes in BE_MERGERS_2025.items():
            if all(code in population for code in old_codes):
                population[new_code] = sum(population[code] for code in old_codes)
        print(f"   {len(BE_MERGERS_2025)} fusies van 2025 omgerekend naar de nieuwe NIS-codes")
    return population, f"Statbel {year}"


def load_wikidata_population(qids):
    """QID -> (inwoners, jaar), de meest recente P1082-waarde. In batches."""
    qids = [q for q in qids if q]
    best = {}
    for start in range(0, len(qids), WIKIDATA_BATCH):
        values = " ".join(f"wd:{q}" for q in qids[start:start + WIKIDATA_BATCH])
        query = (
            "SELECT ?m ?pop ?date WHERE { VALUES ?m { " + values + " } "
            "?m p:P1082 ?st . ?st ps:P1082 ?pop . OPTIONAL { ?st pq:P585 ?date } }"
        )
        resp = requests.post(
            "https://query.wikidata.org/sparql",
            data={"query": query},
            headers={"Accept": "application/sparql-results+json",
                     "User-Agent": "pakketpunten/1.0 (country viewer)"},
            timeout=180,
        )
        resp.raise_for_status()
        for r in resp.json()["results"]["bindings"]:
            qid = r["m"]["value"].rsplit("/", 1)[1]
            date = r.get("date", {}).get("value", "")
            pop = int(float(r["pop"]["value"]))
            if qid not in best or date > best[qid][1]:
                best[qid] = (pop, date)
    print(f"👥 Wikidata: inwoners voor {len(best)} gemeenten")
    return {q: (p, d[:4] or None) for q, (p, d) in best.items()}


# ---------- main ----------

def main():
    code_tag = BOUNDARIES["code_tag"]
    relations = [r for r in fetch_relations() if r["tags"].get(code_tag)]

    expected = EXPECTED_MUNICIPALITIES.get(CONFIG["iso2"])
    if expected and len(relations) < expected * MIN_SHARE:
        sys.exit(f"❌ Slechts {len(relations)} gemeenten met {code_tag}, verwacht ~{expected}. Afgebroken.")

    geometries = [to_geometry(rel) for rel in relations]
    regions = assign_regions(relations, geometries)

    statbel, statbel_label = load_statbel_population()
    wikidata = {} if statbel else load_wikidata_population(r["tags"].get("wikidata") for r in relations)

    municipalities = []
    features = []
    webapp_features = []
    slugs = set()

    for rel, geom, region in zip(relations, geometries, regions):
        tags = rel["tags"]
        code = tags[code_tag]

        name = display_name(tags, region)
        slug = slugify(name)
        if slug in slugs or slug == CONFIG["national_slug"]:
            slug = f"{slug}-{code}"
        slugs.add(slug)

        aliases = sorted({v for k, v in tags.items() if k in ALIAS_TAGS and v and v != name})

        if statbel:
            population, population_source = statbel.get(code), statbel_label
        else:
            population, year = wikidata.get(tags.get("wikidata"), (None, None))
            population_source = f"Wikidata {year}" if year else "Wikidata"

        record = {
            "name": name,
            "slug": slug,
            "province": region,
            "population": population,
            "population_source": population_source if population else None,
            "code": code,
            "aliases": aliases,
        }
        if CONFIG["iso2"] == "BE":
            record["region"] = BE_REGIONS[region]
        municipalities.append(record)

        features.append({
            "type": "Feature",
            "properties": {"gemeente": name, "slug": slug, "code": code, "province": region},
            "geometry": mapping(geom.simplify(SIMPLIFY_TOLERANCE, preserve_topology=True)),
        })
        webapp_features.append({
            "type": "Feature",
            "properties": {"slug": slug, "gemeente": name},
            "geometry": mapping(geom.simplify(WEBAPP_SIMPLIFY_TOLERANCE, preserve_topology=True)),
        })

    municipalities.sort(key=lambda m: m["name"].lower())

    DATA_DIR.mkdir(exist_ok=True)
    with open(MUNICIPALITIES_FILE, "w", encoding="utf-8") as f:
        json.dump(municipalities, f, ensure_ascii=False, indent=2)
    with open(MUNICIPALITY_POLYGONS_FILE, "w", encoding="utf-8") as f:
        json.dump({"type": "FeatureCollection", "features": features}, f, ensure_ascii=False)

    webapp_list = [{
        "name": CONFIG["national_label"],
        "slug": CONFIG["national_slug"],
        "province": CONFIG["all_regions_label"],
        "population": sum(m["population"] or 0 for m in municipalities),
        "code": None,
    }] + [
        {k: m[k] for k in ("name", "slug", "province", "population", "code", "aliases")}
        for m in municipalities
    ]
    webapp_file = ROOT / "webapp" / "public" / "municipalities.json"
    with open(webapp_file, "w", encoding="utf-8") as f:
        json.dump(webapp_list, f, ensure_ascii=False, indent=2)

    # In een submap: de pipeline-scripts en de matrixpagina lezen elke
    # public/data/*.geojson als gemeentebestand
    webapp_polygons = WEBAPP_DATA_DIR / "geo" / "municipality_polygons.geojson"
    webapp_polygons.parent.mkdir(parents=True, exist_ok=True)
    with open(webapp_polygons, "w", encoding="utf-8") as f:
        # 5 decimalen = ~1 m; genoeg voor punt-in-gemeente
        collection = json.loads(json.dumps({"type": "FeatureCollection", "features": webapp_features}),
                                parse_float=lambda x: round(float(x), 5))
        json.dump(collection, f, ensure_ascii=False, separators=(",", ":"))

    missing_pop = [m["name"] for m in municipalities if not m["population"]]
    size_mb = MUNICIPALITY_POLYGONS_FILE.stat().st_size / 1024 / 1024
    print(f"\n✅ {len(municipalities)} gemeenten → {MUNICIPALITIES_FILE.relative_to(ROOT)}")
    print(f"✅ Grenzen ({size_mb:.1f} MB) → {MUNICIPALITY_POLYGONS_FILE.relative_to(ROOT)}")
    print(f"✅ Webapp-lijst → {webapp_file.relative_to(ROOT)}")
    print(f"✅ Webapp-grenzen ({webapp_polygons.stat().st_size / 1024 / 1024:.1f} MB) → {webapp_polygons.relative_to(ROOT)}")
    by_region = {}
    for m in municipalities:
        by_region[m["province"]] = by_region.get(m["province"], 0) + 1
    for region, n in sorted(by_region.items()):
        print(f"   {region:32} {n:4}")
    if missing_pop:
        print(f"⚠️  Geen inwonertal voor {len(missing_pop)} gemeenten: {', '.join(missing_pop[:10])}")


if __name__ == "__main__":
    main()
