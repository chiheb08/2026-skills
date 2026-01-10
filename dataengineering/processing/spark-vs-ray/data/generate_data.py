"""Generate a synthetic dataset for Spark vs Ray comparison.

We keep it simple: event logs with user_id, event_type, ts, and amount.

Output: CSV (easy) so both Spark and Ray can read it without extra dependencies.
"""

from __future__ import annotations

import argparse
import csv
import random
from datetime import datetime, timedelta
from pathlib import Path


EVENT_TYPES = ["view", "click", "purchase", "refund"]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True, help="Output CSV path")
    parser.add_argument("--rows", type=int, default=2_000_000)
    parser.add_argument("--users", type=int, default=100_000)
    parser.add_argument("--days", type=int, default=30)
    parser.add_argument("--seed", type=int, default=7)
    args = parser.parse_args()

    random.seed(args.seed)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    start = datetime.utcnow() - timedelta(days=args.days)

    with out_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["user_id", "event_type", "ts", "amount"])

        for _ in range(args.rows):
            user_id = random.randint(1, args.users)
            event_type = random.choices(EVENT_TYPES, weights=[0.70, 0.25, 0.04, 0.01])[0]
            dt = start + timedelta(seconds=random.randint(0, args.days * 24 * 3600))

            if event_type == "purchase":
                amount = round(random.uniform(5, 200), 2)
            elif event_type == "refund":
                amount = round(-random.uniform(5, 200), 2)
            else:
                amount = 0.0

            w.writerow([user_id, event_type, dt.isoformat(), amount])

    print(f"Wrote {args.rows} rows to {out_path}")


if __name__ == "__main__":
    main()
