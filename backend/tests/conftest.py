import os
from collections.abc import Generator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

os.environ["DATABASE_URL"] = "sqlite:///:memory:"

from app.core.database import Base


@pytest.fixture()
def db() -> Generator[Session, None, None]:
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    TestingSession = sessionmaker(bind=engine, future=True)
    Base.metadata.create_all(engine)
    session = TestingSession()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture(autouse=True)
def provisioned_models_are_explicit(monkeypatch):
    """Normal unit tests exercise missing-runtime fallbacks; opt in to real local weights."""
    if os.environ.get("PARAKH_TEST_MODELS") == "1":
        return
    from app.services import alias_model_service, embedding_service, local_llm, offline_models

    def unavailable(*args, **kwargs):
        raise offline_models.ModelUnavailable("Real model integration tests require PARAKH_TEST_MODELS=1")

    monkeypatch.setattr(local_llm, "model_card", unavailable)
    monkeypatch.setattr(embedding_service, "local_model", unavailable)
    monkeypatch.setattr(alias_model_service, "load_alias", unavailable)
