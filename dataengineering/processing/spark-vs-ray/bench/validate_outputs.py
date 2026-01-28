"""Validate Spark vs Ray outputs for the tutorial.

We validate *high-level equivalence*:
- number of rows (unique users)
- sum(events)
- sum(net_amount)
- sum(purchases)

This is simple and robust for a Medium tutorial.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Tuple

import pyarrow as pa
import pyarrow.dataset as ds


@dataclass
class OutputSummary:
    rows: int
    sum_events: int
    sum_net_amount: float
    sum_purchases: int


def _sum_scalar(table: pa.Table, col: str) -> float:
    arr = table[col]
    # convert to chunked array sum
    s = pa.compute.sum(arr)
    return float(s.as_py() or 0)


def _pick_column(names: list[str], preferred: list[str], contains_any: list[str]) -> str:
    # exact match preference
    for p in preferred:
        if p in names:
            return p
    # substring match fallback
    lowered = {n.lower(): n for n in names}
    for n in names:
        ln = n.lower()
        if any(k in ln for k in contains_any):
            return n
    raise KeyError(f"Could not find a matching column. Available: {names}")


def read_summary(out_dir: str, engine: str) -> OutputSummary:
    """Read parquet output and compute summary metrics.

    engine:
      - 'spark': expects columns: user_id, events, net_amount, purchases
      - 'ray': Ray Data aggregate column names vary; we detect them.
    """
    p = Path(out_dir)
    dataset = ds.dataset(str(p), format="parquet")
    table = dataset.to_table()

    names = table.column_names
    if engine == "spark":
        events_col = "events"
        amount_col = "net_amount"
        purchases_col = "purchases"
    elif engine == "ray":
        # Ray Data typical names:
        # - count(): "count()" or "Count()" or "Count"
        # - sum(amount): "sum(amount)" etc.
        # - sum(purchase_flag): "sum(purchase_flag)" etc.
        events_col = _pick_column(names, preferred=["count()", "Count()"], contains_any=["count"])
        amount_col = _pick_column(names, preferred=["sum(amount)", "Sum(amount)"], contains_any=["sum(amount)", "amount"])
        purchases_col = _pick_column(names, preferred=["sum(purchase_flag)", "Sum(purchase_flag)"], contains_any=["purchase_flag", "purchases"])
    else:
        raise ValueError("engine must be 'spark' or 'ray'")

    rows = table.num_rows
    sum_events = int(_sum_scalar(table, events_col))
    sum_net_amount = float(_sum_scalar(table, amount_col))
    sum_purchases = int(_sum_scalar(table, purchases_col))

    return OutputSummary(rows=rows, sum_events=sum_events, sum_net_amount=sum_net_amount, sum_purchases=sum_purchases)


def compare(spark: OutputSummary, ray: OutputSummary) -> Dict[str, Tuple[float, float]]:
    return {
        "rows": (spark.rows, ray.rows),
        "sum_events": (spark.sum_events, ray.sum_events),
        "sum_net_amount": (spark.sum_net_amount, ray.sum_net_amount),
        "sum_purchases": (spark.sum_purchases, ray.sum_purchases),
    }




