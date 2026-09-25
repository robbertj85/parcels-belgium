"""
Fetch all DPD parcel shop and locker locations in the configured country.

Unlike DHL which requires a grid-based approach due to API limits,
DPD's public API provides a simple 'getAll' endpoint that returns
all locations in one request.

API: https://pickup.dpd.cz/api/getAll?country=<ISO numeric>
     (56 = Belgium, 528 = Netherlands, 380 = Italy)

No authentication required.
"""

import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parent.parent))
from country_config import CONFIG  # noqa: E402


import json
import requests
from pathlib import Path
from datetime import datetime
from typing import Dict, List
from collections import defaultdict


def fetch_all_dpd_locations() -> List[Dict]:
    """
    Fetch all DPD parcel shops and lockers in the configured country.

    Returns
    -------
    list of dict
        Complete list of DPD locations with full details
    """
    print("="*80)
    print("DPD COMPLETE LOCATION FETCH")
    print("="*80)
    print()

    print("📡 Fetching all DPD locations from public API...")
    print("   Endpoint: https://pickup.dpd.cz/api/getAll")
    print(f"   Country: {CONFIG['name']} (ISO 3166-1: {CONFIG['dpd']['country_code']})")
    print()

    try:
        response = requests.get(
            "https://pickup.dpd.cz/api/getAll",
            params={"country": CONFIG["dpd"]["country_code"]},
            timeout=60  # Longer timeout for complete dataset
        )
        response.raise_for_status()
        data = response.json()

        # Extract locations from response
        status = data.get('status')
        count = data.get('count', 0)
        locations = data.get('data', {}).get('items', [])

        if status != 'ok':
            print(f"❌ API returned status: {status}")
            return []

        if not locations:
            print(f"⚠️  No locations returned (expected ~1900+)")
            return []

        print(f"✅ Successfully fetched {len(locations)} DPD locations")
        print(f"   API reported count: {count}")

        if len(locations) != count:
            print(f"   ⚠️  Mismatch: received {len(locations)} but API says {count}")

        return locations

    except requests.exceptions.Timeout:
        print("❌ Request timed out after 60 seconds")
        return []
    except requests.exceptions.RequestException as e:
        print(f"❌ Network error: {e}")
        return []
    except json.JSONDecodeError:
        print("❌ Invalid JSON response")
        return []
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return []


def analyze_locations(locations: List[Dict]):
    """Analyze fetched locations and print statistics."""
    print()
    print("="*80)
    print("ANALYSIS")
    print("="*80)
    print()

    # Count by type
    type_counts = defaultdict(int)
    for loc in locations:
        pickup_type = loc.get('pickup_network_type', 'unknown')
        type_counts[pickup_type] += 1

    print("📦 By type:")
    for loc_type, count in sorted(type_counts.items(), key=lambda x: -x[1]):
        print(f"   {loc_type:20s}: {count:4d}")

    # Count by city (top 10)
    city_counts = defaultdict(int)
    for loc in locations:
        city = loc.get('city', 'Unknown')
        city_counts[city] += 1

    print()
    print("🏙️  Top 10 cities by location count:")
    for i, (city, count) in enumerate(sorted(city_counts.items(), key=lambda x: -x[1])[:10], 1):
        print(f"   {i:2d}. {city:25s}: {count:3d} locations")

    # Service features
    print()
    print("🔧 Service availability:")
    pickup_count = sum(1 for loc in locations if loc.get('pickup_allowed'))
    return_count = sum(1 for loc in locations if loc.get('return_allowed'))
    dropoff_count = sum(1 for loc in locations if loc.get('dropoff_allowed'))
    express_count = sum(1 for loc in locations if loc.get('express_allowed'))
    cod_count = sum(1 for loc in locations if loc.get('cod_allowed'))
    weekend_count = sum(1 for loc in locations if loc.get('open_weekend'))

    print(f"   Pickup allowed:     {pickup_count:4d} ({pickup_count/len(locations)*100:.1f}%)")
    print(f"   Return allowed:     {return_count:4d} ({return_count/len(locations)*100:.1f}%)")
    print(f"   Drop-off allowed:   {dropoff_count:4d} ({dropoff_count/len(locations)*100:.1f}%)")
    print(f"   Express delivery:   {express_count:4d} ({express_count/len(locations)*100:.1f}%)")
    print(f"   Cash on delivery:   {cod_count:4d} ({cod_count/len(locations)*100:.1f}%)")
    print(f"   Open on weekends:   {weekend_count:4d} ({weekend_count/len(locations)*100:.1f}%)")

    # Geographic distribution
    lats = [loc.get('latitude', 0) for loc in locations if loc.get('latitude')]
    lons = [loc.get('longitude', 0) for loc in locations if loc.get('longitude')]

    if lats and lons:
        print()
        print("🌍 Geographic coverage:")
        print(f"   Latitude:  {min(lats):.4f}° to {max(lats):.4f}°")
        print(f"   Longitude: {min(lons):.4f}° to {max(lons):.4f}°")


def save_results(locations: List[Dict], output_file: str = None):
    """
    Save locations to JSON file.

    Parameters
    ----------
    locations : list of dict
        DPD locations data
    output_file : str, optional
        Output filename. If None, uses data/dpd_all_locations.json relative to project root
    """
    print()
    print("="*80)
    print("SAVING RESULTS")
    print("="*80)
    print()

    from cache_guard import safe_save

    # Default output path - works both locally and in GitHub Actions
    if output_file is None:
        script_dir = Path(__file__).parent
        project_root = script_dir.parent
        output_path = project_root / "data" / "dpd_all_locations.json"
    else:
        output_path = Path(output_file)

    safe_save(
        carrier="DPD",
        new_locations=locations,
        output_path=output_path,
        metadata={
            "method": "api-getAll",
            "source": "https://pickup.dpd.cz/api/getAll",
            "country": CONFIG["name"],
            "country_code_iso": CONFIG["dpd"]["country_code"],
        },
    )


def main():
    """Main execution function."""
    print()
    print("Starting DPD location fetch...")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    # Fetch all locations
    locations = fetch_all_dpd_locations()

    if not locations:
        print()
        print("❌ Failed to fetch locations")
        return 1

    # Analyze
    analyze_locations(locations)

    # Save
    save_results(locations)

    print()
    print("="*80)
    print("✅ COMPLETE!")
    print("="*80)
    print()
    print("Next steps:")
    print("  1. Run: python integrate_dpd_data.py")
    print("     (Integrate DPD data into municipality files)")
    print()
    print("  2. Or regenerate everything:")
    print("     python weekly_update.py")
    print()

    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
