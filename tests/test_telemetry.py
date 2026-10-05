import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "examples" / "python"))
from telemetry import Telemetry, guarded_context, redact
from smoke_trace import run_agent


class TelemetryTests(unittest.TestCase):
    def test_redacts_nested_credentials_and_email_without_mutating_input(self):
        source = {"api_key": "secret", "items": [{"Authorization": "Bearer abc", "answer": "contact user@example.com with sk-example123"}], "usage": 12}
        masked = redact(source)
        self.assertEqual(masked["api_key"], "[REDACTED]")
        self.assertEqual(masked["items"][0]["Authorization"], "[REDACTED]")
        self.assertNotIn("user@example.com", str(masked))
        self.assertNotIn("sk-example123", str(masked))
        self.assertEqual(masked["usage"], 12)
        self.assertEqual(source["api_key"], "secret")

    def test_agent_finishes_when_observation_creation_fails(self):
        client = Mock()
        client.start_as_current_observation.side_effect = RuntimeError("offline")
        result = run_agent(Telemetry(client), session_id="outage")
        self.assertEqual(result["answer"], "Deployment status: ready.")

    def test_update_and_cleanup_failures_do_not_change_result(self):
        context = Mock()
        observation = Mock()
        context.__enter__ = Mock(return_value=observation)
        context.__exit__ = Mock(side_effect=RuntimeError("cleanup failure"))
        observation.update.side_effect = RuntimeError("update failure")
        client = Mock()
        client.start_as_current_observation.return_value = context
        result = run_agent(Telemetry(client), session_id="update-error")
        self.assertEqual(result["answer"], "Deployment status: ready.")

    def test_business_exception_is_not_suppressed_by_instrumentation(self):
        context = Mock()
        context.__enter__ = Mock(return_value=None)
        context.__exit__ = Mock(return_value=True)
        with self.assertRaisesRegex(ValueError, "business error"):
            with guarded_context(lambda: context):
                raise ValueError("business error")
        self.assertEqual(context.__exit__.call_args.args[0], ValueError)

    def test_business_exception_survives_cleanup_failure(self):
        context = Mock()
        context.__enter__ = Mock(return_value=None)
        context.__exit__ = Mock(side_effect=RuntimeError("telemetry cleanup"))
        with self.assertRaisesRegex(ValueError, "business error"):
            with guarded_context(lambda: context):
                raise ValueError("business error")

    def test_disabled_telemetry_and_simulated_tool_error(self):
        result = run_agent(Telemetry.create(enabled=False), session_id="offline", simulate_tool_error=True)
        self.assertEqual(result["answer"], "Deployment status: unknown.")


class EnvInitializationTests(unittest.TestCase):
    def test_lan_configuration_preserves_secrets_and_uses_custom_ports(self):
        spec = importlib.util.spec_from_file_location("configure_lan", ROOT / "scripts" / "configure_lan.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / ".env"
            target.write_text("SALT=keep-me\nWEB_PORT=3001\nMINIO_PORT=9092\nNEXTAUTH_URL=http://localhost:3001\n", encoding="utf-8")
            module.configure("10.0.10.150", root)
            content = target.read_text(encoding="utf-8")
            self.assertIn("SALT=keep-me", content)
            self.assertIn("NEXTAUTH_URL=http://10.0.10.150:3001", content)
            self.assertIn("MEDIA_PUBLIC_URL=http://10.0.10.150:9092", content)
            with self.assertRaises(ValueError):
                module.configure("0.0.0.0", root)
            self.assertEqual(content, target.read_text(encoding="utf-8"))

    def test_secrets_generated_once_and_existing_env_preserved(self):
        spec = importlib.util.spec_from_file_location("init_env", ROOT / "scripts" / "init_env.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".env.example").write_text("SALT=__GENERATE__\nENCRYPTION_KEY=__GENERATE__\n", encoding="utf-8")
            self.assertTrue(module.initialize(root))
            original = (root / ".env").read_text(encoding="utf-8")
            values = dict(line.split("=", 1) for line in original.splitlines())
            self.assertRegex(values["ENCRYPTION_KEY"], r"^[0-9a-f]{64}$")
            self.assertNotEqual(values["SALT"], values["ENCRYPTION_KEY"])
            self.assertFalse(module.initialize(root))
            self.assertEqual(original, (root / ".env").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
