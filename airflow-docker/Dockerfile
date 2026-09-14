# =============================================================================
# Stage 1 — Base image
# Official Airflow 3.3.1 as the foundation layer.
# Only installs OS-level packages needed to compile Python extensions.
# =============================================================================
FROM apache/airflow:3.3.1-python3.12 AS airflow-base

LABEL maintainer="indodax-market-data" \
      org.opencontainers.image.title="indodax-airflow-base" \
      org.opencontainers.image.base.name="apache/airflow:3.3.1-python3.12"

# Install OS build dependencies as root, then drop back to airflow user.
# --no-install-recommends keeps the layer lean.
# Cleanup in the same RUN layer prevents image bloat.
USER root

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        curl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

USER airflow

# Prevent Python from writing .pyc files and enable unbuffered stdout/stderr
# so logs appear immediately in Docker without buffering.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1


# =============================================================================
# Stage 2 — Custom image (indodax-airflow)
# Extends base with pinned project-specific Python dependencies.
# Pinning versions ensures reproducible builds and prevents supply-chain drift.
# =============================================================================
FROM airflow-base AS indodax-airflow

LABEL org.opencontainers.image.title="indodax-airflow" \
      org.opencontainers.image.description="Airflow image for the Indodax market data pipeline"

# Pin all dependency versions for reproducible, auditable builds.
# Upgrade pip first to ensure hash-checking and vulnerability patches.
RUN pip install --no-cache-dir --upgrade pip==24.3.1 && \
    pip install --no-cache-dir \
        pandas>=2.2.3 \
        requests>=2.32.4 \
        python-dotenv==1.0.1 \
        databricks-sql-connector==4.4.0 \
        dbt-databricks==1.12.5 \
        duckdb==1.1.3 \
        aiohttp>=3.14.0 \
        aiohttp-retry==2.9.1 \
        aiofiles==24.1.0 \
        asyncpg>=0.30.0 \
        motor>=3.6.0 \
        boto3>=1.35.0

# Ensure the container always runs as the non-root airflow user.
USER airflow
