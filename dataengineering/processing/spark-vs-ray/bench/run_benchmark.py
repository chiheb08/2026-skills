"""Run Spark and Ray jobs and compare runtime (tutorial-friendly but more rigorous).

What this benchmark does:
- runs warmup iterations (optional)
- runs multiple timed iterations
- validates outputs (basic correctness check)
- records environment + configuration
- writes results to:
  - results.json (machine-readable)
  - results.md (Medium-friendly summary you can paste)
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import statistics
import subprocess
import sys
import time
from dataclasses import asdict
from pathlib import Path

import pyarrow as pa  # noqa: F401 (ensures dependency exists in the docker image)

# When running as: `python bench/run_benchmark.py`, the script directory is on sys.path,
# so we can import the sibling module directly.
from validate_outputs import compare, read_summary


def run(cmd: list[str], cwd: str) -> float:
    t0 = time.time()
    subprocess.check_call(cmd, cwd=cwd)
    return time.time() - t0


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, help="Input CSV")
    parser.add_argument("--out", required=True, help="Output base folder")
    parser.add_argument("--runs", type=int, default=5, help="Number of timed runs")
    parser.add_argument("--warmup", type=int, default=1, help="Number of warmup runs (not timed)")
    parser.add_argument("--spark-cmd", default="python", help="How to run Spark job (default: python)")
    parser.add_argument("--ray-cmd", default="python", help="How to run Ray job (default: python)")
    parser.add_argument("--seed", type=int, default=7, help="Seed for data generation (if used)")
    args = parser.parse_args()

    base = Path(args.out)
    spark_out = base / "spark"
    ray_out = base / "ray"
    results_json = base / "results.json"
    results_md = base / "results.md"

    if base.exists():
        shutil.rmtree(base)
    base.mkdir(parents=True, exist_ok=True)

    project_root = str(Path(__file__).resolve().parents[1])

    spark_cmd = [args.spark_cmd, "jobs/spark_job.py", "--in", args.input, "--out", str(spark_out)]
    ray_cmd = [args.ray_cmd, "jobs/ray_job.py", "--in", args.input, "--out", str(ray_out)]

    def timed_runs(label: str, cmd: list[str], out_path: Path) -> list[float]:
        times: list[float] = []
        # warmups
        for i in range(args.warmup):
            if out_path.exists():
                shutil.rmtree(out_path)
            _ = run(cmd, cwd=project_root)
            print(f"{label} warmup {i+1}/{args.warmup} done")
        # timed runs
        for i in range(args.runs):
            if out_path.exists():
                shutil.rmtree(out_path)
            t = run(cmd, cwd=project_root)
            times.append(t)
            print(f"{label} run {i+1}/{args.runs}: {t:.2f}s")
        return times

    spark_times = timed_runs("Spark", spark_cmd, spark_out)
    ray_times = timed_runs("Ray", ray_cmd, ray_out)

    # correctness validation (basic)
    spark_summary = read_summary(str(spark_out), engine="spark")
    ray_summary = read_summary(str(ray_out), engine="ray")
    cmp = compare(spark_summary, ray_summary)

    env = {
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "cpu_count": os.cpu_count(),
        "pwd": project_root,
        "spark_cmd": spark_cmd,
        "ray_cmd": ray_cmd,
        "input": args.input,
        "runs": args.runs,
        "warmup": args.warmup,
    }

    results = {
        "env": env,
        "spark": {
            "times_s": spark_times,
            "stats": {
                "min": min(spark_times),
                "max": max(spark_times),
                "mean": statistics.mean(spark_times),
                "stdev": statistics.pstdev(spark_times) if len(spark_times) > 1 else 0.0,
            },
            "output_summary": asdict(spark_summary),
        },
        "ray": {
            "times_s": ray_times,
            "stats": {
                "min": min(ray_times),
                "max": max(ray_times),
                "mean": statistics.mean(ray_times),
                "stdev": statistics.pstdev(ray_times) if len(ray_times) > 1 else 0.0,
            },
            "output_summary": asdict(ray_summary),
        },
        "validation": {k: {"spark": v[0], "ray": v[1]} for k, v in cmp.items()},
    }

    results_json.write_text(json.dumps(results, indent=2), encoding="utf-8")

    md = []
    md.append("# Spark vs Ray benchmark results\n")
    md.append("\n## What we measured\n")
    md.append(f"- Warmup runs (not timed): **{args.warmup}**\n")
    md.append(f"- Timed runs: **{args.runs}**\n")
    md.append("- Metric: **wall-clock time** (seconds)\n")
    md.append("- Validation: compare aggregated outputs (rows + sums)\n")

    md.append("\n## Environment\n")
    md.append(f"- Python: `{env['python']}`\n")
    md.append(f"- Platform: `{env['platform']}`\n")
    md.append(f"- CPU count: `{env['cpu_count']}`\n")
    md.append(f"- Input: `{env['input']}`\n")

    md.append("\n## Results (timed runs)\n")
    md.append(
        f"- Spark mean: **{results['spark']['stats']['mean']:.2f}s** "
        f"(min {results['spark']['stats']['min']:.2f}s, max {results['spark']['stats']['max']:.2f}s)\n"
    )
    md.append(
        f"- Ray mean: **{results['ray']['stats']['mean']:.2f}s** "
        f"(min {results['ray']['stats']['min']:.2f}s, max {results['ray']['stats']['max']:.2f}s)\n"
    )

    md.append("\n## Output validation (sanity check)\n")
    md.append("These numbers should match (or be extremely close for floating point sums):\n\n")
    for k, v in results["validation"].items():
        md.append(f"- {k}: Spark={v['spark']} | Ray={v['ray']}\n")

    md.append("\n## Notes\n")
    md.append("- First runs are often slower due to startup costs (JVM/Python, caches). That’s why we warm up.\n")
    md.append("- This is a local-mode tutorial benchmark. Distributed cluster benchmarks require different setup.\n")

    results_md.write_text("".join(md), encoding="utf-8")

    print("\n=== Benchmark Summary ===")
    print(f"Wrote: {results_json}")
    print(f"Wrote: {results_md}")
    print(f"Spark mean: {results['spark']['stats']['mean']:.2f}s")
    print(f"Ray mean:   {results['ray']['stats']['mean']:.2f}s")


if __name__ == "__main__":
    main()
