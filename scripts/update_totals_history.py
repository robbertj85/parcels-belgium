#!/usr/bin/env python3
"""
Update totals history with the current week's data.

This script appends the current week's totals to a persistent history file.
Run this weekly (e.g., via GitHub Actions) to build up historical data over time.

Output: webapp/public/data/totals_history.json
"""

import json
import os
from datetime import datetime, timedelta, timezone
from collections import defaultdict
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from country_config import NATIONAL_SLUG  # noqa: E402


def get_week_info(date=None):
    """Get ISO week number and date range for a given date."""
    if date is None:
        date = datetime.now(timezone.utc)
    elif isinstance(date, str):
        date = datetime.strptime(date, '%Y-%m-%d')

    iso_calendar = date.isocalendar()
    week_num = iso_calendar[1]
    year = iso_calendar[0]

    # Calculate week start (Monday) and end (Sunday)
    week_start = date - timedelta(days=date.weekday())
    week_end = week_start + timedelta(days=6)

    return {
        'week': week_num,
        'year': year,
        'week_label': f"{year}-W{week_num:02d}",
        'date_from': week_start.strftime('%Y-%m-%d'),
        'date_to': week_end.strftime('%Y-%m-%d')
    }


def get_current_totals(data_dir):
    """Calculate current totals from all GeoJSON files."""
    totals = {
        'total': 0,
        'providers': defaultdict(int),
        'municipalities': {}
    }

    # All municipality GeoJSON files (the national file would double-count)
    geojson_files = list(data_dir.glob('*.geojson'))

    for file_path in geojson_files:
        slug = file_path.stem

        if slug == NATIONAL_SLUG or slug.endswith('-boundaries'):
            continue

        try:
            with open(file_path, 'r') as f:
                data = json.load(f)

            municipality_total = 0
            municipality_providers = defaultdict(int)

            for feature in data.get('features', []):
                props = feature.get('properties', {})
                if props.get('type') == 'pakketpunt':
                    provider = props.get('vervoerder', 'Unknown')
                    municipality_providers[provider] += 1
                    municipality_total += 1
                    totals['providers'][provider] += 1
                    totals['total'] += 1

            totals['municipalities'][slug] = {
                'total': municipality_total,
                'providers': dict(municipality_providers)
            }

        except Exception as e:
            print(f"Warning: Could not process {file_path}: {e}")

    totals['providers'] = dict(totals['providers'])
    return totals


def load_history(history_path):
    """Load existing history or create empty structure."""
    if history_path.exists():
        with open(history_path, 'r') as f:
            return json.load(f)

    return {
        'snapshots': [],
        'municipalities': {}
    }


def save_history(history_path, history_data):
    """Save history to file."""
    with open(history_path, 'w') as f:
        json.dump(history_data, f, indent=2)


