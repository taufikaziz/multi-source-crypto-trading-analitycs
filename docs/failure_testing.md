# Failure & Chaos Testing Documentation (Phase 22)

Dokumentasi ini mencatat pengujian skenario kegagalan (failure scenarios) pada platform data cryptocurrency multi-source untuk membuktikan ketangguhan sistem data platform saat terjadi gangguan.

---

## Scenario 1: PostgreSQL Connection Down / Unreachable

- **Setup**: Database transaksional PostgreSQL tidak dapat diakses (koneksi timeout / port closed).
- **Expected Behavior**:
  - `PostgresExtractor` mencoba reconnect hingga limit retry (3x) dengan exponential backoff.
  - Setelah retries habis, melempar `ExtractionError`.
  - Task Airflow `extract_postgresql` berstatus FAILED.
  - Watermark pada `etl_watermark` **TIDAK MAJU**.
  - Pipeline berhenti sebelum menulis Bronze yang tidak lengkap.
- **Actual Behavior**: Terbukti via `tests/test_failure_scenarios.py::test_postgres_failure_prevents_watermark_advance` di mana `WatermarkManager.commit_watermarks` tidak pernah terpanggil.
- **Recovery Procedure**: Perbaiki status container/database PostgreSQL. Scheduled run berikutnya atau manual retry di Airflow akan melanjutkan dari watermark terakhir yang tersimpan dengan aman tanpa data loss.
- **Lesson Learned**: Strict sequential dependency (`Extract -> Bronze Write -> Watermark Commit`) mencegah watermark corruption saat source failure.

---

## Scenario 2: MongoDB Unreachable / Query Timeout

- **Setup**: MongoDB connection timeout saat fetching collection `user_events`.
- **Expected Behavior**:
  - Extractor melakukan retry terukur lalu melempar `ExtractionError`.
  - Task `extract_mongodb` fail secara terisolasi tanpa mempengaruhi data di layer Bronze.
- **Actual Behavior**: Terbukti via `tests/test_failure_scenarios.py::test_mongodb_failure_raises_cleanly`.
- **Recovery Procedure**: Service restart MongoDB, Airflow task retry otomatis berjalan sesuai retry policy.
- **Lesson Learned**: Concurrency extraction menggunakan task terpisah mencegah cascade failure ke source lain (Indodax API tetap dapat menyelesaikan extraction miliknya).

---

## Scenario 3: Indodax API Rate Limit (429) & Transient 5xx Errors

- **Setup**: HTTP response 429 Too Many Requests atau 502 Bad Gateway dari public API.
- **Expected Behavior**:
  - `IndodaxClient` mendeteksi status code transient (`_RETRY_STATUSES = {429, 500, 502, 503, 504}`).
  - Menjalankan sleep exponential backoff (`compute_backoff(attempt)`) sebelum retry berikutnya.
- **Actual Behavior**: Teruji pada `src/ingestion/indodax_client.py` dan `tests/test_ingestion_retry.py`.
- **Lesson Learned**: Pemisahan error transient vs code-error (fail-fast) menghemat execution time.

---

## Scenario 4: MinIO Bronze Upload Failure

- **Setup**: S3/MinIO service down atau bucket write timeout.
- **Expected Behavior**:
  - `BronzeWriter` gagal menulis file.
  - Eksekusi terputus sebelum `commit_source_watermarks` dipanggil.
- **Actual Behavior**: Terbukti via `tests/test_failure_scenarios.py::test_bronze_failure_aborts_watermark_commit`.
- **Lesson Learned**: Tidak ada watermark yang committed jika raw file belum tersimpan di Bronze lake.

---

## Scenario 5: Data Quality Violation (Negative Price / Orphan Trades)

- **Setup**: Row data kotor dengan `price <= 0` atau `trade_id` tanpa `order_id` yang cocok.
- **Expected Behavior**:
  - dbt generic test (`not_null`, `unique`, `accepted_values`) atau dbt singular test (`test_no_orphan_trades`, `test_positive_prices`) mengembalikan non-zero rows.
  - `dbt build` menghasilkan non-zero exit code.
  - Airflow mendeteksi task `dbt_build_warehouse` sebagai FAILED.
- **Recovery Procedure**: Quarantine data kotor di staging, perbaiki validasi upstream, rerun dbt build.
