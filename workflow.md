Anda bertindak sebagai Senior Data Engineer / Data Platform Architect yang berpengalaman membangun production-grade data pipeline.

Saya memiliki sebuah aplikasi/project Data Engineering yang SUDAH BERJALAN. Jangan menganggap project ini kosong dan jangan melakukan rewrite dari nol.

Saya ingin melakukan refactoring dan pengembangan bertahap terhadap existing application menjadi:

# Multi-Source Crypto Trading Analytics Platform

Target teknologi yang WAJIB digunakan:

1. Python
2. asyncio
3. aiohttp untuk HTTP/API asynchronous ingestion
4. asyncpg untuk PostgreSQL asynchronous ingestion
5. Motor/PyMongo async-compatible approach untuk MongoDB asynchronous ingestion
6. PostgreSQL
7. MongoDB
8. MinIO sebagai object storage / data lake
9. Apache Airflow 3 sebagai orchestration
10. dbt sebagai transformation, modeling, testing, dan lineage layer
11. DuckDB untuk local dbt development/testing bila diperlukan
12. Databricks SQL Warehouse sebagai analytical warehouse
13. Docker / Docker Compose
14. Git / GitHub
15. pytest untuk automated testing
16. Ruff / SQLFluff atau tooling linting yang sesuai
17. Environment variables / .env untuk configuration dan secrets

JANGAN menambahkan teknologi lain hanya untuk memperbanyak tech stack.
Setiap teknologi harus memiliki tanggung jawab yang jelas dan alasan penggunaannya.

==================================================
## 1. KONTEKS PROJECT
==================================================

Project existing saya sebelumnya sudah memiliki beberapa komponen seperti:

- ingestion Indodax API
- Bronze writer
- Silver transformation
- Gold transformation
- data quality checks
- warehouse loader
- orchestration/pipeline
- Docker
- Airflow
- Databricks integration

Selain itu sudah tersedia/desain awal:

PostgreSQL:
- users
- accounts
- assets
- orders
- trades
- transactions
- etl_watermark

MongoDB:
- user_events

Indodax API:
- pairs
- summaries

Ada synthetic data generator untuk PostgreSQL dan MongoDB.

Karena aplikasi sudah ada, tugas Anda adalah:

AUDIT → REUSE → REFACTOR → EXTEND → MIGRATE → INTEGRATE → TEST

Bukan:

DELETE EVERYTHING → REWRITE EVERYTHING

==================================================
## 2. TARGET ARCHITECTURE
==================================================

Target akhir harus memiliki arsitektur:

                         ┌──────────────────┐
                         │   Indodax API    │
                         │   Market Data    │
                         └────────┬─────────┘
                                  │
                                  │ async HTTP
                                  ▼
┌──────────────────┐      ┌────────────────────┐      ┌──────────────────┐
│   PostgreSQL     │─────▶│                    │◀─────│     MongoDB      │
│                  │      │ Async Ingestion    │      │                  │
│ users            │      │ Layer              │      │ user_events      │
│ accounts         │      │                    │      │                  │
│ orders           │      └─────────┬──────────┘      └──────────────────┘
│ trades           │                │
│ transactions     │                │
└──────────────────┘                │
                                    ▼
                           ┌──────────────────┐
                           │      MinIO       │
                           │  Object Storage  │
                           │                  │
                           │     BRONZE       │
                           └────────┬─────────┘
                                    │
                                    │ dbt
                                    ▼
                           ┌──────────────────┐
                           │       dbt        │
                           │                  │
                           │    STAGING       │
                           │       ↓          │
                           │   INTERMEDIATE   │
                           │       ↓          │
                           │      MARTS       │
                           │                  │
                           │  SILVER → GOLD   │
                           └────────┬─────────┘
                                    │
                                    ▼
                         ┌─────────────────────┐
                         │     Databricks      │
                         │    SQL Warehouse    │
                         │                     │
                         │ Analytical DWH      │
                         └─────────────────────┘

Apache Airflow 3 berada di atas pipeline sebagai orchestration layer:

                    ┌────────────────────┐
                    │    Apache Airflow 3│
                    │                    │
                    │ scheduling         │
                    │ dependency         │
                    │ retry              │
                    │ monitoring         │
                    │ orchestration      │
                    └─────────┬──────────┘
                              │
             ┌────────────────┼────────────────┐
             ▼                ▼                ▼
        Ingestion           dbt            Databricks

