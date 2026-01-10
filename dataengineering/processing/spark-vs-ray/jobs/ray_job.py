"""Ray job: read CSV, filter by date range, aggregate per user, write output.

Uses Ray Data, which is the closest comparable abstraction to Spark DataFrames.

Run locally (example):
  python jobs/ray_job.py --in data/events.csv --out out/ray
"""

from __future__ import annotations

import argparse
from datetime import datetime

import ray
import ray.data as rd


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--in", dest="inp", required=True, help="Input CSV")
    parser.add_argument("--out", required=True, help="Output folder")
    parser.add_argument("--start", default=None, help="ISO timestamp inclusive")
    parser.add_argument("--end", default=None, help="ISO timestamp exclusive")
    args = parser.parse_args()

    ray.init(ignore_reinit_error=True)

    ds = rd.read_csv(args.inp)

    # Parse ts to datetime in a map step (simple, not the fastest, but clear)
    def parse_ts(row):
        row["ts"] = datetime.fromisoformat(row["ts"])
        # for parity with Spark job: count purchases
        row["purchase_flag"] = 1 if row.get("event_type") == "purchase" else 0
        return row

    ds = ds.map(parse_ts)

    if args.start:
        start_dt = datetime.fromisoformat(args.start)
        ds = ds.filter(lambda r: r["ts"] >= start_dt)
    if args.end:
        end_dt = datetime.fromisoformat(args.end)
        ds = ds.filter(lambda r: r["ts"] < end_dt)

    # Aggregate per user_id (same metrics as Spark job):
    # - events (count)
    # - net_amount (sum of amount)
    # - purchases (sum of purchase_flag)
    #
    # Note: Ray Data names these aggregate columns automatically. We'll keep output as-is,
    # and the benchmark script will validate by reading the produced parquet and mapping
    # the correct columns by name/substring.
    grouped = ds.groupby("user_id").aggregate(
        rd.aggregate.Count(),
        rd.aggregate.Sum("amount"),
        rd.aggregate.Sum("purchase_flag"),
    )

    grouped.write_parquet(args.out)

    ray.shutdown()


if __name__ == "__main__":
    main()
