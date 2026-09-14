from pathlib import Path

import duckdb


PROJECT_ROOT = Path(__file__).resolve().parents[2]

DATABASE_PATH = (
    PROJECT_ROOT
    / "data"
    / "warehouse"
    / "indodax.duckdb"
)


def get_connection() -> duckdb.DuckDBPyConnection:
    """
    Create and return a connection to the local
    Indodax DuckDB data warehouse.
    """

    DATABASE_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    return duckdb.connect(
        str(DATABASE_PATH)
    )