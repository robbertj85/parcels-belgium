"""
Fetch all Amazon Hub Locker and Counter locations in the configured country.

Uses Playwright to interact with the Amazon ULP page (amazon.com.be/ulp for
Belgium) and capture the fetch_locations API.
Each search returns at most ~20 locations, so dense cities can be undercounted.
Searches by municipality name and clicks on autocomplete suggestions to trigger searches.

Prerequisites:
    pip install playwright
    playwright install chromium

Usage:
    python scripts/amazon_fetch_all.py
"""

import json
import re
import sys
import time
from pathlib import Path
from datetime import datetime
from typing import Dict, List

try:
    from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
except ImportError:
    print("Playwright not installed. Run:")
    print("   pip install playwright")
    print("   playwright install chromium")
    exit(1)

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from country_config import CONFIG, in_bbox  # noqa: E402

ULP_URL = f"https://{CONFIG['amazon']['domain']}/ulp"


def dismiss_overlays(page):
    """Remove the 'go to amazon.nl?' redirect modal and accept cookies.

    amazon.com.be shows a geo-redirect modal that intercepts every click.
    """
    page.evaluate("document.querySelectorAll('[id^=redir], .redir-modal-bg').forEach(e => e.remove())")
    accept_btn = page.query_selector('#sp-cc-accept')
    if accept_btn:
        accept_btn.click(force=True)
        time.sleep(2)


def load_municipalities() -> List[str]:
    """
    Load municipality names from municipalities.json.
    Returns the municipality names (excluding the national row). A bilingual
    Brussels name like "Elsene (Ixelles)" is searched as "Elsene".
    """
    municipalities_file = Path(__file__).parent.parent / "webapp" / "public" / "municipalities.json"

    with open(municipalities_file, 'r', encoding='utf-8') as f:
        municipalities = json.load(f)

    # Filter out "Nederland (totaal)" and extract just the names
    names = [
        re.sub(r"\s*\(.*\)$", "", m['name']) for m in municipalities
        if m.get('code') is not None
    ]

    print(f"Loaded {len(names)} municipality names")
    return names


def fetch_all_amazon_locations() -> List[Dict]:
    """
    Fetch all Amazon Hub locations using municipality-based search.
    Uses autocomplete selection to properly trigger location searches.
    """
    print("=" * 80)
    print("AMAZON HUB COMPLETE LOCATION FETCH (via Playwright)")
    print("Search method: Municipality names with autocomplete")
    print("=" * 80)
    print()

    municipalities = load_municipalities()
    print()

    all_locations: Dict[str, Dict] = {}  # Keyed by location ID for deduplication

    with sync_playwright() as p:
        print("Launching browser...")
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            locale=CONFIG["amazon"]["locale"],
            viewport={"width": 1280, "height": 800},
        )
        page = context.new_page()

        # Response handler to capture location data
        captured_responses = []

        def handle_response(response):
            if 'fetch_locations' in response.url:
                try:
                    if 'json' in response.headers.get('content-type', ''):
                        body = response.text()
                        captured_responses.append(body)
                except:
                    pass

        page.on("response", handle_response)

        # Navigate to ULP page
        print(f"Loading {ULP_URL}...")
        try:
            page.goto(ULP_URL, wait_until="networkidle", timeout=60000)
        except PlaywrightTimeout:
            print("Page load timeout, continuing anyway...")

        time.sleep(5)
        dismiss_overlays(page)

        print()

        # Search each municipality
        total = len(municipalities)
        start_time = time.time()
        failed_searches = []

        # Locations returned per municipality search. If amazon.nl/ulp caps a
        # response, that shows up here as a pile-up of searches all returning
        # the same number -- which is the difference between "Amazon has fewer
        # locations" and "we stopped being able to see them all". The count
        # fell from a steady ~1,700 to ~1,150 in the week of 2026-08-03 with
        # no change on our side, and this is what tells the two apart.
        per_search_counts = []

        for idx, municipality in enumerate(municipalities):
            # Progress update every 10 municipalities
            if idx % 10 == 0:
                elapsed = time.time() - start_time
                rate = idx / elapsed if elapsed > 0 else 0
                eta = (total - idx) / rate if rate > 0 else 0
                print(f"Progress: {idx}/{total} ({idx*100//total}%) - {len(all_locations)} unique locations - ETA: {eta/60:.1f} min", flush=True)

            # Clear previous responses
            captured_responses.clear()

            # Find search input (might need to re-find after interactions)
            search_input = page.query_selector('#lsView input[type="text"]')
            if not search_input:
                search_input = page.query_selector('input[placeholder*="Voer"]')

            if not search_input:
                failed_searches.append(municipality)
                continue

            try:
                # Clear and type the municipality name
                search_input.click(force=True)
                time.sleep(0.2)
                search_input.fill('')
                time.sleep(0.2)
                search_input.type(municipality, delay=50)
                time.sleep(1.2)  # Wait for autocomplete

                # Look for autocomplete suggestions
                suggestions = page.query_selector_all('#lsView li')

                # Click on the first matching suggestion
                clicked = False
                for suggestion in suggestions:
                    try:
                        text = suggestion.inner_text().lower()
                        if text.startswith(municipality.lower()):
                            suggestion.click(force=True)
                            clicked = True
                            time.sleep(2.5)  # Wait for API response
                            break
                    except:
                        continue

                # If no exact match, click first suggestion
                if not clicked and suggestions:
                    try:
                        suggestions[0].click(force=True)
                        time.sleep(2.5)
                    except:
                        pass

            except Exception as e:
                failed_searches.append(municipality)
                # Try to recover by refreshing
                try:
                    page.goto(ULP_URL, wait_until="networkidle", timeout=30000)
                    time.sleep(3)
                    dismiss_overlays(page)
                except:
                    pass
                continue

            # Process captured responses
            search_returned = 0
            for resp_body in captured_responses:
                try:
                    data = json.loads(resp_body)
                    locations = data.get('locationList') or []
                    search_returned += len(locations)

                    for loc in locations:
                        loc_id = loc.get('id')
                        if not loc_id or loc_id in all_locations:
                            continue

                        # Extract coordinates
                        coords = loc.get('location', {})
                        latitude = coords.get('latitude', 0)
                        longitude = coords.get('longitude', 0)

                        # Skip if no valid coordinates or outside the country
                        if not latitude or not in_bbox(latitude, longitude):
                            continue

                        # Store location with standardized format
                        address = loc.get('addressLine1', '') or loc.get('addressLine2', '') or ''
                        all_locations[loc_id] = {
                            'id': loc_id,
                            'locatieNaam': loc.get('name', ''),
                            'straatNaam': address.strip(),
                            'straatNr': '',
                            'postcode': loc.get('postalCode', ''),
                            'city': loc.get('city', ''),
                            'latitude': latitude,
                            'longitude': longitude,
                            'puntType': loc.get('accessPointType', '').lower(),
                            'apisType': loc.get('apisAccessPointType', ''),
                            'vervoerder': 'Amazon',
                        }

                except json.JSONDecodeError:
                    continue

            per_search_counts.append((municipality, search_returned))

            # Small delay between searches
            time.sleep(0.3)

        browser.close()

    locations_list = list(all_locations.values())
    print()
    print(f"Fetched {len(locations_list)} unique Amazon locations")

    if failed_searches:
        print(f"Failed searches ({len(failed_searches)}): {', '.join(failed_searches[:10])}...")

    report_per_search(per_search_counts)

    return locations_list


