"""Run with python -m app.agents.rag; never starts an HTTP server."""

import argparse
import json
import sys

from . import IndexNotReadyError, PolicyIndex, RagSettings, create_rag_agent


def main() -> int:
    parser = argparse.ArgumentParser(description="Standalone StorePilot policy RAG")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("index", help="Index policies and download local embeddings if needed")
    for name in ("retrieve", "ask"):
        command = sub.add_parser(name)
        command.add_argument("question", help="Policy question (sanitized; no private data)")
    args = parser.parse_args()
    try:
        settings = RagSettings.from_env()
        if args.command == "index":
            payload = PolicyIndex(settings).build()
        elif args.command == "retrieve":
            payload = [item.model_dump() for item in PolicyIndex(settings).search(args.question)]
        else:
            result = create_rag_agent(settings).ask(args.question)
            # ASCII-safe JSON also works in Windows consoles with legacy encodings.
            print(json.dumps(result.model_dump(), indent=2))
            return 1 if result.status in {"invalid_response", "model_unavailable"} else 0
        print(json.dumps(payload, indent=2))
        return 0
    except IndexNotReadyError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except Exception as exc:
        # Configuration/provider errors may include secret values; print only a safe hint.
        print(
            f"RAG failed ({type(exc).__name__}). Check configuration, run the index command, "
            "and verify network/model availability. See backend/app/agents/rag/README.md.",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
