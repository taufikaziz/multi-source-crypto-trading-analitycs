# Master Workflow â€” Multi-Source Crypto Trading Analytics Platform

Dokumen ini adalah checklist kerja lengkap, dari kondisi project sekarang
(hanya ingest Indodax API) sampai jadi platform multi-source penuh. Setiap
fase punya: **tujuan**, **langkah konkret** (dengan command kalau ada),
**output**, **cara verifikasi**, dan **status**.

Kerjakan urut dari atas ke bawah. Jangan loncat fase â€” tiap fase adalah
fondasi untuk fase berikutnya.

Status: âœ… selesai Â· â³ belum dikerjakan

---

## FASE 0 â€” Fondasi Repo

**Tujuan:** siapkan struktur dasar sebelum menulis logic apapun.

1. Kalau belum ada git repo: `git init`, buat branch kerja
   `git checkout -b refactor/multi-source-platform`.
2. Buat struktur folder berikut di root project (boleh pakai `mkdir -p`
   sekaligus):
   ```
   mkdir -p infra/postgres/init infra/mongodb/init infra/minio
   mkdir -p scripts src/ingestion src/bronze src/quality
   mkdir -p dbt_crypto_platform dags docs
   ```
3. Buat `.gitignore` minimal, isi:
   ```
   .env
   venv/
   __pycache__/
   *.duckdb
   dbt_crypto_platform/target/
   dbt_crypto_platform/logs/
   dbt_crypto_platform/profiles.yml
   ```
4. Buat virtual environment Python:
   ```
   python3 -m venv venv
   source venv/bin/activate      # Windows: venv\Scripts\activate
   ```
5. Buat `requirements.txt` awal (akan ditambah lagi tiap fase butuh library
   baru):
   ```
   pandas
   numpy
   requests
   aiohttp
   aiofiles
   asyncpg
   motor
   psycopg2-binary
   pymongo
   faker
   duckdb
   python-dotenv
   ```
   Install: `pip install -r requirements.txt`

**Output:** struktur folder kosong, git repo siap, virtualenv aktif.
**Verifikasi:** `git status` menunjukkan folder baru; `pip list` menunjukkan
semua library ter-install.
**Status: â³**

---

## FASE 1 â€” Audit & Requirements

**Tujuan:** pastikan kode lama yang bagus tidak dibuang, requirement bisnis
jelas sebelum desain skema.

1. Buka project existing kamu, inventarisasi file-file yang sudah ada
   (`indodax_client.py`, `bronze/writer.py`, `silver/transformer.py`, dst).
2. Untuk tiap file, tentukan: **dipertahankan as-is**, **perlu digeneralize**,
   atau **akan digantikan dbt**. Tulis ke `docs/audit.md`.
3. Tulis `docs/requirements.md` berisi 6 business questions yang sudah
   disepakati sebelumnya, plus untuk tiap pertanyaan: kolom data apa yang
   dibutuhkan untuk menjawabnya (ini nanti jadi acuan desain kolom Gold).

**Output:** `docs/audit.md`, `docs/requirements.md`.
**Verifikasi:** baca ulang kedua file, pastikan tidak ada bagian yang masih
kosong/placeholder.
**Status: â³**

---

## FASE 2 â€” Desain Data (Schema-First)

**Tujuan:** kontrak data (skema) ditulis sebelum coding, supaya Silver/Gold
tidak berubah-ubah di tengah implementasi.

| Sub-fase | Isi | Status |
|---|---|---|
| 2.1 | Skema PostgreSQL (`assets`, `users`, `accounts`, `orders`, `trades`, `transactions`, `etl_watermark`) | âœ… â€” `infra/postgres/init/01_schema.sql`, dokumentasi di `docs/postgres_schema.md` |
| 2.2 | Generator data sintetis PostgreSQL | âœ… â€” `scripts/generate_synthetic_data.py` |
| 2.3 | Desain koleksi MongoDB `user_events` (nested document, validator, index) | âœ… â€” `infra/mongodb/init/01_validation_and_indexes.js`, dokumentasi di `docs/mongodb_schema.md` |
| 2.4 | Generator data sintetis MongoDB | âœ… â€” `scripts/generate_mongo_events.py` |
| 2.5 | Kontrak Bronze: nama dataset, strategi partisi, format file per source | â³ |
| 2.6 | Kontrak Silver: kolom, tipe, constraint tiap staging model | â³ |
| 2.7 | Kontrak Gold: kolom, grain, tipe agregasi tiap mart | â³ |

