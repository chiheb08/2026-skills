# Spark vs Ray (Airflow tutorial + benchmark)

This folder is a mini project to support a Medium article comparing **Apache Spark** vs **Ray**.

It contains:
- a synthetic dataset generator
- the same workload implemented in Spark and Ray
- Airflow DAGs to orchestrate each
- a simple benchmark script

## Folder layout

- `article/`: the Medium article (Markdown + PDF)
- `data/`: synthetic dataset generator + generated CSV
- `jobs/`: Spark and Ray job code
- `dags/`: Airflow DAGs
- `bench/`: benchmark runner
- `out/`: outputs (created when you run jobs)

## What workload are we comparing?

We generate user events, then compute per-user aggregates:
- total events
- net amount
- number of purchases

This is intentionally “data engineer realistic” and easy to explain.

## 1) Generate data

From this folder:

```bash
python data/generate_data.py --out data/events.csv --rows 2000000 --users 100000 --days 30
```

Smaller quick run:

```bash
python data/generate_data.py --out data/events.csv --rows 200000 --users 20000 --days 30
```

## 2) Run Spark job

Requires Java + PySpark installed.

```bash
python jobs/spark_job.py --in data/events.csv --out out/spark
```

## 3) Run Ray job

Requires Ray installed.

```bash
python jobs/ray_job.py --in data/events.csv --out out/ray
```

## 4) Run the benchmark

```bash
python bench/run_benchmark.py --input data/events.csv --out out/benchmark --warmup 1 --runs 5
```

This prints wall-clock timing for Spark vs Ray and writes:
- `out/benchmark/results.json` (full detail)
- `out/benchmark/results.md` (copy/paste into Medium)

## 5) Airflow tutorial (two DAGs)

The DAGs are in `dags/`:
- `airflow_spark_dag.py`
- `airflow_ray_dag.py`

In a real deployment, you’d mount this project into your Airflow environment (e.g., Docker/Kubernetes) at `/opt/project`.

### What the DAGs do
- Spark DAG calls `python .../jobs/spark_job.py` (Spark runs in local mode via PySpark)
- Ray DAG calls `python .../jobs/ray_job.py`

## 6) Run everything with Docker Compose (recommended)

From this folder:

```bash
docker compose up --build
```

Then open Airflow:
- `http://localhost:8080`

Login:
- username: `admin`
- password: `admin`

In the Airflow UI, you should see two DAGs:
- `spark_job_example`
- `ray_job_example`

Trigger them manually. Each DAG will:
- generate a small dataset (`data/events.csv`)
- run its job
- write output to `out/`

### Run the benchmark inside Docker

```bash
docker compose exec airflow bash -lc "cd /opt/project && python bench/run_benchmark.py --input data/events.csv --out out/benchmark --warmup 1 --runs 5"
```

Then open:
- `out/benchmark/results.md` (nice summary)
- `out/benchmark/results.json` (full detail)

To stop:

```bash
docker compose down
```

## Notes on “fair” performance comparisons

For a Medium article, if you want your comparison to be trustworthy, report:
- dataset size and schema
- hardware (CPU/RAM/disk)
- Spark configs (executors, shuffle partitions)
- Ray configs (num_cpus, dataset parallelism)
- warmup strategy (first run often includes JVM startup)

If you want, I can extend this project with:
- multiple benchmark iterations + summary stats
- memory measurements
- output validation checks (row counts + hashes)
- a Docker Compose setup for Airflow + Spark + Ray
