import sqlite3
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_and_dashboard_use_database(monkeypatch):
    database = Path(__file__).resolve().parents[1] / "database/retail.db"
    monkeypatch.setenv("DATABASE_PATH", str(database))
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["total_rows"] == 2970
    response = client.get("/api/dashboard")
    assert response.status_code == 200
    data = response.json()
    with sqlite3.connect(database) as connection:
        expected = connection.execute(
            "SELECT COUNT(*) FROM support_cases WHERE status IN ('Open', 'In Progress') "
            "AND created_ts <= ?", ("2026-10-10 12:00:00",),
        ).fetchone()[0]
    assert data["unresolved_cases"] == expected
    for key in ("priority_distribution", "category_distribution", "region_distribution"):
        assert sum(row["count"] for row in data[key]) == expected


def test_missing_database_returns_unavailable_without_creating_file(tmp_path, monkeypatch):
    path = tmp_path / "missing.db"
    monkeypatch.setenv("DATABASE_PATH", str(path))
    assert client.get("/api/health").status_code == 503
    assert not path.exists()
