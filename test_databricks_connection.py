import os

from databricks import sql
from dotenv import load_dotenv


load_dotenv()


def main():
    with sql.connect(
        server_hostname=os.getenv(
            "DATABRICKS_SERVER_HOSTNAME"
        ),
        http_path=os.getenv(
            "DATABRICKS_HTTP_PATH"
        ),
        auth_type="databricks-oauth",
    ) as connection:

        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT current_user(), current_catalog(), current_schema()"
            )

            result = cursor.fetchall()

            print(result)


if __name__ == "__main__":
    main()