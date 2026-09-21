from alembic import context
from orbit import database as db


def migrate(connection):
    context.configure(connection=connection, target_metadata=db.metadata)
    with context.begin_transaction():
        context.run_migrations()


connection = context.config.attributes.get("connection")
if connection is not None:
    migrate(connection)
else:
    with db.get_engine().begin() as connection:
        migrate(connection)
