import pytest
from orbit import accounts
from orbit import database as db
from pydantic import ValidationError
from sqlalchemy import create_engine, select


@pytest.fixture
def engine(tmp_path):
    engine = create_engine("sqlite:///" + (tmp_path / "accounts.db").as_posix())
    accounts.prepare(engine)
    yield engine
    engine.dispose()


def registration(**changes):
    return accounts.Registration(
        **{
            "email": "alice@example.com",
            "name": "Alice",
            "password": "a long password!",
            **changes,
        }
    )


def test_accounts_persist_and_credentials_are_isolated(engine):
    alice = accounts.register(engine, registration(email=" Alice@Example.com "))
    bob = accounts.register(
        engine,
        registration(
            email="bob@example.com", name="Bob", password="different password!"
        ),
    )
    engine.dispose()
    assert alice["id"] != bob["id"]
    assert (
        accounts.authenticate(engine, "ALICE@example.com", "a long password!") == alice
    )
    assert accounts.authenticate(engine, "bob@example.com", "a long password!") is None
    assert (
        accounts.authenticate(engine, "missing@example.com", "a long password!") is None
    )
    assert (
        accounts.authenticate(engine, "bob@example.com", "different password!") == bob
    )
    assert "password_hash" not in alice
    with engine.connect() as conn:
        hashes = conn.scalars(select(db.owners.c.password_hash)).all()
    assert all(value.startswith("$argon2id$") for value in hashes)


def test_duplicate_email_does_not_replace_account(engine):
    original = accounts.register(engine, registration())
    with pytest.raises(accounts.AccountExists):
        accounts.register(engine, registration(email="ALICE@example.com", name="Other"))
    assert (
        accounts.authenticate(engine, "alice@example.com", "a long password!")
        == original
    )
    accounts.prepare(engine)
    assert (
        accounts.authenticate(engine, "alice@example.com", "a long password!")
        == original
    )


@pytest.mark.parametrize(
    "changes",
    [
        {"email": "invalid"},
        {"email": "a@@b"},
        {"email": "a b@c"},
        {"name": "  "},
        {"password": "short"},
        {"owner_id": 42},
    ],
)
def test_invalid_registration(changes):
    with pytest.raises(ValidationError):
        registration(**changes)


def test_long_passwords_are_not_truncated(engine):
    password = "x" * 100
    accounts.register(engine, registration(password=password))
    assert accounts.authenticate(engine, "alice@example.com", password)
    assert accounts.authenticate(engine, "alice@example.com", "x" * 99 + "y") is None