def main():
    # Determine paths
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    data_dir = project_root / 'webapp' / 'public' / 'data'
    history_path = data_dir / 'totals_history.json'

    print("Updating totals history...")

    # Get current week info
    now = datetime.now(timezone.utc)
    week_info = get_week_info(now)
    date_str = now.strftime('%Y-%m-%d')

    print(f"Current date: {date_str}")
    print(f"Week: {week_info['week_label']} ({week_info['date_from']} to {week_info['date_to']})")

    # Load existing history
    history = load_history(history_path)

    # Check if we already have an entry for this week
    existing_weeks = {s['week_label'] for s in history['snapshots']}

    if week_info['week_label'] in existing_weeks:
        print(f"Week {week_info['week_label']} already exists in history.")
        # Update the existing entry instead of adding a new one
        for snapshot in history['snapshots']:
            if snapshot['week_label'] == week_info['week_label']:
                print("Updating existing entry...")
                current = get_current_totals(data_dir)
                snapshot['date'] = date_str
                snapshot['totals'] = {
                    'total': current['total'],
                    'providers': current['providers']
                }
                # Update municipality data for this week
                for slug, muni_data in current['municipalities'].items():
                    if slug not in history['municipalities']:
                        history['municipalities'][slug] = {'history': []}

                    # Find and update or append municipality entry for this week
                    muni_history = history['municipalities'][slug]['history']
                    found = False
                    for entry in muni_history:
                        if entry['week_label'] == week_info['week_label']:
                            entry.update({
                                'date': date_str,
                                'total': muni_data['total'],
                                'providers': muni_data['providers']
                            })
                            found = True
                            break
                    if not found:
                        muni_history.append({
                            'date': date_str,
                            **week_info,
                            'total': muni_data['total'],
                            'providers': muni_data['providers']
                        })
                break
    else:
        print(f"Adding new entry for week {week_info['week_label']}...")

        # Get current totals
        current = get_current_totals(data_dir)

        # Create new snapshot
        new_snapshot = {
            'date': date_str,
            **week_info,
            'totals': {
                'total': current['total'],
                'providers': current['providers']
            }
        }

        history['snapshots'].append(new_snapshot)

        # Add municipality data
        for slug, muni_data in current['municipalities'].items():
            if slug not in history['municipalities']:
                history['municipalities'][slug] = {'history': []}

            history['municipalities'][slug]['history'].append({
                'date': date_str,
                **week_info,
                'total': muni_data['total'],
                'providers': muni_data['providers']
            })

    # Sort snapshots by date
    history['snapshots'].sort(key=lambda x: x['date'])

    # Sort municipality histories by date
    for slug in history['municipalities']:
        history['municipalities'][slug]['history'].sort(key=lambda x: x['date'])

    # Sync the national entry from snapshots (the national file itself is skipped above)
    national_history = []
    for snapshot in history['snapshots']:
        national_history.append({
            'date': snapshot['date'],
            'week': snapshot['week'],
            'year': snapshot['year'],
            'week_label': snapshot['week_label'],
            'date_from': snapshot['date_from'],
            'date_to': snapshot['date_to'],
            'total': snapshot['totals']['total'],
            'providers': snapshot['totals']['providers']
        })
    history['municipalities'][NATIONAL_SLUG] = {'history': national_history}

    # Update metadata
    history['updated_at'] = now.isoformat().replace('+00:00', 'Z')

    # Calculate trend (comparing latest to previous)
    if len(history['snapshots']) >= 2:
        latest = history['snapshots'][-1]
        previous = history['snapshots'][-2]

        history['trend'] = {
            'period': {
                'from': previous['date'],
                'to': latest['date'],
                'weeks': len(history['snapshots'])
            },
            'change': {
                'total': latest['totals']['total'] - previous['totals']['total'],
                'providers': {}
            }
        }

        all_providers = set(latest['totals']['providers'].keys()) | set(previous['totals']['providers'].keys())
        for provider in all_providers:
            latest_count = latest['totals']['providers'].get(provider, 0)
            previous_count = previous['totals']['providers'].get(provider, 0)
            history['trend']['change']['providers'][provider] = latest_count - previous_count

    # Save updated history
    save_history(history_path, history)

    print(f"\nHistory updated: {history_path}")
    print(f"Total snapshots: {len(history['snapshots'])}")

    # Print summary
    if history['snapshots']:
        latest = history['snapshots'][-1]
        print(f"\nLatest snapshot ({latest['date']}, {latest['week_label']}):")
        print(f"  Total: {latest['totals']['total']:,} pakketpunten")
        for provider, count in sorted(latest['totals']['providers'].items()):
            print(f"  {provider}: {count:,}")

        if len(history['snapshots']) >= 2:
            oldest = history['snapshots'][0]
            print(f"\nHistory range: {oldest['week_label']} to {latest['week_label']}")
            print(f"  {oldest['totals']['total']:,} -> {latest['totals']['total']:,}")


if __name__ == '__main__':
    main()
