"""
Run the nationwide fetch for every carrier of the configured country.

Each carrier has scripts/<carrier>_fetch_all.py (lower case). Carriers listed in
--skip (Amazon: its own workflow, it needs a browser and 45+ minutes) are left
out. A fetcher that fails or whose cache guard blocks the save does not stop
the others: their previous cache stays in place.

Writes the carriers that failed to --anomalies (one line, space separated) so
the workflow can report them and mention them in the commit message.

    python scripts/fetch_all.py --skip Amazon --anomalies /tmp/anomaly_carriers.txt
"""

import argparse
import subprocess
import sys
import time
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS_DIR.parent))
from country_config import CARRIERS, CONFIG  # noqa: E402

TIMEOUT_SECONDS = 45 * 60


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    parser.add_argument("--skip", nargs="*", default=[], help="carriers to leave out")
    parser.add_argument("--anomalies", help="file to write failed carriers to")
    args = parser.parse_args()

    skip = {c.lower() for c in args.skip}
    failed = []

    print(f"🌍 {CONFIG['name']}: {', '.join(CARRIERS)}")
    for carrier in CARRIERS:
        if carrier.lower() in skip:
            print(f"\n⏭️  {carrier}: skipped")
            continue

        script = SCRIPTS_DIR / f"{carrier.lower()}_fetch_all.py"
        if not script.exists():
            print(f"\n❌ {carrier}: {script.name} does not exist")
            failed.append(carrier)
            continue

        print(f"\n{'=' * 80}\n▶️  {carrier}: {script.name}\n{'=' * 80}", flush=True)
        started = time.time()
        try:
            result = subprocess.run([sys.executable, str(script)], timeout=TIMEOUT_SECONDS)
            ok = result.returncode == 0
        except subprocess.TimeoutExpired:
            print(f"❌ {carrier}: timed out after {TIMEOUT_SECONDS // 60} min")
            ok = False

        took = time.time() - started
        print(f"{'✅' if ok else '❌'} {carrier} ({took / 60:.1f} min)", flush=True)
        if not ok:
            failed.append(carrier)

    if args.anomalies and failed:
        Path(args.anomalies).write_text(" ".join(failed) + " ")

    print(f"\n{'All carriers fetched' if not failed else 'Failed or blocked: ' + ', '.join(failed)}")
    # Never fail the job: the previous caches of failed carriers are still valid,
    # and check_cache_freshness.py is the gate for carriers that stay stale.
    return 0


if __name__ == "__main__":
    sys.exit(main())
