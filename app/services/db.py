import os


def get_database_url() -> str | None:
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        return None

    clean_url = database_url.strip()
    if not clean_url:
        return None

    return clean_url


def is_postgres_enabled() -> bool:
    database_url = get_database_url()
    if not database_url:
        return False

    return database_url.startswith(("postgres://", "postgresql://"))


def normalize_postgres_url(url: str) -> str:
    if url.startswith("postgres://"):
        return "postgresql://" + url[len("postgres://"):]

    return url


def get_storage_backend() -> str:
    if is_postgres_enabled():
        return "postgres"

    return "sqlite"


def get_postgres_connection():
    database_url = get_database_url()
    if not database_url:
        raise RuntimeError("DATABASE_URL is not set. PostgreSQL storage cannot be used.")

    try:
        import psycopg
        from psycopg.rows import dict_row
    except ImportError as error:
        raise RuntimeError(
            "PostgreSQL storage requires psycopg. Install dependencies from requirements.txt."
        ) from error

    try:
        return psycopg.connect(
            normalize_postgres_url(database_url),
            autocommit=True,
            row_factory=dict_row,
        )
    except Exception as error:
        raise RuntimeError("Could not connect to PostgreSQL using DATABASE_URL.") from error