==================================================
## 3. PRINSIP ARSITEKTUR
==================================================

Terapkan prinsip berikut:

### Separation of concerns

Python:
- ingestion
- API clients
- database extraction
- MinIO storage
- configuration
- infrastructure integration

asyncio:
- concurrency untuk I/O-bound operations

dbt:
- SQL transformation
- staging
- intermediate
- marts
- data tests
- documentation
- lineage

MinIO:
- raw/bronze object storage
- immutable/replayable data

Databricks:
- analytical warehouse
- business-ready analytical tables

Airflow:
- scheduling
- orchestration
- retries
- dependencies
- monitoring

Airflow JANGAN menjadi tempat business logic.

==================================================
## 4. PHASE 0 — AUDIT EXISTING APPLICATION
==================================================

Ini WAJIB menjadi langkah pertama.

Sebelum mengubah kode:

1. Inspect seluruh repository.
2. Identifikasi:
   - existing ingestion
   - existing API client
   - existing database access
   - existing Bronze writer
   - existing Silver transformation
   - existing Gold transformation
   - existing quality checks
   - existing warehouse loader
   - existing Airflow DAG
   - existing Docker configuration
   - existing Databricks configuration
   - existing tests
3. Untuk setiap komponen tentukan:
   - KEEP
   - REFACTOR
   - EXTEND
   - MIGRATE TO DBT
   - REPLACE
   - REMOVE
4. Jangan menghapus komponen sebelum memahami dependensinya.
5. Jangan membuat file baru jika existing file masih dapat digunakan dengan refactor yang reasonable.

Buat:

docs/audit.md

Berisi tabel:

| Component | Existing | Action | Reason | Dependency | Risk |

Buat juga:

docs/migration_plan.md

yang menjelaskan perubahan dari architecture lama ke architecture baru.

==================================================
## 5. PHASE 1 — BUSINESS REQUIREMENTS
==================================================

Definisikan business questions yang harus dapat dijawab platform.

Minimal:

1. Bagaimana performa harga crypto setiap hari?
2. Crypto mana yang memiliki volume market terbesar?
3. Bagaimana aktivitas trading berubah setiap hari?
4. Bagaimana hubungan price movement dengan trading volume?
5. Bagaimana aktivitas user berubah setiap hari?
6. Apakah market activity berhubungan dengan trading/user activity?

Buat:

docs/business_requirements.md

Setiap business question harus dipetakan ke:
- source
- required columns
- transformation
- target Gold model

==================================================
## 6. PHASE 2 — DATA CONTRACT & SCHEMA-FIRST
==================================================

Jangan mulai transformation sebelum data contract jelas.

Definisikan:

### Bronze contract

Indodax:
- pairs
- summaries

PostgreSQL:
- users
- accounts
- assets
- orders
- trades
- transactions

MongoDB:
- user_events

Gunakan struktur MinIO:

s3://indodax-data/

bronze/
├── indodax/
│   ├── pairs/
│   └── summaries/
├── postgresql/
│   ├── users/
│   ├── accounts/
│   ├── assets/
│   ├── orders/
│   ├── trades/
│   └── transactions/
└── mongodb/
    └── user_events/

Partition menggunakan ingestion timestamp:

ingestion_date=YYYY-MM-DD/hour=HH/

Contoh:

bronze/postgresql/orders/
ingestion_date=2026-09-12/
hour=15/
orders_20260912T150500Z.parquet

Bronze harus:
- raw
- immutable
- replayable
- auditable

Jangan melakukan business transformation di Bronze.

Buat:

docs/bronze_contract.md

==================================================
## 7. PHASE 3 — SILVER & GOLD DATA CONTRACT
==================================================

Definisikan grain secara eksplisit.

### gold_market_daily

Grain:
1 row per date + symbol

Columns:

date
symbol
open
high
low
close
volume
price_change_pct
volatility

### gold_trading_daily

Grain:
1 row per date + symbol

Columns:

date
symbol
total_orders
completed_orders
buy_volume
sell_volume
trading_volume
avg_trade_size

### gold_user_activity_daily

Grain:
1 row per date

Columns:

date
active_users
market_views
order_events
login_events

### gold_crypto_business_metrics

