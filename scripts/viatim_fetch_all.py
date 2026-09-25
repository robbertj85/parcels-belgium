"""
Fetch all ViaTim service point locations in the configured country.

ViaTim operates a network of neighbourhood service points ("buurtpunten")
that handle parcels for multiple carriers (DHL, UPS, GLS, DPD).

API: https://production.viapunt-api.viatim.nl/public/servicepoints
     No authentication required. Single GET returns all locations.

Usage:
    python scripts/viatim_fetch_all.py
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


def fetch_all_viatim_locations() -> List[Dict]:
    """
    Fetch all ViaTim service points and filter to the configured country.

    Returns
    -------
    list of dict
        ViaTim locations in the configured country with standardized fields
    """
    print("=" * 80)
    print("VIATIM COMPLETE LOCATION FETCH")
    print("=" * 80)
    print()

    print("📡 Fetching all ViaTim service points from public API...")
    print("   Endpoint: https://production.viapunt-api.viatim.nl/public/servicepoints")
    print()

    try:
        response = requests.get(
            "https://production.viapunt-api.viatim.nl/public/servicepoints",
            params={"limit": 1000},  # 554 total as of 2026, 1000 is enough
            timeout=60,
        )
        response.raise_for_status()
        data = response.json()

        # Response is a dict with 'pagination' and 'servicepoints' keys
        if isinstance(data, dict):
            all_servicepoints = data.get('servicepoints', [])
            total = data.get('pagination', {}).get('total', len(all_servicepoints))
            print(f"   API reports {total} total service points")
        elif isinstance(data, list):
            all_servicepoints = data
        else:
            print(f"❌ Unexpected response format: {type(data)}")
            return []

        print(f"✅ Fetched {len(all_servicepoints)} service points (NL + BE)")

        # Alleen het ingestelde land
        country = CONFIG['viatim']['country']
        nl_locations = [sp for sp in all_servicepoints if sp.get('location', {}).get('country') == country]
        print(f"   {CONFIG['name']}: {len(nl_locations)}")

        # Convert to standardized format
        locations = []
        for sp in nl_locations:
            loc = sp.get('location', {})
            transporters = sp.get('transporters', [])

            locations.append({
                'viacode': sp.get('viacode', ''),
                'locatieNaam': sp.get('name', ''),
                'straatNaam': loc.get('streetname', ''),
                'straatNr': str(loc.get('housenr', '')) + (loc.get('housenr_extra', '') or ''),
                'postcode': loc.get('postcode', ''),
                'city': loc.get('city', ''),
                'latitude': loc.get('latitude'),
                'longitude': loc.get('longitude'),
                'email': loc.get('email', ''),
                'phone': loc.get('phone', ''),
                'transporters': transporters,
                'hours': sp.get('hours', {}),
            })

        print(f"   📦 Converted {len(locations)} {country} locations")
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
    print("=" * 80)
    print("ANALYSIS")
    print("=" * 80)
    print()

    # Count by transporters
    transporter_counts = defaultdict(int)
    for loc in locations:
        for t in loc.get('transporters', []):
            transporter_counts[t] += 1

    print("📦 Carriers served:")
    for carrier, count in sorted(transporter_counts.items(), key=lambda x: -x[1]):
        print(f"   {carrier:20s}: {count:4d}")

    # Count by city (top 10)
    city_counts = defaultdict(int)
    for loc in locations:
        city = loc.get('city', 'Unknown')
        city_counts[city] += 1

    print()
    print("🏙️  Top 10 cities by location count:")
    for i, (city, count) in enumerate(sorted(city_counts.items(), key=lambda x: -x[1])[:10], 1):
        print(f"   {i:2d}. {city:25s}: {count:3d} locations")

    # Geographic coverage
    lats = [loc.get('latitude', 0) for loc in locations if loc.get('latitude')]
    lons = [loc.get('longitude', 0) for loc in locations if loc.get('longitude')]

    if lats and lons:
        print()
        print("🌍 Geographic coverage:")
        print(f"   Latitude:  {min(lats):.4f}° to {max(lats):.4f}°")
        print(f"   Longitude: {min(lons):.4f}° to {max(lons):.4f}°")


def save_results(locations: List[Dict]):
    """Save locations to JSON file."""
    print()
    print("=" * 80)
    print("SAVING RESULTS")
    print("=" * 80)
    print()

    from cache_guard import safe_save

    output_path = Path(__file__).parent.parent / "data" / "viatim_all_locations.json"

    safe_save(
        carrier="ViaTim",
        new_locations=locations,
        output_path=output_path,
        metadata={
            "method": "api-public-servicepoints",
            "source": "https://production.viapunt-api.viatim.nl/public/servicepoints",
            "country": CONFIG["name"],
        },
    )


def main():
    print()
    print(f"Starting ViaTim location fetch...")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    locations = fetch_all_viatim_locations()

    if not locations:
        print()
        print("❌ Failed to fetch locations")
        return 1

    analyze_locations(locations)
    save_results(locations)

    print()
    print("=" * 80)
    print("✅ COMPLETE!")
    print("=" * 80)
    print()
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
