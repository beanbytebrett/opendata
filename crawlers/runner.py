"""CLI runner for crawlers.

Usage: python -m crawlers.runner <source> [--output-dir DIR]
"""

import argparse
import sys
import time
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from crawlers.sources.congress_contacts import CongressContactsCrawler

CRAWLERS = {
    "congress_contacts": CongressContactsCrawler,
}


def main():
    parser = argparse.ArgumentParser(description="Run a crawler and export to Parquet.")
    parser.add_argument("source", choices=sorted(CRAWLERS.keys()), help="Crawler source name")
    parser.add_argument("--output-dir", default="./data/public", help="Output directory")
    parser.add_argument("--proxy", default=None, help="SOCKS proxy (e.g. socks5h://127.0.0.1:9050)")
    args = parser.parse_args()

    crawler = CRAWLERS[args.source]()
    if args.proxy:
        crawler.proxy = args.proxy
        print(f"[{crawler.name}] Using proxy: {args.proxy}")
    print(f"[{crawler.name}] Starting crawl...")
    start = time.time()

    records = list(crawler.crawl())
    elapsed = time.time() - start
    print(f"[{crawler.name}] Crawled {len(records)} records in {elapsed:.1f}s")

    # Validate all records have 'id'
    for i, r in enumerate(records):
        if "id" not in r:
            print(f"FATAL: Record at index {i} has no 'id' field")
            sys.exit(1)

    # Run done conditions
    conditions = crawler.done_conditions()
    failures = []
    for cond in conditions:
        passed, msg = cond.check(records)
        status = "PASS" if passed else "FAIL"
        print(f"  [{status}] {msg}")
        if not passed:
            failures.append(msg)

    if failures:
        print(f"\n{len(failures)} condition(s) failed. Export blocked.")
        sys.exit(1)

    # Write Parquet
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{crawler.name}.parquet"

    table = pa.Table.from_pylist(records)
    pq.write_table(table, output_path)
    print(f"[{crawler.name}] Wrote {output_path} ({len(records)} rows)")


if __name__ == "__main__":
    main()
