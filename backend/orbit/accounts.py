"""Personal account storage, independent of the demo student catalog.

Run `python -m orbit.accounts` to create the additive personal workspace tables.
"""

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from . import database as db

_hasher = PasswordHasher()
# Unknown emails still perform a password verification.
_dummy_hash = _hasher.hash("unused-account-password")


class Registration(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: str = Field(min_length=3, max_length=254)
    name: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=12, max_length=1024, repr=False)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value):
        value = value.strip().lower()
        local, separator, domain = value.partition("@")
        if (
            not separator
            or not local
            or not domain
            or "@" in domain
            or any(char.isspace() for char in value)
        ):
            raise ValueError("Enter a valid email address")
        return value

    @field_validator("name")
    @classmethod
    def clean_name(cls, value):
        value = value.strip()
        if not value:
            raise ValueError("Enter your name")
        return value


class AccountExists(ValueError):
    pass


def prepare(engine):
    """Upgrade personal tables without importing demo records."""
    from .migrate import upgrade

    upgrade(engine)


def register(engine, registration: Registration):
    hashed = _hasher.hash(registration.password)
    try:
        with engine.begin() as conn:
            owner_id = conn.execute(
                db.owners.insert().values(
                    email=registration.email,
                    name=registration.name,
                    password_hash=hashed,
                )
            ).inserted_primary_key[0]
    except IntegrityError as exc:
        raise AccountExists("An account already uses this email") from exc
    return {"id": owner_id, "email": registration.email, "name": registration.name}


def authenticate(engine, email: str, password: str):
    with engine.connect() as conn:
        owner = (
            conn.execute(
                select(db.owners).where(db.owners.c.email == email.strip().lower())
            )
            .mappings()
            .one_or_none()
        )
    stored = owner["password_hash"] if owner else _dummy_hash
    try:
        _hasher.verify(stored, password)
    except (VerificationError, InvalidHashError):
        return None
    if owner is None:
        return None
    if _hasher.check_needs_rehash(stored):
        with engine.begin() as conn:
            conn.execute(
                db.owners.update()
                .where(
                    db.owners.c.id == owner["id"], db.owners.c.password_hash == stored
                )
                .values(password_hash=_hasher.hash(password))
            )
    return {key: owner[key] for key in ("id", "email", "name")}


if __name__ == "__main__":
    prepare(db.get_engine())
    print("Personal workspace tables are ready.")
