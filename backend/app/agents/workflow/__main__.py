"""Standalone CLI; no API registration or HTTP server startup."""

import argparse
import json
import sys

from .service import create_workflow


def main() -> int:
    parser = argparse.ArgumentParser(description="StorePilot triage/router/RAG/data workflow")
    parser.add_argument("question")
    parser.add_argument("--employee-id", help="Trusted local caller ID for scoped case queries")
    args = parser.parse_args()
    try:
        result = create_workflow().ask(args.question, viewer_employee_id=args.employee_id)
        print(json.dumps(result.model_dump(mode="json"), indent=2))
        return 1 if result.status == "unavailable" else 0
    except Exception as exc:
        print(
            f"Workflow failed ({type(exc).__name__}). Check backend configuration and setup.",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