Grain:
1 row per date + symbol

Columns minimal:

date
symbol
close_price
market_volume
price_change_pct
trading_volume
total_orders
active_users
market_views

Buat:

docs/silver_contract.md
docs/gold_contract.md

==================================================
## 8. PHASE 4 — DOCKER INFRASTRUCTURE
==================================================

Project sudah memiliki Docker infrastructure.

Jangan membuat ulang jika service sudah tersedia.

Audit dan extend menjadi minimal:

- PostgreSQL application database
- MongoDB
- MinIO
- Airflow metadata PostgreSQL
- Airflow API Server
- Airflow Scheduler
- Airflow DAG Processor

Gunakan Airflow 3 architecture.

Gunakan LocalExecutor untuk local portfolio environment jika sesuai.

Jangan menambahkan Celery/Redis/worker jika tidak diperlukan.

Databricks tidak dijalankan dalam Docker.

Databricks adalah external analytical warehouse.

Pastikan resource usage rendah karena development environment memiliki keterbatasan RAM.

==================================================
## 9. PHASE 5 — ASYNC INGESTION FRAMEWORK
==================================================

Refactor existing ingestion agar asynchronous.

Gunakan:

Indodax:
aiohttp

PostgreSQL:
asyncpg

MongoDB:
Motor atau driver MongoDB asynchronous yang sesuai dengan versi library saat implementasi.

Jangan membuat seluruh aplikasi asynchronous secara paksa.

Gunakan async hanya untuk I/O-bound operations.

Data transformation lokal yang CPU/memory-bound tetap synchronous jika menggunakan Pandas atau library lainnya.

Target architecture:

Airflow task
    ↓
asyncio.run()
    ↓
async ingestion
    ↓
multiple sources concurrently

Gunakan:

asyncio.gather()

untuk menjalankan extraction source secara concurrent jika aman.

Contoh:

await asyncio.gather(
    extract_indodax(),
    extract_postgres(),
    extract_mongodb()
)

Pastikan error dari satu source dapat ditangani secara jelas.

==================================================
## 10. PHASE 6 — INGESTION CLIENT DESIGN
==================================================

Buat abstraction yang konsisten.

Contoh struktur:

src/
└── ingestion/
    ├── base.py
    ├── indodax.py
    ├── postgres.py
    ├── mongodb.py
    ├── watermark.py
    ├── retry.py
    └── models.py

Jangan copy-paste logic retry/logging/configuration ke setiap client.

Shared functionality harus di-abstraction.

Setiap extractor harus:
- menerima configuration
- mengambil watermark
- extract data
- validate response
- menghasilkan metadata extraction
- mengembalikan data
- mencatat metrics/logging
- menangani retry
- tidak mengubah watermark sebelum Bronze berhasil

==================================================
## 11. PHASE 7 — INCREMENTAL EXTRACTION
==================================================

Pipeline harus incremental.

Jangan melakukan full extraction setiap run jika source mendukung incremental extraction.

Gunakan etl_watermark.

Minimal:

source_name
dataset_name
watermark_column
last_successful_value
updated_at
status

Contoh:

postgres | orders | updated_at | 2026-09-12T14:55:00 | success

PostgreSQL:

WHERE updated_at > watermark

ORDER BY updated_at

MongoDB:

filter berdasarkan field timestamp yang sesuai.

Indodax:
gunakan strategi yang sesuai karakteristik API karena public API mungkin tidak menyediakan watermark seperti database transactional sources.

Jangan memaksakan watermark yang tidak tersedia.

==================================================
## 12. PHASE 8 — WATERMARK SAFETY
==================================================

Urutan wajib:

extract
↓
validate
↓
write Bronze
↓
verify Bronze
↓
commit/update watermark

Jangan:

extract
↓
update watermark
↓
write Bronze

Jika Bronze gagal:
- pipeline/task harus fail
- watermark tidak boleh maju

Pipeline harus aman terhadap retry.

==================================================
## 13. PHASE 9 — MINIO BRONZE
==================================================

MinIO harus menjadi object storage utama sejak awal.

Jangan membuat architecture:

Source → local filesystem → migration → MinIO

Target:

Source → async ingestion → MinIO

Buat storage abstraction agar business logic tidak bergantung langsung pada implementation detail MinIO.

