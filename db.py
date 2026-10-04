import os
import time

import pyodbc


def get_connection():
    connection_string = os.getenv("SQL_CONNECTION_STRING")

    if not connection_string:
        raise RuntimeError(
            "SQL_CONNECTION_STRING is not configured."
        )

    max_attempts = 4

    for attempt in range(1, max_attempts + 1):
        try:
            return pyodbc.connect(
                connection_string,
                timeout=60
            )

        except pyodbc.Error as exc:
            error_message = str(exc)

            # Azure SQL transient error:
            # 40613 = database temporarily unavailable
            if "40613" not in error_message:
                raise

            if attempt == max_attempts:
                raise

            wait_seconds = 10 * attempt

            print(
                f"Azure SQL is temporarily unavailable. "
                f"Retrying in {wait_seconds} seconds "
                f"(attempt {attempt}/{max_attempts})..."
            )

            time.sleep(wait_seconds)
