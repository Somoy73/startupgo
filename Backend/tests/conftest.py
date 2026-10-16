import pytest
from fastapi.testclient import TestClient

from app.db import init_db


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db = tmp_path / "test.db"
    monkeypatch.setenv("STARTUPGO_DB", str(db))
    init_db(db)
    from app.main import app

    with TestClient(app) as c:
        yield c
