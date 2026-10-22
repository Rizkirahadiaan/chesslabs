"""Migrasi dengan akun pemilik, lalu beri hak minimum ke akun API."""
import os
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine
from .core.config import get_settings


def main():
    settings = get_settings()
    password = os.environ["CHESSLAB_RUNTIME_PASSWORD"]
    if len(password) < 32: raise ValueError("Kata sandi akun runtime minimal 32 karakter.")
    command.upgrade(Config("alembic.ini"), "head")
    engine = create_engine(settings.database_url, hide_parameters=True)
    from psycopg import sql
    with engine.begin() as connection:
        raw = connection.connection.driver_connection
        with raw.cursor() as cursor:
            cursor.execute("SELECT 1 FROM pg_roles WHERE rolname='chesslab_api'")
            exists = cursor.fetchone()
            statement = "ALTER ROLE chesslab_api WITH LOGIN PASSWORD {}" if exists else "CREATE ROLE chesslab_api WITH LOGIN PASSWORD {}"
            cursor.execute(sql.SQL(statement).format(sql.Literal(password)))
            cursor.execute("REVOKE CREATE ON SCHEMA public FROM PUBLIC")
            cursor.execute("GRANT USAGE ON SCHEMA public TO chesslab_api")
            cursor.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO chesslab_api")
            cursor.execute("REVOKE UPDATE, DELETE, TRUNCATE ON audit_logs, license_renewals FROM chesslab_api")
            cursor.execute("REVOKE INSERT, UPDATE, DELETE ON alembic_version FROM chesslab_api")
    engine.dispose()


if __name__ == "__main__": main()
