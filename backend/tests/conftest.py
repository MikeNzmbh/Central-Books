import os

os.environ.setdefault("APP_ENV", "testing")
os.environ.setdefault("DATABASE_URL", "sqlite:///./test.db")
os.environ.setdefault("SEED_DEV_USER", "false")
os.environ.setdefault("COOKIE_SECURE", "false")
os.environ.setdefault("COOKIE_SAMESITE", "lax")

from fastapi.testclient import TestClient  # noqa: E402
import pytest  # noqa: E402

from app.db import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import User  # noqa: E402
from app.security import hash_password  # noqa: E402


def _reset_db() -> None:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        user = User(
            email="demo@cloverbooks.local",
            name="Demo User",
            password_hash=hash_password("changeme"),
            is_admin=True,
            role="superadmin",
        )
        db.add(user)
        db.commit()


_reset_db()


@pytest.fixture()
def client() -> TestClient:
    return TestClient(app)
