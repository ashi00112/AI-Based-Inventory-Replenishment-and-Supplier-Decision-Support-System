import pytest
from sqlalchemy import create_engine, select, Integer, String, Boolean, DateTime
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.database.base import Base
from app.models.user import User, UserRole


@pytest.fixture(scope="function")
def in_memory_db():
    """
    Isolated in-memory SQLite database session fixture for testing ORM models
    without connecting to or altering the external cloud database.
    """
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    with Session(engine) as session:
        yield session
    Base.metadata.drop_all(bind=engine)


def test_user_table_schema_definition():
    """
    Verify the User model table and column metadata against specifications.
    """
    table = User.__table__
    assert table.name == "users"

    col_names = {col.name: col for col in table.columns}
    expected_cols = {
        "id",
        "name",
        "email",
        "password_hash",
        "role",
        "is_active",
        "created_at",
        "updated_at",
    }
    assert expected_cols.issubset(col_names.keys())

    # Ensure no plain-text password column exists
    assert "password" not in col_names

    # Primary key and index verification
    id_col = col_names["id"]
    assert id_col.primary_key is True
    assert isinstance(id_col.type, Integer)

    # Name column
    name_col = col_names["name"]
    assert isinstance(name_col.type, String)
    assert name_col.nullable is False
    assert name_col.type.length == 100

    # Email column
    email_col = col_names["email"]
    assert isinstance(email_col.type, String)
    assert email_col.unique is True
    assert email_col.nullable is False
    assert email_col.type.length == 255

    # Password hash column
    pw_col = col_names["password_hash"]
    assert isinstance(pw_col.type, String)
    assert pw_col.nullable is False
    assert pw_col.type.length == 255

    # Role column
    role_col = col_names["role"]
    assert isinstance(role_col.type, String)
    assert role_col.nullable is False
    assert role_col.default.arg == "user"

    # Is active column
    active_col = col_names["is_active"]
    assert isinstance(active_col.type, Boolean)
    assert active_col.nullable is False
    assert active_col.default.arg is True

    # Timestamps
    created_at_col = col_names["created_at"]
    assert isinstance(created_at_col.type, DateTime)
    assert created_at_col.type.timezone is True
    assert created_at_col.nullable is False

    updated_at_col = col_names["updated_at"]
    assert isinstance(updated_at_col.type, DateTime)
    assert updated_at_col.type.timezone is True
    assert updated_at_col.nullable is False

    # Index checks
    indexed_columns = {
        col.name for index in table.indexes for col in index.columns
    }
    assert "id" in indexed_columns
    assert "email" in indexed_columns


def test_user_role_enum_values():
    """
    Ensure UserRole enum defines expected admin and user roles.
    """
    assert UserRole.ADMIN == "admin"
    assert UserRole.USER == "user"
    assert UserRole.ADMIN.value == "admin"
    assert UserRole.USER.value == "user"


def test_user_creation_with_defaults(in_memory_db: Session):
    """
    Test creating a user with defaults and verifying timestamp generation.
    """
    user = User(
        name="Jane Doe",
        email="jane.doe@example.com",
        password_hash="$2b$12$fakehashedpasswordstringforuserauth",
    )
    in_memory_db.add(user)
    in_memory_db.commit()
    in_memory_db.refresh(user)

    assert user.id is not None
    assert user.name == "Jane Doe"
    assert user.email == "jane.doe@example.com"
    assert user.role == "user"
    assert user.is_active is True
    assert user.created_at is not None
    assert user.updated_at is not None


def test_user_admin_creation(in_memory_db: Session):
    """
    Test creating a user with explicit admin role.
    """
    admin = User(
        name="Admin User",
        email="admin@example.com",
        password_hash="$2b$12$fakehashedpasswordstringforadmin",
        role=UserRole.ADMIN.value,
    )
    in_memory_db.add(admin)
    in_memory_db.commit()
    in_memory_db.refresh(admin)

    assert admin.id is not None
    assert admin.role == "admin"


def test_user_email_uniqueness_enforced(in_memory_db: Session):
    """
    Verify that duplicate email addresses violate the unique constraint.
    """
    user1 = User(
        name="User One",
        email="duplicate@example.com",
        password_hash="hash_1",
    )
    in_memory_db.add(user1)
    in_memory_db.commit()

    user2 = User(
        name="User Two",
        email="duplicate@example.com",
        password_hash="hash_2",
    )
    in_memory_db.add(user2)
    with pytest.raises(IntegrityError):
        in_memory_db.commit()
    in_memory_db.rollback()


def test_user_repr_does_not_leak_password_hash():
    """
    Verify that __repr__ does not reveal the password_hash.
    """
    user = User(
        id=1,
        name="Security Test",
        email="security@example.com",
        password_hash="super_secret_hash_value",
        role="user",
        is_active=True,
    )
    repr_str = repr(user)
    assert "super_secret_hash_value" not in repr_str
    assert "security@example.com" in repr_str
