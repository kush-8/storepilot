"""Authenticated employee/location context and allowlisted policy citation resolution."""

from urllib.parse import quote

import pytest

from tests.support import EMPLOYEES, expect


def test_current_profile_comes_from_directory(client, auth):
    profile = expect(client.get("/api/me", headers=auth(2)), 200, "EmployeeContext")
    assert profile["employee_id"] == EMPLOYEES[2]
    assert profile["assigned_store_id"] == "ST002"
    assert profile["escalation_level"] == 2


def test_locations_include_store_and_warehouse_options(client, auth):
    result = expect(client.get("/api/stores", headers=auth(1)), 200, "StoreList")
    identifiers = {row["store_id"] for row in result["items"]}
    assert {"ST001", "ST003", "WH001"} <= identifiers
    assert len(identifiers) == len(result["items"])


@pytest.mark.parametrize(
    "filename",
    [
        "01_retail_operations_sop.md",
        "02_pos_pricing_returns_policy.md",
        "03_inventory_replenishment_policy.md",
        "04_vendor_quality_policy.md",
        "05_responsible_ai_policy.md",
    ],
)
def test_known_policy_section_returns_source_text_and_hash(client, auth, policies, filename):
    expected = next(s for s in policies.sections if s["filename"] == filename)
    result = expect(
        client.get("/api/policies/" + quote(expected["section_id"], safe=""), headers=auth(1)),
        200,
        "PolicySection",
    )
    for field in ("section_id", "filename", "heading", "source_hash"):
        assert result[field] == expected[field]
    assert result["body"].strip() == expected["body"].strip()


def test_unknown_policy_section_returns_safe_not_found(client, auth):
    result = expect(
        client.get("/api/policies/missing.md%23not-a-section", headers=auth(1)), 404, "Error"
    )
    assert "Traceback" not in str(result) and "C:\\Users" not in str(result)
