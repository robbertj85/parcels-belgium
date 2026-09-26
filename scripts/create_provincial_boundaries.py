"""
Split the national boundary set into per-province chunks for GitHub compatibility.

The full national boundary file is too large to commit and to load in one go,
so the outlines are grouped per province (Belgium: 10 provinces plus the
Brussels-Capital Region) into files the browser loads in parallel.
"""

import json
from pathlib import Path
from collections import defaultdict
import geopandas as gpd
import pandas as pd
import re
import sys
import unicodedata

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from country_config import NATIONAL_SLUG, WEBAPP_DATA_DIR  # noqa: E402


def slugify(text: str) -> str:
    """Convert province name to URL-safe slug"""
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def create_provincial_boundaries():
    """Split municipal boundaries into provincial chunks"""

    print("🗺️  Creating Provincial Boundary Chunks...")
    print("="*60)

    data_dir = WEBAPP_DATA_DIR
    boundaries_dir = data_dir / "boundaries"
    boundaries_dir.mkdir(exist_ok=True)

    # Load municipalities to get province mapping
    municipalities_file = data_dir.parent / "municipalities.json"
    with open(municipalities_file, 'r', encoding='utf-8') as f:
        municipalities = json.load(f)

    # Create slug -> province mapping (exclude the national row)
    slug_to_province = {
        m['slug']: m['province']
        for m in municipalities
        if m['slug'] != NATIONAL_SLUG
    }

    print(f"📊 Found {len(slug_to_province)} municipalities")

    # Get unique provinces
    provinces = sorted(set(slug_to_province.values()))
    print(f"📊 Provinces: {len(provinces)}")
    for prov in provinces:
        count = sum(1 for p in slug_to_province.values() if p == prov)
        print(f"   {prov}: {count} municipalities")

    # Group boundaries by province
    provincial_boundaries = defaultdict(list)
    total_boundaries = 0
    missing_boundaries = []

    # Process each municipality file
    geojson_files = [f for f in data_dir.glob("*.geojson")
                     if f.stem not in (NATIONAL_SLUG, f'{NATIONAL_SLUG}-boundaries')]

    print(f"\n🔍 Processing {len(geojson_files)} municipality files...")

    for geojson_file in geojson_files:
        slug = geojson_file.stem

        # Skip if not in our mapping
        if slug not in slug_to_province:
            continue

        province = slug_to_province[slug]

        # Read file and extract boundary features
        with open(geojson_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # Find boundary features
        boundary_features = [
            feature for feature in data.get('features', [])
            if feature['properties'].get('type') == 'boundary'
        ]

        if boundary_features:
            provincial_boundaries[province].extend(boundary_features)
            total_boundaries += len(boundary_features)
        else:
            missing_boundaries.append(slug)

    print(f"\n✅ Extracted {total_boundaries} boundary features")

    if missing_boundaries:
        print(f"\n⚠️  No boundaries found for {len(missing_boundaries)} municipalities:")
        for slug in missing_boundaries[:10]:
            print(f"   - {slug}")
        if len(missing_boundaries) > 10:
            print(f"   ... and {len(missing_boundaries) - 10} more")

    # Save provincial files
    print(f"\n💾 Saving {len(provincial_boundaries)} provincial boundary files...")

    file_sizes = {}

    for province, features in provincial_boundaries.items():
        province_slug = slugify(province)

        # Create GeoJSON structure
        province_data = {
            "type": "FeatureCollection",
            "metadata": {
                "province": province,
                "slug": province_slug,
                "generated_at": pd.Timestamp.now().isoformat() + "Z",
                "boundaries_count": len(features),
                "municipalities": [
                    slug for slug, prov in slug_to_province.items()
                    if prov == province
                ]
            },
            "features": features
        }

        # Save file
        output_file = boundaries_dir / f"provincie-{province_slug}.geojson"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(province_data, f, ensure_ascii=False, separators=(",", ":"))

        file_size_mb = output_file.stat().st_size / (1024 * 1024)
        file_sizes[province] = file_size_mb

        print(f"   ✓ {province:20} → {file_size_mb:6.1f} MB ({len(features)} boundaries)")

    # Create index file for browser
    index_data = {
        "generated_at": pd.Timestamp.now().isoformat() + "Z",
        "total_provinces": len(provincial_boundaries),
        "total_boundaries": total_boundaries,
        "provinces": [
            {
                "name": province,
                "slug": slugify(province),
                "file": f"boundaries/provincie-{slugify(province)}.geojson",
                "size_mb": round(file_sizes[province], 2),
                "boundaries_count": len(features)
            }
            for province, features in sorted(provincial_boundaries.items())
        ]
    }

    index_file = boundaries_dir / "index.json"
    with open(index_file, 'w', encoding='utf-8') as f:
        json.dump(index_data, f, ensure_ascii=False, indent=2)

    print(f"\n✅ Index file created: {index_file}")

    # Summary
    total_size_mb = sum(file_sizes.values())
    avg_size_mb = total_size_mb / len(file_sizes) if file_sizes else 0

    print("\n" + "="*60)
    print("📊 Summary:")
    print(f"   Total boundaries: {total_boundaries}")
    print(f"   Provincial files: {len(provincial_boundaries)}")
    print(f"   Total size: {total_size_mb:.1f} MB")
    print(f"   Average size: {avg_size_mb:.1f} MB per province")
    print(f"   Largest: {max(file_sizes.values()):.1f} MB ({max(file_sizes, key=file_sizes.get)})")
    print(f"   Smallest: {min(file_sizes.values()):.1f} MB ({min(file_sizes, key=file_sizes.get)})")
    print("="*60)
    print("✅ Provincial boundaries created successfully!")
    print(f"   Files saved to: {boundaries_dir}/")
    print("="*60)


if __name__ == "__main__":
    create_provincial_boundaries()
