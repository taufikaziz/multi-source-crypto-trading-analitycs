# Ingestion Architecture Documentation (Phase 25)

## Overview
Modul ingestion bertanggung jawab mengekstraksi data secara asynchronous dan incremental dari tiga sumber berbeda:
1. **Indodax Public API** (HTTP async via `aiohttp`)
2. **PostgreSQL Transactional Database** (`asyncpg`)
3. **MongoDB Event Store** (`motor`)

## Concurrency & Retry Model
- **Async I/O Concurrency**: Menjalankan ekstraksi multi-source secara paralel menggunakan `asyncio.gather()`.
- **Shared Retry Policy (`src/ingestion/retry.py`)**:
  - Transient errors (HTTP 429, 5xx, socket timeout, connection reset): Retry maksimal 3 kali dengan exponential backoff bertahap (1s, 2s, 4s capped at 30s).
  - Non-transient errors (`ValueError`, `TypeError`, corrupt schema): Fail fast tanpa membakar kuota retry.

## Watermark & Safety
- **Tabel State**: `etl_watermark` pada database PostgreSQL.
- **Aturan Eksekusi**: `Extract` -> `Validate` -> `Write Bronze (MinIO)` -> `Verify` -> `Commit Watermark`.
- Jika terjadi kegagalan jaringan atau parsing sebelum data tersimpan di Bronze, watermark **tidak akan maju**, menjaga integritas data saat retry/backfill.
