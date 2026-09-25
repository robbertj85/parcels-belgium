"""
Bouw de gemeentelijst en gemeentegrenzen voor België.

Bron grenzen: OpenStreetMap (admin_level=8, 565 gemeenten na de fusies van
1 januari 2025), in één Overpass-query. Elke relatie draagt de NIS-code
(`ref:INS`), waaruit ook de provincie volgt.

Bron inwoners, in volgorde van voorkeur:
  1. Statbel "Bevolking naar woonplaats" (TF_SOC_POP_STRUCT_<jaar>), als dat
     bestand in data/raw/ staat. Statbel blokkeert geautomatiseerde downloads,
     dus dit bestand moet met de hand worden gedownload:
     https://statbel.fgov.be/nl/open-data/bevolking-naar-woonplaats-nationaliteit-burgerlijke-staat-leeftijd-en-geslacht-11
  2. Wikidata (P1082, meest recente waarde), via de wikidata-tag in OSM.

Output:
  data/municipalities_all.json          lijst voor batch_generate
  data/municipality_polygons.geojson    grenzen, gelezen door utils.get_gemeente_polygon
  webapp/public/municipalities.json     lijst voor de webapp (incl. landelijke rij)

Draai opnieuw na een gemeentefusie (in België per 1 januari na
gemeenteraadsverkiezingen).
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

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from country_config import (  # noqa: E402
    CONFIG, DATA_DIR, MUNICIPALITIES_FILE, MUNICIPALITY_POLYGONS_FILE, ROOT,
)
from utils import overpass_post, _extract_geometry_from_overpass  # noqa: E402

# Vereenvoudiging van de grenzen in graden (~5 m). Houdt de bestanden klein
# genoeg voor de browser zonder dat een pakketpunt aan de grens van gemeente wisselt.
SIMPLIFY_TOLERANCE = 0.00005

# Provincie op basis van de eerste cijfers van de NIS-code
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

# Gewest op basis van de provincie
REGIONS = {
    "Brussels Hoofdstedelijk Gewest": "Brussels Hoofdstedelijk Gewest",
    "Antwerpen": "Vlaams Gewest", "Vlaams-Brabant": "Vlaams Gewest",
    "West-Vlaanderen": "Vlaams Gewest", "Oost-Vlaanderen": "Vlaams Gewest",
    "Limburg": "Vlaams Gewest",
    "Waals-Brabant": "Waals Gewest", "Henegouwen": "Waals Gewest",
    "Luik": "Waals Gewest", "Luxemburg": "Waals Gewest", "Namen": "Waals Gewest",
}


def province_for(nis: str) -> str:
    for prefix, name in PROVINCES:
        if nis.startswith(prefix):
            return name
    raise ValueError(f"Onbekende NIS-code {nis}")


def slugify(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    text = re.sub(r"[^a-zA-Z0-9]+", "-", text.lower())
    return text.strip("-")


def display_name(tags: dict, province: str) -> str:
    """Naam zoals de (Nederlandstalige) viewer hem toont.

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
    if REGIONS[province] == "Vlaams Gewest":
        return nl or name
    return name


def fetch_relations():
    iso2 = CONFIG["iso2"]
    query = f"""
    [out:json][timeout:300];
    area["ISO3166-1"="{iso2}"]["admin_level"="2"]->.country;
    relation(area.country)["admin_level"="8"]["boundary"="administrative"];
    out geom;
    """
    print("🌍 Gemeentegrenzen ophalen via Overpass (kan enkele minuten duren)...")
    data = overpass_post(query, timeout=600)
    relations = [e for e in data.get("elements", []) if e.get("type") == "relation"]
    print(f"   {len(relations)} gemeenten ontvangen")
    return relations


def load_statbel_population():
    """NIS -> inwoners uit een handmatig gedownload Statbel-bestand, als dat er is."""
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
    return population, f"Statbel {year}"


