import pytest
from fastapi.testclient import TestClient

from app.db import init_db


@pytest.fixture()
def client(tmp_path, monkeypatch):
    """The API on a copy of DB/startupgo_unified.db: 8 scored startups (seed estimates), 30 to score, BlueInvest leads."""
    db = tmp_path / "test.db"
    monkeypatch.setenv("STARTUPGO_DB", str(db))
    init_db(db)
    from app.main import app

    with TestClient(app) as c:
        yield c
