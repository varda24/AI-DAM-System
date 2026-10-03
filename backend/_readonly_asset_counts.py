import re

from sqlalchemy import text

from app.core.database import engine


query = text(
    """
    SELECT current_database() AS database_name,
           current_schema() AS schema_name,
           COUNT(*) AS total_assets,
           COUNT(*) FILTER (WHERE source = 'local_pc') AS local_pc_count,
           COUNT(*) FILTER (WHERE source = 'google_drive') AS google_drive_count,
           COUNT(*) FILTER (
               WHERE source = 'local_pc' AND is_missing = FALSE
           ) AS local_pc_not_missing_count,
           COUNT(*) FILTER (
               WHERE source = 'google_drive'
                 AND source_account_id IS NOT NULL
                 AND source_file_id IS NOT NULL
           ) AS drive_with_account_and_file_id_count,
           COUNT(*) FILTER (
               WHERE source = 'google_drive'
                 AND path ~ '^[A-Za-z]:[/\\\\]'
           ) AS drive_windows_absolute_path_count
    FROM assets
    """
)

try:
    with engine.connect() as connection:
        result = connection.execute(query).mappings().one()
    for key, value in result.items():
        print(f"{key}={value}")
except Exception as error:
    message = re.sub(
        r"(?i)(postgres(?:ql)?(?:\+\w+)?://)[^@\s]+@",
        r"\1[REDACTED]@",
        str(error),
    )
    print(f"ERROR_TYPE={type(error).__name__}")
    print(f"ERROR={message}")
    raise SystemExit(1)