def load_wikidata_population(qids):
    """QID -> (inwoners, jaar), de meest recente P1082-waarde."""
    values = " ".join(f"wd:{q}" for q in qids if q)
    query = (
        "SELECT ?m ?pop ?date WHERE { VALUES ?m { " + values + " } "
        "?m p:P1082 ?st . ?st ps:P1082 ?pop . OPTIONAL { ?st pq:P585 ?date } }"
    )
    resp = requests.post(
        "https://query.wikidata.org/sparql",
        data={"query": query},
        headers={"Accept": "application/sparql-results+json",
                 "User-Agent": "pakketpunten_belgie/1.0"},
        timeout=120,
    )
    resp.raise_for_status()
    best = {}
    for r in resp.json()["results"]["bindings"]:
        qid = r["m"]["value"].rsplit("/", 1)[1]
        date = r.get("date", {}).get("value", "")
        pop = int(float(r["pop"]["value"]))
        if qid not in best or date > best[qid][1]:
            best[qid] = (pop, date)
    print(f"👥 Wikidata: inwoners voor {len(best)} gemeenten")
    return {q: (p, d[:4] or None) for q, (p, d) in best.items()}


def main():
    relations = fetch_relations()
    if len(relations) < 500:
        sys.exit(f"❌ Slechts {len(relations)} gemeenten ontvangen, verwacht ~565. Afgebroken.")

    statbel, statbel_label = load_statbel_population()
    wikidata = {} if statbel else load_wikidata_population(r["tags"].get("wikidata") for r in relations)

    municipalities = []
    features = []
    slugs = set()

    for rel in relations:
        tags = rel["tags"]
        nis = tags.get("ref:INS")
        if not nis:
            print(f"   ⚠️  Geen NIS-code voor {tags.get('name')}, overgeslagen")
            continue

        province = province_for(nis)
        name = display_name(tags, province)
        slug = slugify(name)
        if slug in slugs:
            slug = f"{slug}-{nis}"
        slugs.add(slug)

        aliases = sorted({v for k, v in tags.items()
                          if k in ("name", "name:nl", "name:fr", "name:de", "alt_name") and v and v != name})

        if statbel:
            population, population_source = statbel.get(nis), statbel_label
        else:
            population, year = wikidata.get(tags.get("wikidata"), (None, None))
            population_source = f"Wikidata {year}" if year else "Wikidata"

        geom = shape(_extract_geometry_from_overpass(rel))
        if not geom.is_valid:
            geom = geom.buffer(0)
        geom = geom.simplify(SIMPLIFY_TOLERANCE, preserve_topology=True)

        municipalities.append({
            "name": name,
            "slug": slug,
            "province": province,
            "region": REGIONS[province],
            "population": population,
            "population_source": population_source if population else None,
            "code": nis,
            "aliases": aliases,
        })
        features.append({
            "type": "Feature",
            "properties": {"gemeente": name, "slug": slug, "code": nis, "province": province},
            "geometry": mapping(geom),
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

    missing_pop = [m["name"] for m in municipalities if not m["population"]]
    size_mb = MUNICIPALITY_POLYGONS_FILE.stat().st_size / 1024 / 1024
    print(f"\n✅ {len(municipalities)} gemeenten → {MUNICIPALITIES_FILE.relative_to(ROOT)}")
    print(f"✅ Grenzen ({size_mb:.1f} MB) → {MUNICIPALITY_POLYGONS_FILE.relative_to(ROOT)}")
    print(f"✅ Webapp-lijst → {webapp_file.relative_to(ROOT)}")
    by_province = {}
    for m in municipalities:
        by_province[m["province"]] = by_province.get(m["province"], 0) + 1
    for prov, n in sorted(by_province.items()):
        print(f"   {prov:32} {n:4}")
    if missing_pop:
        print(f"⚠️  Geen inwonertal voor {len(missing_pop)} gemeenten: {', '.join(missing_pop[:10])}")


if __name__ == "__main__":
    main()
