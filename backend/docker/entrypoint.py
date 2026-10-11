"""Persist a signing key, explicitly prepare RAG, then replace this process with Uvicorn."""

import os
import secrets
import subprocess
import sys
from pathlib import Path


def prepare():
    state_directory = Path(
        os.getenv("APPLICATION_DATABASE_PATH", "/app/state/storepilot.db")
    ).parent
    state_directory.mkdir(parents=True, exist_ok=True)
    if not os.getenv("JWT_SECRET"):
        key_path = state_directory / "jwt-secret"
        if not key_path.exists():
            # Exclusive creation avoids replacing the signing key on subsequent starts.
            try:
                descriptor = os.open(key_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                with os.fdopen(descriptor, "w") as key_file:
                    key_file.write(secrets.token_urlsafe(48))
            except FileExistsError:
                pass
        os.environ["JWT_SECRET"] = key_path.read_text(encoding="utf-8").strip()
    if len(os.environ["JWT_SECRET"].encode()) < 32:
        raise ValueError("JWT_SECRET must contain at least 32 bytes")

    if os.getenv("STOREPILOT_INDEX_ON_START", "true").lower() == "true":
        # PolicyIndex.build is idempotent and rebuilds only when policy/configuration changes.
        result = subprocess.run([sys.executable, "-m", "app.agents.rag", "index"], check=False)
        if result.returncode:
            print(
                "Policy indexing failed. Serving login, guards and dashboard with degraded "
                "chat readiness; rerun indexing after fixing setup.",
                file=sys.stderr,
                flush=True,
            )


if __name__ == "__main__":
    prepare()
    command = sys.argv[1:] or ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
    os.execvp(command[0], command)
