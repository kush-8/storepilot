"""Real API/SQLite/graph for browser integration tests; only model adapters are offline."""

import os
from pathlib import Path
from tempfile import TemporaryDirectory

directory = TemporaryDirectory(prefix="storepilot-browser-")
os.environ["APPLICATION_DATABASE_PATH"] = str(Path(directory.name) / "application.db")
os.environ["JWT_SECRET"] = "browser-integration-test-key-0123456789abcdef"
os.environ["APP_ENV"] = "development"
os.environ["GROQ_API_KEY"] = ""

from app.dependencies import get_workflow  # noqa: E402
from app.main import app  # noqa: E402
from app.storage import ROOT  # noqa: E402
from tests.agent_fakes import offline_workflow  # noqa: E402

os.environ["DATABASE_PATH"] = str(ROOT / "database/retail.db")
runtime = offline_workflow(ROOT / "database/retail.db")
app.dependency_overrides[get_workflow] = lambda: runtime.workflow