def report_per_search(per_search_counts: List[tuple]):
    """
    Print the distribution of per-search response sizes.

    A hard cap in the API reads as a spike at one value: dozens of searches
    all returning exactly the same number, with none above it. Organic data
    gives a smooth spread with the dense municipalities well clear of the rest.
    """
    if not per_search_counts:
        return

    sizes = [n for _, n in per_search_counts]
    counter: Dict[int, int] = {}
    for n in sizes:
        counter[n] = counter.get(n, 0) + 1

    print()
    print("=" * 80)
    print("PER-SEARCH RESPONSE SIZES")
    print("=" * 80)
    print(f"   searches:  {len(sizes)}")
    print(f"   empty:     {sum(1 for n in sizes if n == 0)}")
    print(f"   max:       {max(sizes)}")
    print(f"   mean:      {sum(sizes) / len(sizes):.1f}")
    print()
    print("   most common response sizes:")
    for size, hits in sorted(counter.items(), key=lambda kv: (-kv[1], -kv[0]))[:8]:
        flag = "  <-- possible cap" if size == max(sizes) and hits > 5 else ""
        print(f"      {size:>4} locations x {hits:>3} searches{flag}")
    print()
    print("   largest searches:")
    for name, n in sorted(per_search_counts, key=lambda kv: -kv[1])[:8]:
        print(f"      {name:<28} {n:>4}")


def analyze_locations(locations: List[Dict]):
    """Print statistics about fetched locations."""
    print()
    print("=" * 80)
    print("ANALYSIS")
    print("=" * 80)
    print()

    if not locations:
        print("No locations to analyze")
        return

    # Count by type
    type_counts = {}
    for loc in locations:
        loc_type = loc.get('puntType', 'unknown')
        type_counts[loc_type] = type_counts.get(loc_type, 0) + 1

    print("By type:")
    for loc_type, count in sorted(type_counts.items(), key=lambda x: -x[1]):
        print(f"   {loc_type:20s}: {count:4d}")

    # Count by city (top 15)
    city_counts = {}
    for loc in locations:
        city = loc.get('city', 'Unknown')
        if city:
            # Normalize city names (some are uppercase)
            city_normalized = city.title()
            city_counts[city_normalized] = city_counts.get(city_normalized, 0) + 1

    if city_counts:
        print()
        print("Top 15 cities:")
        for i, (city, count) in enumerate(sorted(city_counts.items(), key=lambda x: -x[1])[:15], 1):
            print(f"   {i:2d}. {city:25s}: {count:3d}")

    # Geographic bounds
    lats = [loc['latitude'] for loc in locations if loc.get('latitude')]
    lons = [loc['longitude'] for loc in locations if loc.get('longitude')]

    if lats and lons:
        print()
        print("Geographic coverage:")
        print(f"   Latitude:  {min(lats):.4f} to {max(lats):.4f}")
        print(f"   Longitude: {min(lons):.4f} to {max(lons):.4f}")


def save_results(locations: List[Dict]):
    """Save locations to JSON file."""
    print()
    print("=" * 80)
    print("SAVING RESULTS")
    print("=" * 80)
    print()

    from cache_guard import safe_save

    output_path = Path(__file__).parent.parent / "data" / "amazon_all_locations.json"

    safe_save(
        carrier="Amazon",
        new_locations=locations,
        output_path=output_path,
        metadata={
            "method": "playwright-scraping-municipality-autocomplete",
            "source": ULP_URL,
            "country": CONFIG["name"],
        },
    )


def main():
    print()
    print(f"Starting Amazon Hub location fetch...")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    locations = fetch_all_amazon_locations()

    if locations:
        analyze_locations(locations)
        save_results(locations)
    else:
        print("No locations fetched")

    print()
    print("=" * 80)
    print("COMPLETE!")
    print("=" * 80)


if __name__ == "__main__":
    main()
