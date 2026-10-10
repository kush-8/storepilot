"""Validate the contract itself and future API response/request compatibility."""

import re

import pytest
from jsonschema import Draft202012Validator
from openapi_spec_validator import validate

from tests.support import SPEC, assert_schema


def test_openapi_document_conforms_to_31():
    validate(SPEC)


@pytest.mark.parametrize("name", sorted(SPEC["components"]["schemas"]))
def test_each_schema_is_valid_json_schema(name):
    Draft202012Validator.check_schema(SPEC["components"]["schemas"][name])


@pytest.mark.parametrize(
    "name,example",
    [
        (name, example)
        for name, schema in SPEC["components"]["schemas"].items()
        for example in schema.get("examples", [])
    ],
)
def test_contract_examples_match_their_schemas(name, example):
    assert_schema(example, name)


def test_path_parameters_security_and_operation_ids_are_consistent():
    operation_ids = []
    for path, path_item in SPEC["paths"].items():
        for method, operation in path_item.items():
            if method not in {"get", "post", "patch", "delete", "put"}:
                continue
            operation_ids.append(operation["operationId"])
            placeholders = set(re.findall(r"\{([^}]+)\}", path))
            parameters = {
                p["name"]
                for p in operation.get("parameters", [])
                if p["in"] == "path" and p.get("required")
            }
            assert placeholders == parameters
            security = operation.get("security", SPEC["security"])
            assert security == (
                [] if path in {"/api/health", "/api/auth/login"} else [{"BearerJWT": []}]
            )
    assert len(operation_ids) == len(set(operation_ids))
    assert not any("evaluation" in path for path in SPEC["paths"])


def test_required_api_operations_are_registered(client):
    implemented = {
        (path, method)
        for path, item in client.app.openapi()["paths"].items()
        for method in item
        if method in {"get", "post", "patch", "delete", "put"}
    }
    required = {(path, method) for path, item in SPEC["paths"].items() for method in item}
    assert required <= implemented, f"Missing API operations: {sorted(required - implemented)}"


@pytest.mark.parametrize(
    "schema,payload",
    [
        ("LoginRequest", {"employee_id": "E9001", "store_id": "ST001", "role": "Admin"}),
        (
            "TicketCreate",
            {
                "draft_id": "123e4567-e89b-42d3-a456-426614174000",
                "draft_revision": 1,
                "priority": "P4",
            },
        ),
    ],
)
def test_client_cannot_supply_authority_fields_in_contract(schema, payload):
    with pytest.raises(AssertionError):
        assert_schema(payload, schema)
