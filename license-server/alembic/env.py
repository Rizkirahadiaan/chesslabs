from alembic import context
from sqlalchemy import create_engine, pool
from app.core.config import get_settings
from app.db import Base
from app import models

config = context.config
url = config.attributes.get("database_url") or get_settings().database_url
if context.is_offline_mode():
    context.configure(url=url, target_metadata=Base.metadata, literal_binds=True, compare_type=True)
    with context.begin_transaction(): context.run_migrations()
else:
    engine = create_engine(url, poolclass=pool.NullPool, hide_parameters=True)
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=Base.metadata, compare_type=True)
        with context.begin_transaction(): context.run_migrations()
    engine.dispose()
