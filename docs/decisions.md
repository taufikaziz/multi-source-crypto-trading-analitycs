# Architecture Decisions Record (ADR) (Phase 25)

| ADR ID | Decision | Context | Trade-off / Rationale |
|---|---|---|---|
| **ADR-01** | Medallion Architecture (Bronze -> Silver -> Gold) | Kebutuhan audit trail dan data replayability | Membutuhkan storage layer tambahan (MinIO), namun menjamin raw fidelity & data lineage. |
| **ADR-02** | dbt for In-Warehouse Transformations | Memisahkan concern transformasi data dari orkestrasi Python | SQL declarative modeling lebih mudah di-maintain, didokumentasikan, dan diuji secara otomatis. |
| **ADR-03** | PostgreSQL-backed Watermarking | Pelacakan delta extraction multi-source | Menghilangkan state dependency pada Airflow DB; watermark dapat dipulihkan secara independen. |
| **ADR-04** | MinIO S3 Object Storage as Bronze First | Menyimpan raw multi-format (JSON + Parquet) | Menyerupai production AWS S3 / Azure Data Lake, kompatibel penuh dengan dbt & Databricks connector. |
| **ADR-05** | Airflow 3 with LocalExecutor | Orkestrasi pada environment 8 GB RAM | Menghilangkan kebutuhan Celery worker/Redis overhead, tetap mendukung paralel task execution. |
