"""
Test configuration and fixtures for HealthBuddy-AI.
"""

import os
import warnings
import pytest
from fastapi.testclient import TestClient

warnings.filterwarnings(
    "ignore",
    message=r"builtin type SwigPyPacked has no __module__ attribute",
    category=DeprecationWarning,
)
warnings.filterwarnings(
    "ignore",
    message=r"builtin type SwigPyObject has no __module__ attribute",
    category=DeprecationWarning,
)

# Force a dedicated test database to prevent touching production/local data.
os.environ["DATABASE_URL"] = "sqlite:///./data/healthbuddy_test.db"
os.environ["GROQ_API_KEY"] = ""
os.environ["OPENAI_API_KEY"] = ""
os.environ["REDIS_URL"] = ""
os.environ["REQUIRE_TOS_ACCEPTANCE"] = "false"

from app.core.database import Base, engine, SessionLocal
from app.main import app


@pytest.fixture(scope="session", autouse=True)
def setup_database():
    """Create test database tables."""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)

    # Best-effort cleanup for local test DB file.
    try:
        os.remove("./data/healthbuddy_test.db")
    except OSError:
        pass


@pytest.fixture()
def client():
    """FastAPI test client."""
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture()
def db_session():
    """Database session for testing."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
