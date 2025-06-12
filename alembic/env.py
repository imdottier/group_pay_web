from logging.config import fileConfig
import os
from dotenv import load_dotenv

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

# Load environment variables
load_dotenv()

# --- START Cloud SQL Configuration ---
# Get DB credentials from environment variables
db_user = os.getenv("DB_USER")
db_password = os.getenv("DB_PASSWORD")
db_name = os.getenv("DB_NAME")
cloud_sql_connection_name = os.getenv("CLOUD_SQL_CONNECTION_NAME") # e.g. <project>:<region>:<instance>

db_url = None
# Check if all required environment variables for Cloud SQL are set
if all([db_user, db_password, db_name, cloud_sql_connection_name]):
    # Construct the Cloud SQL connection string for a Unix socket
    db_url = (
        f"mysql+pymysql://{db_user}:{db_password}@/{db_name}"
        f"?unix_socket=/cloudsql/{cloud_sql_connection_name}"
    )
else:
    # Fallback to the original URL from env var for local development or other environments
    db_url = os.getenv("SYNC_SQLALCHEMY_DATABASE_URL")
# --- END Cloud SQL Configuration ---


# Import your Base from your database setup
from backend.database import Base
# Import your models module so Base knows about the tables
import backend.models as models # Or specific models if preferred: from models import User, Item
# ---------------

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Override sqlalchemy.url with our constructed URL, if it exists
if db_url:
    config.set_main_option("sqlalchemy.url", db_url)
else:
    # Handle case where no database URL is available
    # This will likely cause an error downstream, but it's better to be explicit.
    print("\nERROR: Database URL not configured.\n"
          "Please set environment variables for Cloud SQL (DB_USER, DB_PASSWORD, DB_NAME, CLOUD_SQL_CONNECTION_NAME)\n"
          "or set SYNC_SQLALCHEMY_DATABASE_URL for other environments.\n")


# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
# from myapp import mymodel
# target_metadata = mymodel.Base.metadata
target_metadata = Base.metadata

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    # This simplified version uses the 'sqlalchemy.url' we already set in the config object
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
