"""Temporary databases and offline model collaborators for real API tests."""

import ipaddress
import shutil
import socket
import sqlite3

import pytest
from fastapi.testclient import TestClient

from app.dependencies import get_workflow
from app.main import app
from app.storage import state
from tests.agent_fakes import offline_workflow
from tests.support import BACKEND, EMPLOYEES, SIGNING_KEY, bearer


@pytest.fixture(autouse=True)
def no_external_network(monkeypatch):
    def denied(*args, **kwargs):
        raise AssertionError("External network is disabled in the deterministic test suite")

    original_connect = socket.socket.connect

    def local_socket_connect(sock, address):
        # Windows asyncio uses a loopback socket pair to wake its event loop.
        if isinstance(address, tuple):
            try:
                if ipaddress.ip_address(address[0]).is_loopback:
                    return original_connect(sock, address)
            except ValueError:
                pass
        elif sock.family == getattr(socket, "AF_UNIX", None):
            return original_connect(sock, address)
        return denied()

    monkeypatch.setattr(socket, "create_connection", denied)
    monkeypatch.setattr(socket.socket, "connect", local_socket_connect)


@pytest.fixture
def databases(tmp_path, monkeypatch):
    retail = tmp_path / "retail.db"
    application = tmp_path / "storepilot.db"
    shutil.copyfile(BACKEND / "database" / "retail.db", retail)
    with sqlite3.connect(retail) as connection:
        for level, employee in EMPLOYEES.items():
            connection.execute(
                "INSERT INTO employee_master VALUES (?, ?, ?, ?, ?)",
                (employee, f"Test employee {level}", f"Test role {level}", f"ST00{level}", level),
            )
    monkeypatch.setenv("DATABASE_PATH", str(retail))
    monkeypatch.setenv("APPLICATION_DATABASE_PATH", str(application))
    monkeypatch.setenv("JWT_SECRET", SIGNING_KEY)
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("GROQ_API_KEY", "")
    with state():
        pass
    return {"retail": retail, "application": application}


@pytest.fixture
def client(databases):
    runtime = offline_workflow(databases["retail"])
    original = app.dependency_overrides.copy()
    app.dependency_overrides[get_workflow] = lambda: runtime.workflow
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(original)


@pytest.fixture
def auth(databases):
    def headers(level=1, **options):
        return bearer(databases["application"], level, **options)

    return headers