Contoh:

src/storage/
└── minio.py

Gunakan:
- boto3 atau S3-compatible client yang sesuai
- atomic upload strategy bila diperlukan
- deterministic object naming
- partitioned paths

Gunakan format:

JSON:
- raw API/document data jika preservation struktur original penting

Parquet:
- tabular database extracts atau data yang memang cocok untuk columnar processing

Jangan memaksakan semua source menjadi Parquet jika itu menghilangkan raw fidelity.

==================================================
## 14. PHASE 10 — DBT FOUNDATION
==================================================

dbt WAJIB menjadi transformation layer utama.

Jangan mempertahankan seluruh business transformation di Python jika logic tersebut lebih tepat dilakukan dengan SQL/dbt.

Target:

dbt_crypto_platform/

├── models/
│   ├── staging/
│   │   ├── indodax/
│   │   ├── postgres/
│   │   └── mongodb/
│   ├── intermediate/
│   └── marts/
│       ├── market/
│       ├── trading/
│       ├── activity/
│       └── business/
├── tests/
├── macros/
├── seeds/
├── snapshots/
├── dbt_project.yml
└── packages.yml

Gunakan dbt-duckdb untuk local development/testing jika sesuai.

Gunakan dbt-databricks untuk target Databricks.

Jangan membuat credentials hardcoded.

==================================================
## 15. PHASE 11 — DBT STAGING / SILVER
==================================================

Staging model harus melakukan:

- rename
- cast
- standardization
- basic cleaning
- deduplication
- source normalization

Jangan melakukan business aggregation berat di staging.

Model minimal:

stg_indodax__pairs
stg_indodax__summaries

stg_postgres__users
stg_postgres__accounts
stg_postgres__assets
stg_postgres__orders
stg_postgres__trades
stg_postgres__transactions

stg_mongodb__user_events

MongoDB nested event context harus dinormalisasi/flatten secara tepat.

==================================================
## 16. PHASE 12 — DBT INTERMEDIATE
==================================================

Intermediate adalah tempat:

- join
- enrichment
- reusable transformations
- domain integration

Minimal:

int_orders_trades
int_daily_market
int_user_events_daily
int_user_trading_activity

Jangan melakukan business-specific final presentation logic terlalu dini.

Gunakan intermediate hanya jika transformation tersebut reusable atau membantu menjaga mart tetap clean.

==================================================
## 17. PHASE 13 — DBT MARTS / GOLD
==================================================

Implementasikan:

gold_market_daily
gold_trading_daily
gold_user_activity_daily
gold_crypto_business_metrics

Gunakan materialization yang sesuai.

Gunakan incremental models jika memang workload dan source pattern membutuhkannya.

Jangan menggunakan incremental hanya demi terlihat "advanced".

Pastikan unique key sesuai grain.

Contoh:

date + symbol

Gunakan merge/upsert strategy jika didukung dan sesuai target warehouse.

==================================================
## 18. PHASE 14 — DBT DATA QUALITY
==================================================

Gunakan:

Generic tests:
- not_null
- unique
- accepted_values
- relationships

Singular/business tests:

1. filled_quantity <= quantity
2. no orphan trades
3. account balance reconciliation
4. price > 0
5. volume >= 0
6. business metric consistency

Gunakan dbt build sebagai validation pipeline utama jika sesuai.

Pastikan failure menghasilkan non-zero exit code agar Airflow dapat mendeteksi failure.

==================================================
## 19. PHASE 15 — DATABRICKS
==================================================

Databricks adalah analytical warehouse final.

Target:

Databricks SQL Warehouse

Logical structure:

catalog
└── crypto_platform
    ├── staging
    ├── intermediate
    └── marts

Gold berada pada:

crypto_platform.marts

Gunakan dbt-databricks untuk deployment.

Environment:

dev:
DuckDB/local

prod:
Databricks

Credentials melalui environment variables:

DATABRICKS_HOST
DATABRICKS_HTTP_PATH
DATABRICKS_TOKEN

Jangan commit:
- token
- password
- secrets
- profiles.yml yang berisi credential

==================================================
## 20. PHASE 16 — AIRFLOW 3
==================================================

Gunakan Apache Airflow 3.

Airflow bertanggung jawab atas:

- scheduling
- task dependency
- retries
- backoff
- observability
- orchestration

