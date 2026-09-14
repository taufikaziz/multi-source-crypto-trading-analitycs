from src.warehouse.schema import (
    create_warehouse_schema,
)


def main():
    create_warehouse_schema()

    print(
        "Data Warehouse schema created successfully."
    )


if __name__ == "__main__":
    main()