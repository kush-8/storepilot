"""Standalone agents must work without importing API or persistence modules."""

import subprocess
import sys

from tests.support import BACKEND


def test_agents_import_and_run_without_api_database_or_model_runtime():
    script = """
import sys
from app.agents.guardrails import PIIAgent, SafetyAgent
result = PIIAgent().sanitize('One reader failed at ST003.')
assert SafetyAgent().evaluate(result).allowed
for name in ('app.main', 'app.copilot', 'app.storage', 'fastapi', 'sqlite3', 'openai'):
    assert name not in sys.modules, name
"""
    completed = subprocess.run(
        [sys.executable, "-c", script],
        cwd=BACKEND,
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
