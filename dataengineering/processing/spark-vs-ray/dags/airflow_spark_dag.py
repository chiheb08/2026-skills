"""Airflow DAG that runs the Spark job (local Spark via PySpark).

For a Docker Compose tutorial, the simplest approach is to run Spark in local mode
inside the Airflow container (Java + PySpark installed).
"""

from __future__ import annotations

from datetime import datetime

from airflow import DAG
from airflow.operators.bash import BashOperator


with DAG(
    dag_id="spark_job_example",
    start_date=datetime(2025, 1, 1),
    schedule=None,
    catchup=False,
    tags=["tutorial", "spark"],
) as dag:
    generate_data = BashOperator(
        task_id="generate_data",
        bash_command=(
            "python /opt/project/data/generate_data.py "
            "--out /opt/project/data/events.csv "
            "--rows 200000 "
            "--users 20000 "
            "--days 30"
        ),
    )
    run_spark = BashOperator(
        task_id="run_spark_job",
        bash_command=(
            "python /opt/project/jobs/spark_job.py "
            "--in /opt/project/data/events.csv "
            "--out /opt/project/out/spark"
        ),
    )

    generate_data >> run_spark