Airflow bukan transformation engine.

Untuk portfolio, mulai dengan satu modular DAG:

crypto_pipeline

Logical flow:

start
  ↓
┌──────────────┬───────────────┬───────────────┐
│              │               │
▼              ▼               ▼
Indodax      PostgreSQL      MongoDB
extract       extract         extract
│              │               │
└──────────────┴───────────────┘
                ↓
             Bronze
                ↓
             dbt build
                ↓
          Databricks
                ↓
               END

Extraction tasks dapat berjalan parallel.

Jangan langsung membuat banyak DAG hanya untuk menunjukkan kompleksitas.

Pisahkan DAG jika ada business/domain/scheduling boundary yang benar-benar berbeda.

==================================================
## 21. PHASE 17 — AIRFLOW + ASYNC
==================================================

Airflow task tetap synchronous pada level orchestration.

Di dalam task:

asyncio.run()

Kemudian jalankan async ingestion.

Contoh konsep:

@task
def extract_sources():
    asyncio.run(extract_all_sources())

Jangan mencoba menjadikan seluruh Airflow DAG sebagai native async coroutine tanpa alasan.

Gunakan async untuk concurrent I/O.

==================================================
## 22. PHASE 18 — AIRFLOW RETRY POLICY
==================================================

Extraction:
- retry 3
- exponential backoff
- timeout yang masuk akal

dbt:
- retry minimal
- failure harus terlihat

Database/network/API transient errors:
- retry

SQL/model/code errors:
- jangan retry berkali-kali

Tambahkan:
- execution timeout
- sensible task timeout
- clear logging

==================================================
## 23. PHASE 19 — IDEMPOTENCY
==================================================

Pipeline harus idempotent.

Jika task dijalankan ulang:

- tidak membuat duplicate Bronze yang tidak dapat dilacak
- tidak membuat duplicate Silver
- tidak membuat duplicate Gold
- tidak memajukan watermark secara salah

Gunakan:
- deterministic object keys
- extraction/run metadata
- unique keys
- incremental models
- merge/upsert jika sesuai

Tambahkan run_id sebagai metadata/audit field jika berguna.

==================================================
## 24. PHASE 20 — OBSERVABILITY
==================================================

Gunakan structured logging.

Minimal setiap extraction mencatat:

run_id
source
dataset
start_time
end_time
rows_extracted
watermark_before
watermark_after
status
duration

Contoh:

INFO
source=postgres
dataset=orders
rows=1248
watermark_before=...
watermark_after=...
duration=2.81
status=success

Jangan hanya menggunakan print().

==================================================
## 25. PHASE 21 — TESTING
==================================================

Buat:

tests/
├── unit/
├── integration/
└── data_quality/

Unit tests:
- watermark
- parsing
- configuration
- partition naming
- validation
- retry behavior

Integration tests:
- PostgreSQL ingestion
- MongoDB ingestion
- Indodax ingestion
- MinIO write
- dbt integration

Data quality:
- dbt generic tests
- dbt singular tests

Jangan membuat test hanya untuk mengejar coverage.
Prioritaskan critical path.

==================================================
## 26. PHASE 22 — FAILURE TESTING
==================================================

WAJIB menunjukkan pipeline dapat gagal dengan benar.

Scenario 1:
PostgreSQL mati

Expected:
extract retry
→ failure
→ watermark tidak maju
→ Bronze tidak dianggap berhasil

Scenario 2:
MongoDB mati

Expected:
retry
→ task failure

Scenario 3:
Indodax API timeout

Expected:
retry + exponential backoff

Scenario 4:
Invalid data

Contoh:
price < 0

Expected:
dbt test FAIL

Scenario 5:
Duplicate primary key

Expected:
dbt unique test FAIL

Scenario 6:
Orphan trade

Expected:
relationship/singular test FAIL

Scenario 7:
Bronze object missing

Expected:
downstream validation/dbt failure

Dokumentasikan:

docs/failure_testing.md

Untuk setiap scenario tulis:
- setup
- expected behavior
- actual behavior
- logs
- recovery
- lesson learned

==================================================
## 27. PHASE 23 — CI/CD
==================================================

GitHub Actions minimal:

On pull request:

ruff
pytest
dbt parse
dbt build menggunakan DuckDB/fixture data

