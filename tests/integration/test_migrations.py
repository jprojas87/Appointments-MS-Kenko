from alembic import command
from alembic.config import Config


def test_migrations_match_models(alembic_config: Config) -> None:
    """Falla si los modelos ORM y el esquema de las migraciones han divergido."""
    command.check(alembic_config)
