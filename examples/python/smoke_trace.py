"""Simulated agent/tool/LLM trace. No LLM credentials or paid API call required."""

import argparse
import json
import logging
import os
from pathlib import Path
import uuid

from telemetry import Telemetry


def run_agent(telemetry, *, session_id, simulate_tool_error=False):
    with telemetry.session(session_id=session_id, system="demo-agent"):
        with telemetry.observation(
            name="demo-agent.run", as_type="agent",
            input={"question": "What is the deployment status?", "email": "demo@example.com"},
            metadata={"system": "demo-agent", "simulated": True},
        ) as root:
            with telemetry.observation(name="plan", input={"task": "inspect status"}) as step:
                step.update(output={"next_tool": "deployment-status"})
            with telemetry.observation(name="deployment-status", as_type="tool") as tool:
                if simulate_tool_error:
                    tool.update(level="ERROR", status_message="Simulated tool timeout")
                    status = "unknown"
                else:
                    status = "ready"
                tool.update(output={"status": status, "api_key": "example-do-not-export"})
            with telemetry.observation(
                name="summarize", as_type="generation", model="demo-model",
                input=[{"role": "user", "content": "Summarize deployment status"}],
                metadata={"simulated": True},
            ) as generation:
                answer = f"Deployment status: {status}."
                generation.update(
                    output=answer,
                    usage_details={"input": 12, "output": 6},
                    cost_details={"input": 0.0, "output": 0.0},
                )
            result = {"answer": answer, "session_id": session_id}
            root.update(output=result)
            return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--offline", action="store_true", help="Disable telemetry; no SDK required")
    parser.add_argument("--check-auth", action="store_true", help="Fail early if SDK/project keys/server are unavailable")
    parser.add_argument("--simulate-tool-error", action="store_true")
    parser.add_argument("--session-id", default=None)
    args = parser.parse_args()
    if args.offline and args.check_auth:
        parser.error("--offline and --check-auth cannot be combined")
    logging.basicConfig(level=logging.WARNING)
    if not args.offline:
        try:
            from dotenv import load_dotenv
            load_dotenv(Path(__file__).with_name(".env"), override=False)
        except ImportError:
            parser.error("Install examples/python/requirements.txt, or use --offline")
        if not all(os.getenv(key) for key in ("LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY")):
            parser.error("Set project API keys in examples/python/.env, or use --offline")
        # Explicit local target: never silently fall back to Langfuse Cloud.
        os.environ.setdefault("LANGFUSE_BASE_URL", "http://localhost:3000")
    telemetry = Telemetry.create(enabled=not args.offline)
    try:
        if args.check_auth:
            try:
                authenticated = telemetry.client is not None and telemetry.client.auth_check()
            except Exception:
                authenticated = False
            if not authenticated:
                print("Auth check failed. Check project keys and Langfuse availability.")
                return 2
        result = run_agent(
            telemetry, session_id=args.session_id or f"demo-{uuid.uuid4().hex}",
            simulate_tool_error=args.simulate_tool_error,
        )
        print(json.dumps(result))
        print("Agent completed. Verify delivery in Langfuse UI; completion alone does not confirm ingestion.")
        return 0
    finally:
        telemetry.shutdown()


if __name__ == "__main__":
    raise SystemExit(main())
