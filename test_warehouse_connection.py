from src.warehouse.connection import (
    DATABASE_PATH,
    get_connection,
)


def main():
    connection = get_connection()

    result = connection.execute(
        "SELECT 'DuckDB warehouse connected' AS status"
    ).fetchone()

    print(result[0])

    connection.close()

    print(f"Database path: {DATABASE_PATH}")


if __name__ == "__main__":
    main()