Jangan menjalankan full Databricks pipeline untuk setiap PR kecuali memang dibutuhkan.

CI harus murah dan deterministic.

==================================================
## 28. PHASE 24 — SECURITY & CONFIGURATION
==================================================

Semua secret melalui environment variables.

Gunakan:

.env

dan:

.env.example

.gitignore harus mencakup:

.env
profiles.yml
*.duckdb
target/
logs/
__pycache__/
credentials/
secrets/

Jangan pernah memasukkan:
- Databricks token
- database password
- API secret
- Mongo credential

ke Git.

==================================================
## 29. PHASE 25 — DOCUMENTATION
==================================================

Buat dokumentasi:

docs/
├── audit.md
├── migration_plan.md
├── business_requirements.md
├── architecture.md
├── bronze_contract.md
├── silver_contract.md
├── gold_contract.md
├── ingestion.md
├── dbt.md
├── airflow.md
├── databricks.md
├── data_quality.md
├── failure_testing.md
└── decisions.md

README harus dapat menjelaskan project dalam <5 menit.

README:

1. Problem statement
2. Business questions
3. Architecture diagram
4. Data sources
5. Technology stack
6. Data flow
7. Async ingestion
8. MinIO Bronze
9. dbt transformation
10. Databricks warehouse
11. Airflow orchestration
12. Data quality
13. Failure recovery
14. How to run
15. Example queries
16. Screenshots/evidence

==================================================
## 30. PHASE 26 — PORTFOLIO EVIDENCE
==================================================

Project harus menghasilkan evidence yang dapat ditunjukkan kepada recruiter/HR.

Minimal:

1. Indodax API response
2. PostgreSQL source data
3. MongoDB source data
4. MinIO Bronze structure
5. Airflow DAG success
6. Airflow retry/failure
7. dbt lineage
8. dbt test result
9. Databricks SQL query
10. Gold business metrics

Contoh query:

SELECT *
FROM crypto_platform.marts.gold_crypto_business_metrics
ORDER BY date DESC
LIMIT 20;

Screenshot harus menunjukkan hasil nyata, bukan mockup.

==================================================
## 31. RESOURCE CONSTRAINTS
==================================================

Development environment saya memiliki resource terbatas, sekitar 8 GB RAM.

Karena itu:

- jangan menjalankan service yang tidak diperlukan
- jangan menggunakan Spark lokal hanya untuk portfolio
- jangan menggunakan Kafka jika tidak diperlukan
- jangan menggunakan Celery jika LocalExecutor cukup
- jangan membuat banyak Airflow worker
- jangan membuat banyak database instance
- gunakan Databricks sebagai external compute
- gunakan DuckDB untuk local dbt testing
- gunakan async hanya untuk concurrency yang benar-benar bermanfaat

Best practice bukan berarti menambahkan sebanyak mungkin teknologi.

==================================================
## 32. MIGRATION STRATEGY
==================================================

Karena existing application sudah berjalan, lakukan perubahan secara incremental.

Untuk setiap perubahan:

1. inspect existing implementation
2. jelaskan masalah/limitasi
3. tentukan KEEP / REFACTOR / EXTEND / MIGRATE
4. implement perubahan kecil
5. run existing tests
6. run new tests
7. verify behavior
8. lanjut ke tahap berikutnya

Jangan melakukan big-bang rewrite.

Jika logic existing masih bagus, gunakan kembali.

Jika existing Pandas transformation sekarang akan dipindahkan ke dbt:
- jelaskan logic yang dipindahkan
- buat equivalent dbt model
- validasi output lama vs output dbt
- baru hapus/deprecate logic lama

==================================================
## 33. IMPORTANT DBT MIGRATION RULE
==================================================

Pandas tidak harus dihapus seluruhnya.

Gunakan Python/Pandas jika:
- parsing API kompleks
- preprocessing yang lebih mudah dilakukan di Python
- validation sebelum storage
- logic yang memang bukan SQL transformation

Gunakan dbt jika:
- SQL transformation
- join
- aggregation
- business metrics
- dimensional/analytical modeling
- data quality tests
- lineage
- documentation

Tujuannya bukan "semua harus dbt".

Tujuannya adalah separation of responsibility yang benar.

==================================================
## 34. EXPECTED FINAL FLOW
==================================================

Final pipeline:

