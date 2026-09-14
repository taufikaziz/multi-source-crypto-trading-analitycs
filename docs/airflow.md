# Airflow Orchestration Documentation (Phase 25)

## Engine Architecture
- **Version**: Apache Airflow 3
- **Executor**: `LocalExecutor`
- **Topology**:
  - `indodax-app-postgres`: Application transactional database (`5433:5432`)
  - `indodax-airflow-postgres`: Airflow metadata DB (`5432:5432`)
  - `indodax-mongodb`: User interaction & event store (`27017:27017`)
  - `indodax-minio`: S3-compatible Bronze storage (`9000` API, `9002` Console)
  - `indodax-airflow-api`: FastAPI backend & Web UI (`8080:8080`)
  - `indodax-airflow-scheduler`: Task trigger & dependency coordinator
  - `indodax-airflow-dag-processor`: Parsing DAG mandiri

## DAG DAG Flow
```
                   ┌── extract_indodax ────┐
start ─────────────┼── extract_postgresql ─┼──> load_bronze_to_databricks ──> dbt_build_warehouse ──> end
                   └── extract_mongodb ────┘
```
