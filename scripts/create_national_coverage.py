"""
Precompute the national coverage areas: the union of 300, 400 and 500 m circles
around every parcel point in the country.

The webapp draws coverage in the browser with Turf for at most MAX_BUFFER_POINTS
points (webapp/lib/mapLimits.ts); for all of Belgium that takes 30-40 s per
radius and freezes the page. GEOS does the same union here in seconds, so the
national view shows these files instead, as long as every filter is at its
default (all carriers, all point types, all services). Any other filter
combination falls back to drawing the points in view.

Reads webapp/public/data/<national_slug>.geojson (create_national_overview.py),
writes webapp/public/data/geo/coverage_<radius>.geojson.

    python scripts/create_national_coverage.py
"""

import json
import sys
import time
from pathlib import Path

import geopandas as gpd
from shapely.geometry import mapping
from shapely.ops import unary_union

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from country_config import METRIC_CRS, NATIONAL_SLUG, WEBAPP_DATA_DIR  # noqa: E402

RADII = (300, 400, 500)
# Simplify the union outline by this many metres: invisible at national zoom
# levels, and it keeps each file to a few MB
SIMPLIFY_M = 5
OUTPUT_DIR = WEBAPP_DATA_DIR / "geo"


def rounded(geometry, decimals=5):
    """GeoJSON geometry with coordinates rounded to ~1 m."""
    return json.loads(json.dumps(mapping(geometry)), parse_float=lambda x: round(float(x), decimals))


def main():
    source = WEBAPP_DATA_DIR / f"{NATIONAL_SLUG}.geojson"
    with open(source, encoding="utf-8") as f:
        national = json.load(f)

    points = [f for f in national["features"] if f["properties"].get("type") == "pakketpunt"]
    gdf = gpd.GeoDataFrame.from_features(points, crs="EPSG:4326").to_crs(METRIC_CRS)
    # Carriers often share one address; one circle per location is enough
    locations = gdf.geometry.drop_duplicates()
    print(f"📍 {len(points)} points, {len(locations)} distinct locations")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for radius in RADII:
        started = time.time()
        coverage = unary_union(locations.buffer(radius, resolution=8)).simplify(SIMPLIFY_M)
        wgs = gpd.GeoSeries([coverage], crs=METRIC_CRS).to_crs("EPSG:4326").iloc[0]

        output = OUTPUT_DIR / f"coverage_{radius}.geojson"
        collection = {
            "type": "FeatureCollection",
            "metadata": {
                "radius_m": radius,
                "generated_from": source.name,
                "generated_at": national["metadata"].get("generated_at"),
                "points": len(points),
            },
            "features": [{
                "type": "Feature",
                "properties": {"type": f"coverage_{radius}m", "buffer_m": radius},
                "geometry": rounded(wgs),
            }],
        }
        with open(output, "w", encoding="utf-8") as f:
            json.dump(collection, f, ensure_ascii=False, separators=(",", ":"))

        size_mb = output.stat().st_size / 1024 / 1024
        print(f"✅ {radius} m: {size_mb:.1f} MB in {time.time() - started:.1f} s → {output.relative_to(WEBAPP_DATA_DIR.parent.parent.parent)}")


if __name__ == "__main__":
    main()
