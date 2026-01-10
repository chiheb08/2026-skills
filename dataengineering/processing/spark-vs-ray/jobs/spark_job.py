"""Spark job: read CSV, filter by date range, aggregate per user, write output.

Run locally (example):
  spark-submit jobs/spark_job.py --in data/events.csv --out out/spark
"""

from __future__ import annotations

import argparse
from pyspark.sql import SparkSession
from pyspark.sql import functions as F


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--in", dest="inp", required=True, help="Input CSV")
    parser.add_argument("--out", required=True, help="Output folder")
    parser.add_argument("--start", default=None, help="ISO timestamp inclusive")
    parser.add_argument("--end", default=None, help="ISO timestamp exclusive")
    args = parser.parse_args()

    spark = (
        SparkSession.builder
        .appName("spark-vs-ray-spark-job")
        .getOrCreate()
    )

    df = (
        spark.read
        .option("header", True)
        .option("inferSchema", True)
        .csv(args.inp)
        .withColumn("ts", F.to_timestamp("ts"))
    )

    if args.start:
        df = df.filter(F.col("ts") >= F.to_timestamp(F.lit(args.start)))
    if args.end:
        df = df.filter(F.col("ts") < F.to_timestamp(F.lit(args.end)))

    # Aggregates per user
    out = (
        df.groupBy("user_id")
          .agg(
              F.count("*").alias("events"),
              F.sum("amount").alias("net_amount"),
              F.sum(F.when(F.col("event_type") == "purchase", 1).otherwise(0)).alias("purchases"),
          )
    )

    out.write.mode("overwrite").parquet(args.out)

    spark.stop()


if __name__ == "__main__":
    main()