Indodax API
      │
PostgreSQL
      │
MongoDB
      │
      ▼
Async Ingestion
      │
      ▼
MinIO Bronze
      │
      ▼
dbt Staging
      │
      ▼
dbt Intermediate
      │
      ▼
dbt Marts / Gold
      │
      ▼
Databricks SQL Warehouse
      │
      ▼
Analytics / BI

Airflow 3 mengorkestrasi seluruh flow tersebut.

==================================================
## 35. EXECUTION RULES FOR YOU
==================================================

Jangan langsung memberikan seluruh kode project sekaligus.

Kerjakan secara bertahap.

Pada setiap phase:

1. Jelaskan tujuan phase.
2. Inspect existing files yang relevan.
3. Tunjukkan file yang akan:
   - KEEP
   - MODIFY
   - CREATE
   - DEPRECATE
4. Jelaskan alasan arsitekturnya.
5. Berikan implementasi konkret.
6. Berikan command yang harus dijalankan.
7. Berikan expected output.
8. Berikan verification checklist.
9. Jangan lanjut ke phase berikutnya sebelum phase saat ini tervalidasi.

Jika menemukan existing implementation yang sudah benar:
JANGAN rewrite hanya demi mengikuti struktur Anda.

Jika menemukan konflik architecture:
jelaskan trade-off terlebih dahulu.

Jika ada beberapa pilihan:
pilih satu rekomendasi utama dan jelaskan mengapa pilihan tersebut paling sesuai untuk:
- existing application
- portfolio Data Engineering
- resource 8 GB RAM
- maintainability
- production-like architecture

==================================================
## 36. OUTPUT PERTAMA YANG SAYA INGINKAN
==================================================

Jangan langsung coding.

Mulai dengan:

### A. Existing Architecture Assessment

Berdasarkan repository/project yang saya berikan:
- petakan architecture existing
- identifikasi komponen
- identifikasi dependency
- identifikasi bagian yang dapat dipertahankan

### B. Target Architecture

Berikan architecture final.

### C. Migration Matrix

Buat tabel:

| Existing Component | Target Component | Action | Reason |
|---|---|---|---|

### D. Final Project Structure

Tunjukkan struktur folder final yang realistis.

### E. Phase Plan

Berikan seluruh phase 0 sampai selesai.

### F. Risk Register

Minimal:
- breaking existing application
- duplicate data
- watermark corruption
- MinIO failure
- dbt failure
- Databricks connection failure
- Airflow retry issue
- schema drift
- resource exhaustion

### G. Start Phase 0

Setelah assessment selesai, mulai Phase 0 secara konkret.

JANGAN melewati audit.

==================================================
## 37. DEFINITION OF DONE
==================================================

Project dianggap selesai hanya jika:

[ ] Existing application successfully audited
[ ] Existing functionality preserved where appropriate
[ ] Business requirements documented
[ ] PostgreSQL integrated
[ ] MongoDB integrated
[ ] Indodax API integrated
[ ] Async ingestion implemented
[ ] Incremental ingestion implemented
[ ] Watermark implemented safely
[ ] MinIO implemented as Bronze object storage
[ ] Bronze contract implemented
[ ] dbt staging implemented
[ ] dbt intermediate implemented
[ ] dbt marts implemented
[ ] dbt tests implemented
[ ] Databricks SQL Warehouse integrated
[ ] Airflow 3 orchestrates pipeline
[ ] Airflow retries implemented
[ ] Pipeline idempotent
[ ] Structured logging implemented
[ ] Unit tests implemented
[ ] Integration tests implemented
[ ] Failure testing implemented
[ ] CI implemented
[ ] Documentation complete
[ ] Portfolio evidence collected
[ ] Final end-to-end pipeline succeeds

==================================================
## FINAL PRINCIPLE
==================================================

Jadilah pragmatis.

Saya tidak membutuhkan architecture yang terlihat kompleks.

Saya membutuhkan architecture yang:
- technically correct
- maintainable
- explainable saat interview
- production-like
- resource-efficient
- testable
- observable
- reproducible
- incremental
- idempotent

Dan yang paling penting:

EXISTING APPLICATION HARUS MENJADI STARTING POINT.

Jangan membangun project baru dari nol.
Refactor dan evolve aplikasi yang sudah ada secara bertahap.
