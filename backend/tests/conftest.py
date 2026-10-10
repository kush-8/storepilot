"""Isolated databases and deterministic collaborators for tests only."""

from __future__ import annotations

import hashlib
import importlib
import ipaddress
import shutil
import socket
import sqlite3
from datetime import timedelta
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from tests.support import (
    BACKEND,
    EMPLOYEES,
    SIGNING_KEY,
    DataDouble,
    PolicyDouble,
    ScriptedModel,
    bearer,
    boundary,
    iso,
    utc_now,
)


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
    with sqlite3.connect(application) as connection:
        connection.executescript(
            (BACKEND / "tests" / "fixtures" / "application.sql").read_text(encoding="utf-8")
        )
        created = iso(utc_now() - timedelta(hours=1))
        for level, employee in EMPLOYEES.items():
            for state in ("Open", "Closed"):
                connection.execute(
                    """INSERT INTO tickets (
                      ticket_id, created_by_employee_id, creator_level_at_creation,
                      creator_role_at_creation, store_id, title, description, category, priority,
                      priority_provenance, confidence, status, review_required, approval_required,
                      approval_status, origin, policy_validation_status, created_at_utc,
                      updated_at_utc, closed_at_utc, version)
                      VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        f"SP-L{level}-{state.upper()}",
                        employee,
                        level,
                        f"Test role {level}",
                        f"ST00{level}",
                        f"L{level}_{state.upper()}_SENTINEL",
                        f"Level {level} {state.lower()} report",
                        "POS and Payments",
                        "P2" if state == "Open" else "P3",
                        "policy_validated",
                        0.9,
                        state,
                        0,
                        0,
                        "not_required",
                        "copilot",
                        "validated",
                        created,
                        created,
                        created if state == "Closed" else None,
                        1,
                    ),
                )
    monkeypatch.setenv("DATABASE_PATH", str(retail))
    monkeypatch.setenv("APPLICATION_DATABASE_PATH", str(application))
    monkeypatch.setenv("JWT_SIGNING_KEY", SIGNING_KEY)
    monkeypatch.setenv("JWT_ISSUER", "storepilot")
    monkeypatch.setenv("JWT_AUDIENCE", "storepilot-api")
    monkeypatch.setenv("JWT_EXPIRY_SECONDS", "1800")
    monkeypatch.setenv("OPENAI_API_KEY", "")
    monkeypatch.setenv("CHROMA_HOST", "network-disabled-in-tests.invalid")
    return {"retail": retail, "application": application}


@pytest.fixture
def model():
    return ScriptedModel()


@pytest.fixture
def policies():
    return PolicyDouble()


@pytest.fixture
def data_spy():
    return DataDouble()


@pytest.fixture
def workflow_factory(model, policies, data_spy):
    def build():
        factory = boundary("app.services.orchestrator", "build_workflow")
        return factory(model=model, retriever=policies, data=data_spy, clock=utc_now)

    return build


@pytest.fixture
def client(databases, model, policies, fixture_hashes):
    main = importlib.import_module("app.main")
    app = main.create_app() if hasattr(main, "create_app") else main.app
    # Future dependency seams inject collaborators only, never the behaviour being asserted.
    original = dict(app.dependency_overrides)
    try:
        dependencies = importlib.import_module("app.dependencies")
    except ModuleNotFoundError as exc:
        if exc.name != "app.dependencies":
            raise
    else:
        for name, value in (("get_model_adapter", model), ("get_policy_retriever", policies)):
            dependency = getattr(dependencies, name, None)
            if dependency is not None:
                app.dependency_overrides[dependency] = lambda value=value: value
    try:
        with TestClient(app, raise_server_exceptions=False) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(original)


@pytest.fixture
def auth(databases):
    def headers(level=1, **options):
        return bearer(databases["application"], level, **options)

    return headers


@pytest.fixture
def conversation(databases):
    def create(level=1):
        identifier = str(uuid4())
        created = iso(utc_now())
        with sqlite3.connect(databases["application"]) as connection:
            connection.execute(
                "INSERT INTO conversations VALUES (?, ?, ?, ?, ?, ?)",
                (identifier, EMPLOYEES[level], f"ST00{level}", created, created, 1),
            )
        return identifier

    return create


@pytest.fixture
def fixture_hashes():
    paths = [BACKEND / "database" / "retail.db"] + [
        p
        for folder in ("evaluation", "knowledge_base")
        for p in (BACKEND / folder).glob("*")
        if p.is_file()
    ]
    return {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
