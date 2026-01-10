"""Airflow DAG that runs the Ray job.

This uses BashOperator to run a Python script.
"""

from __future__ import annotations

from datetime import datetime

from airflow import DAG
from airflow.operators.bash import BashOperator


with DAG(
    dag_id="ray_job_example",
    start_date=datetime(2025, 1, 1),
    schedule=None,
    catchup=False,
    tags=["tutorial", "ray"],
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
    run_ray = BashOperator(
        task_id="run_ray_job",
        bash_command=(
            "python /opt/project/jobs/ray_job.py "
            "--in /opt/project/data/events.csv "
            "--out /opt/project/out/ray"
        ),
    )

    generate_data >> run_ray
