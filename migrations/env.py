from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, pool

from app.accounts.models import User  # noqa: F401
from app.bookmarklet.models import BookmarkletToken  # noqa: F401
from app.busy_blocks.models import BusyBlock  # noqa: F401
from app.core.config import get_settings
from app.core.database import Base
from app.google_calendar.models import (  # noqa: F401
    GoogleCalendar,
    GoogleCalendarEventState,
    GoogleOAuthToken,
)

config = context.config
settings = get_settings()
if config.config_file_name:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(url=settings.database_url, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = create_engine(settings.database_url, poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
