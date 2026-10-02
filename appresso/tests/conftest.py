"""Configuración global y fixtures para la suite de pruebas de VELUM."""
from __future__ import annotations

import sys
from pathlib import Path

# Garantizar que el directorio raíz del proyecto esté en sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.detector import detector
from app.main import app


# Base de datos en memoria para pruebas
TEST_DATABASE_URL = "sqlite:///:memory:"

test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, expire_on_commit=False, bind=test_engine)


@pytest.fixture(scope="function")
def db_session():
    """Crea una base de datos limpia en memoria para cada prueba."""
    Base.metadata.create_all(bind=test_engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=test_engine)


@pytest.fixture(scope="function")
def client(db_session):
    """Cliente de pruebas HTTP conectado a la sesión de prueba."""
    def override_get_db():
        session = TestingSessionLocal()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db

    # Limpiar ventanas en memoria del detector entre pruebas
    detector._windows.clear()
    detector._user_locks.clear()

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()