### Langkah 2.5 â€” Kontrak Bronze (kerjakan sekarang)

1. Tulis `docs/bronze_contract.md`, isi tabel berikut untuk tiap source:

   | Source | Dataset name | Format file | Path partisi |
   |---|---|---|---|
   | Indodax | `pairs`, `summaries` | JSON mentah | `bronze/indodax/{dataset}/ingestion_date={date}/hour={hour}/` |
   | PostgreSQL | `users`, `accounts`, `orders`, `trades`, `transactions` | Parquet | `bronze/postgresql/{dataset}/ingestion_date={date}/hour={hour}/` |
   | MongoDB | `user_events` | JSON mentah (dokumen asli, sebelum flatten) | `bronze/mongodb/{dataset}/ingestion_date={date}/hour={hour}/` |

2. Tulis aturan penamaan file: `{dataset}_{extraction_timestamp}.{ext}`,
   contoh `orders_20260911T140500Z.parquet`.
3. Tulis aturan retention (berapa lama Bronze disimpan sebelum boleh
   dihapus â€” untuk portfolio scope, boleh tulis "disimpan permanen selama
   development, retention policy jadi catatan untuk production").

### Langkah 2.6 & 2.7 â€” Kontrak Silver & Gold

1. Tulis `docs/silver_contract.md`: untuk tiap staging model
   (`stg_indodax__pairs`, `stg_postgres__orders`, dst), daftar kolom output
   beserta tipe data dan aturan cleaning (mis. "harga harus > 0, baris yang
   melanggar di-drop dan dicatat di log").
2. Tulis `docs/gold_contract.md`: untuk `gold_market_daily`,
   `gold_trading_daily`, `gold_user_activity_daily`,
   `gold_crypto_business_metrics` â€” tentukan **grain** secara eksplisit
   (contoh: `gold_trading_daily` = 1 baris per kombinasi `date` + `symbol`),
   lalu daftar kolom dan cara hitungnya.

**Output:** `docs/bronze_contract.md`, `docs/silver_contract.md`,
`docs/gold_contract.md`.
**Verifikasi:** cek silang dengan `docs/requirements.md` â€” pastikan semua
kolom yang dibutuhkan untuk menjawab 6 business questions ada di kontrak
Gold.
**Status: â³**

---

## FASE 3 â€” Infrastruktur (Docker Compose)

**Tujuan:** database lokal jalan, reproducible dengan satu command.

1. `docker-compose.yml` (Postgres + MongoDB) â€” âœ… sudah dibuat.
2. `.env.example` â€” âœ… sudah dibuat.
3. Jalankan:
   ```
   cp .env.example .env
   docker compose up -d
   docker compose ps        # pastikan kedua container "healthy"
   ```
4. Verifikasi schema Postgres terbentuk:
   ```
   docker compose exec postgres psql -U <user> -d crypto_platform -c "\dt"
   ```
   Harus muncul 7 tabel.
5. Verifikasi collection MongoDB terbentuk:
   ```
   docker compose exec mongodb mongosh -u <user> -p --authenticationDatabase admin crypto_platform --eval "db.getCollectionNames()"
   ```
   Harus muncul `user_events`.
6. Isi data sintetis:
   ```
   python scripts/generate_synthetic_data.py --dsn "postgresql://<user>:<pass>@localhost:5432/crypto_platform" --num-users 500 --days 30 --seed 42
   python scripts/generate_mongo_events.py --pg-dsn "postgresql://<user>:<pass>@localhost:5432/crypto_platform" --mongo-uri "mongodb://<user>:<pass>@localhost:27017/?authSource=admin" --mongo-db crypto_platform --days 30 --seed 42
   ```

**Output:** Postgres & MongoDB jalan, berisi data sintetis konsisten.
**Verifikasi:** `SELECT COUNT(*) FROM orders;` di Postgres mengembalikan
angka > 0; `db.user_events.countDocuments()` di Mongo juga > 0.
**Status: ✅Infra jalan + data terisi (2026-09-13: postgres+mongodb+minio healthy, data sintetis + watermark awal ter-seed)**

---

## FASE 4 â€” Ingestion Layer (Extract)

**Tujuan:** extend layer extraction supaya bisa narik data dari 3 source,
dengan pola yang konsisten dengan `indodax_client.py` yang sudah ada.

1. Buka `indodax_client.py` yang sudah ada, catat pola yang dipakai: async,
   retry, struktur return data. Pola ini yang akan direplikasi.
2. Buat `src/ingestion/postgres_client.py`:
   - Pakai `asyncpg` untuk koneksi async.
   - Baca watermark dari tabel `etl_watermark` (`SELECT last_extracted_at
     FROM etl_watermark WHERE source_table = 'orders'`).
   - Query dengan filter: `WHERE updated_at > $1 ORDER BY updated_at`.
   - Return list of dict / DataFrame, konsisten dengan format return
     `indodax_client.py`.
3. Buat `src/ingestion/mongodb_client.py`:
   - Pakai `motor` (driver async MongoDB).
   - Query filter: `{"ingested_at": {"$gt": last_watermark}}`, sort
     ascending by `ingested_at`.
4. Tambahkan retry decorator (reuse dari `indodax_client.py` kalau ada,
   jangan tulis ulang) di kedua client baru.
5. Tambahkan logging terstruktur (bukan `print`): jumlah row diekstrak,
   watermark lama vs baru, durasi eksekusi.
6. Test manual (belum lewat Airflow): jalankan tiap client langsung dari
   script kecil (`python -c "..."` atau file test sementara), pastikan data
   yang keluar sesuai jumlah baris di database.

**Output:** `postgres_client.py`, `mongodb_client.py`, keduanya bisa
dipanggil dan mengembalikan data dengan benar.
**Verifikasi:** jumlah baris yang diekstrak = jumlah baris di database untuk
watermark awal (`1970-01-01`).
**Status: â³**

---

## FASE 5 â€” Bronze Layer (Load, Raw)

**Tujuan:** generalize Bronze writer supaya menerima source manapun.

1. Refactor `bronze/writer.py`: ubah jadi fungsi generic
   `write_bronze(dataset_name: str, source_type: str, payload, partition_cols)`.
   Pastikan pemanggilan lama untuk Indodax tetap jalan (backward
   compatible), cukup ubah cara manggilnya, bukan logicnya.
2. Terapkan strategi partisi sesuai `docs/bronze_contract.md`:
   `bronze/{source}/{dataset}/ingestion_date={date}/hour={hour}/`.
3. Tambahkan validasi ringan sebelum menulis: cek field wajib ada di setiap
   row/dokumen. Kalau tidak lengkap, log sebagai warning dan skip row itu
   (jangan gagalkan seluruh batch untuk satu row rusak).
4. Update `etl_watermark` di PostgreSQL **hanya setelah** Bronze write
   sukses dan tervalidasi.
5. Jalankan manual untuk ketiga source, cek file Bronze muncul dengan
   partisi yang benar.

**Output:** Bronze berisi data 3 source, partisi konsisten, watermark
terupdate dengan benar.
**Verifikasi:** `ls -R bronze/` menunjukkan struktur folder sesuai kontrak;
`SELECT * FROM etl_watermark;` menunjukkan timestamp terbaru.
**Status: â³**

---

## FASE 6 â€” Setup dbt Project

**Tujuan:** dbt bisa membaca Bronze sebagai source SQL.

1. Install dbt: `pip install dbt-duckdb dbt-databricks`
2. `dbt init dbt_crypto_platform` â€” pilih adapter `duckdb` untuk target
   pertama.
3. Buat `profiles.yml` (di luar folder project, biasanya
   `~/.dbt/profiles.yml`, atau lokal dan di-gitignore) dengan 2 target:
   ```yaml
   crypto_platform:
     target: dev
     outputs:
       dev:
         type: duckdb
         path: dev.duckdb
       prod:
         type: databricks
         host: "{{ env_var('DATABRICKS_HOST') }}"
         http_path: "{{ env_var('DATABRICKS_HTTP_PATH') }}"
         token: "{{ env_var('DATABRICKS_TOKEN') }}"
         schema: crypto_gold
   ```
4. Buat `models/staging/*/â€‹_sources.yml` per domain (`indodax`, `postgres`,
   `mongodb`), definisikan `external_location` menunjuk ke path Bronze.
5. Tambahkan `packages.yml`:
   ```yaml
   packages:
     - package: dbt-labs/dbt_utils
       version: [">=1.0.0", "<2.0.0"]
     - package: calogica/dbt_expectations
       version: [">=0.10.0", "<0.11.0"]
   ```
   lalu `dbt deps`.
6. Jalankan `dbt debug` â€” harus muncul "All checks passed!".

**Output:** dbt project ter-scaffold, `dbt debug` sukses.
**Verifikasi:** `dbt debug` tidak ada error koneksi.
**Status: â³**

---

## FASE 7 â€” dbt Staging Models

**Tujuan:** satu staging model per raw table/dataset, transformasi minimal.

1. Untuk tiap dataset Postgres, buat file `models/staging/postgres/stg_postgres__<nama>.sql`.
   Isinya: `select`, rename kolom kalau perlu, cast tipe eksplisit. **Tidak
   ada join atau agregasi di sini.**
2. Buat `stg_indodax__pairs.sql` dan `stg_indodax__summaries.sql` â€” parsing
   JSON mentah jadi kolom tabular.
3. Buat `stg_mongodb__user_events.sql` â€” flatten field `context` (yang
   bentuknya beda-beda per `event_type`) jadi kolom-kolom terpisah,
   menggunakan fungsi JSON dbt/DuckDB (`json_extract`).
4. Untuk tiap staging model, buat file `_<domain>__schema.yml` berisi test
   minimal: `not_null` dan `unique` untuk primary key, `accepted_values`
   untuk kolom enum (`status`, `side`, `event_type`, dst).
5. Jalankan:
   ```
   dbt run --select staging
   dbt test --select staging
   ```
   Semua harus lulus sebelum lanjut ke fase berikutnya.

**Output:** seluruh staging model + test lulus.
**Verifikasi:** `dbt test --select staging` keluar "PASS" untuk semua test.
**Status: â³**

---

## FASE 8 â€” dbt Intermediate Models

**Tujuan:** tempat join/enrich yang dipakai lebih dari satu Gold model.

1. `models/intermediate/int_orders_trades_joined.sql` â€” join
   `stg_postgres__orders` dengan `stg_postgres__trades`.
2. `models/intermediate/int_daily_market_snapshot.sql` â€” agregasi harian
   dari `stg_indodax__summaries`.
3. `models/intermediate/int_user_events_daily.sql` â€” agregasi
   `stg_mongodb__user_events` per user per hari.
4. Set materialization `ephemeral` di `dbt_project.yml` untuk folder
   `intermediate/`.
5. `dbt run --select intermediate`.

**Output:** model intermediate siap dipakai marts.
**Verifikasi:** `dbt run --select intermediate` sukses tanpa error.
**Status: â³**

---

## FASE 9 â€” dbt Marts (Gold Layer)

**Tujuan:** dataset business-ready, materialized sebagai tabel fisik.

1. `models/marts/market/gold_market_daily.sql` â€” materialization
   `incremental`, `unique_key=['date','symbol']`.
2. `models/marts/trading/gold_trading_daily.sql` â€” sama pola.
3. `models/marts/activity/gold_user_activity_daily.sql` â€” sama pola.
4. `models/marts/business/gold_crypto_business_metrics.sql` â€” join ketiga
   Gold di atas per `date` (+ `symbol` untuk market/trading).
5. Tulis `_*__schema.yml` lengkap untuk semua mart: `not_null`, range check
   (`dbt_expectations.expect_column_values_to_be_between`), deskripsi kolom.
6. `dbt run --select marts && dbt test --select marts`.

**Output:** 4 Gold table tervalidasi.
**Verifikasi:** query manual salah satu Gold table lewat `dbt show --select
gold_trading_daily`, cek angkanya masuk akal.
**Status: â³**

---

## FASE 10 â€” Business-Rule Testing (Singular Tests)

**Tujuan:** menangkap aturan bisnis yang tidak bisa diekspresikan generic
test.

1. `tests/assert_filled_qty_not_exceed_order_qty.sql` â€” query yang harus
   mengembalikan 0 baris kalau `filled_quantity > quantity`.
2. `tests/assert_account_balance_reconciles.sql` â€” reconciliation
   `accounts.balance` vs `SUM(transactions.amount)`.
3. `tests/assert_no_orphan_trades.sql` â€” setiap `trades.buy_order_id` /
   `sell_order_id` harus ada di `stg_postgres__orders`.
4. `dbt test --select test_type:singular`.

**Output:** business rule test lulus.
**Verifikasi:** `dbt test` keluar 0 failure.
**Status: â³**

---

## FASE 11 â€” Orchestration (Airflow, 3 DAG)

**Tujuan:** otomatisasi seluruh pipeline.

1. Tambahkan service Airflow ke `docker-compose.yml` (webserver, scheduler,
   Postgres metadata terpisah dari Postgres data â€” jangan pakai database
   yang sama).
2. `dags/crypto_ingestion.py`:
   TaskGroup paralel (`extract_indodax`, `extract_postgresql`,
   `extract_mongodb`) â†’ `write_bronze`. Deklarasikan `outlets=[bronze_dataset]`
   di task terakhir.
3. `dags/crypto_transformation.py`: `schedule=[bronze_dataset]` â†’
   `dbt_run_staging` (BashOperator: `dbt run --select staging`) â†’
   `dbt_test_staging` â†’ `dbt_run_intermediate` â†’ `dbt_run_marts` â†’
   `dbt_test_marts` â†’ `dbt_test_singular`. Task terakhir punya
   `outlets=[gold_dataset]`.
4. `dags/crypto_warehouse_load.py`: `schedule=[gold_dataset]` â†’
   `dbt run --target prod`.
5. Set retry policy: extraction 3x exponential backoff, dbt task 1x saja.
6. Test tiap DAG tanpa scheduler asli dulu:
   ```
   airflow dags test crypto_ingestion 2026-09-11
   airflow dags test crypto_transformation 2026-09-11
   ```

**Output:** 3 DAG jalan end-to-end.
**Verifikasi:** di Airflow UI, graph view menunjukkan semua task hijau.
**Status: â³**

---

## FASE 12 â€” Storage Migration (Local â†’ MinIO)

**Tujuan:** pindahkan Bronze fisik ke MinIO setelah logic stabil.

1. Tambahkan service `minio` ke `docker-compose.yml`.
2. Buat `src/storage/minio_client.py` (`boto3`), pertahankan pola atomic
   write (upload ke temp key â†’ copy/rename).
3. Update `bronze/writer.py`: pilih backend (local/MinIO) lewat config.
4. Update `sources.yml` dbt: `external_location` ganti ke `s3://bronze/...`.
5. Re-run DAG 1 & 2, bandingkan hasil dbt dengan sebelum migrasi â€” harus
   identik.

**Output:** Bronze fisik di MinIO.
**Verifikasi:** hasil query Gold table sebelum & sesudah migrasi sama
persis (regression check).
**Status: â³**

---

## FASE 13 â€” Databricks (Production Target)

**Tujuan:** buktikan model dbt yang sama jalan di target produksi.

1. Setup Databricks SQL Warehouse (community edition cukup).
2. Isi kredensial target `prod` lewat environment variable, bukan
   hardcoded di `profiles.yml`.
3. `dbt run --target prod --select staging` â†’ validasi koneksi ke
   MinIO/Databricks external location berhasil.
4. `dbt build --target prod` penuh.
5. Query salah satu Gold table dari Databricks SQL editor, screenshot untuk
   dokumentasi.

**Output:** Gold table ter-load di Databricks.
**Verifikasi:** query manual di Databricks SQL editor mengembalikan data.
**Status: â³**

---

## FASE 14 â€” Failure Testing

**Tujuan:** buktikan pipeline gagal dengan cara yang benar, bukan cuma
berhasil saat kondisi normal.

1. Matikan `docker compose stop postgres` saat DAG 1 jalan â€” cek extractor
   retry lalu fail gracefully, Bronze tidak tertulis parsial, watermark
   tidak maju.
2. Suntik data kotor manual (`UPDATE orders SET filled_quantity = quantity
   * 2 WHERE order_id = ...`) â€” cek dbt singular test menangkapnya.
3. Hapus satu file partisi Bronze manual â€” cek staging test/freshness
   check menandai data hilang.
4. Tulis hasil tiap skenario (apa yang terjadi, log yang muncul, cara
   recovery) ke `docs/failure_testing.md`.

**Output:** `docs/failure_testing.md`.
**Verifikasi:** baca ulang dokumen, pastikan tiap skenario ada bukti log.
**Status: â³**

---

## FASE 15 â€” CI (opsional)

**Tujuan:** validasi otomatis tiap ada perubahan kode.

1. `.github/workflows/ci.yml`: jalankan lint (`ruff`/`sqlfluff`) di setiap
   PR.
2. Workflow kedua: `dbt build --target ci` memakai DuckDB + fixture data
   kecil yang di-commit ke repo.
3. Tambahkan badge status CI di README.

**Output:** CI aktif di GitHub Actions.
**Verifikasi:** buka tab Actions di GitHub, pastikan run terakhir hijau.
**Status: â³**

---

## FASE 16 â€” Dokumentasi Final

**Tujuan:** paket portfolio yang bisa dipahami reviewer dalam < 5 menit.

1. `dbt docs generate && dbt docs serve` â€” screenshot lineage graph.
2. Tulis README utama: problem statement â†’ diagram arsitektur â†’ tech stack
   â†’ cara menjalankan (`docker compose up`, dst) â†’ business questions yang
   terjawab â†’ screenshot hasil query.
3. `docs/architecture.md`: jelaskan keputusan desain kunci (watermark,
   incremental, kenapa dbt, kenapa urutan storage migration di akhir).
4. Link `docs/failure_testing.md` dari README.
5. Diagram arsitektur final (satu gambar: source â†’ Bronze â†’ dbt â†’ warehouse
   â†’ BI).

**Output:** repo siap dibagikan sebagai portfolio.
**Verifikasi:** minta orang lain baca README saja (tanpa penjelasan
lisan), cek apakah mereka paham project ini ngapain dalam < 5 menit.
**Status: â³**

---

## Ringkasan Posisi Sekarang

```
FASE 0  â³  belum
FASE 1  â³  belum
FASE 2  ðŸŸ¡  2.1-2.4 selesai, 2.5-2.7 belum
FASE 3  ✅  infra jalan + data sintetis terisi (2026-09-13)
FASE 4  â³  belum
FASE 5  â³  belum
FASE 6  â³  belum
FASE 7  â³  belum
FASE 8  â³  belum
FASE 9  â³  belum
FASE 10 â³  belum
FASE 11 â³  belum
FASE 12 â³  belum
FASE 13 â³  belum
FASE 14 â³  belum
FASE 15 â³  belum (opsional)
FASE 16 â³  belum
```

**Langkah paling logis berikutnya:** selesaikan eksekusi Fase 3 di mesin
kamu sendiri (jalankan `docker compose up -d`, isi data sintetis), baru
lanjut ke Fase 2.5â€“2.7 (kontrak Bronze/Silver/Gold) atau langsung ke Fase 4
(ingestion layer) â€” dua-duanya bisa dikerjakan sebelum Fase 3 selesai
dijalankan di sisi kamu, karena sifatnya menulis kode/dokumen, bukan
bergantung pada database yang sudah hidup.
