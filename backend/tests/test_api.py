"""Contract-facing readiness and protected dashboard regression tests."""

import hashlib

from tests.support import expect


def test_public_health_matches_contract_without_exposing_ticket_information(client):
    body = expect(client.get("/api/health"), 200, "Health")
    assert "employee" not in body and "tickets" not in body


def test_missing_source_database_is_unavailable_without_creating_it(
    databases, monkeypatch, tmp_path, request
):
    missing = tmp_path / "missing.db"
    monkeypatch.setenv("DATABASE_PATH", str(missing))
    client = request.getfixturevalue("client")
    expect(client.get("/api/health"), 503, "Health")
    assert not missing.exists()


def test_starter_dashboard_must_not_remain_public(client):
    expect(client.get("/api/dashboard"), 401, "Error")


def test_tests_leave_source_inputs_unchanged(client, fixture_hashes):
    client.get("/api/health")
    for path, digest in fixture_hashes.items():
        assert hashlib.sha256(path.read_bytes()).hexdigest() == digest
