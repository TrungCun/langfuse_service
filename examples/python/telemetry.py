"""Best-effort telemetry; instrumentation must never replace business outcomes."""

from contextlib import contextmanager
import logging
import re
import sys

LOGGER = logging.getLogger(__name__)
SENSITIVE_KEYS = {
    "apikey", "secret", "secretkey", "password", "passwd", "token",
    "accesstoken", "refreshtoken", "authorization", "credentials",
    "email", "phone", "address", "cookie", "setcookie",
}


def redact(data, **_kwargs):
    """Example redaction; real systems should allow-list fields before tracing."""
    if isinstance(data, dict):
        return {
            key: "[REDACTED]"
            if re.sub(r"[^a-z0-9]", "", str(key).lower()) in SENSITIVE_KEYS
            else redact(value)
            for key, value in data.items()
        }
    if isinstance(data, (list, tuple)):
        return [redact(value) for value in data]
    if isinstance(data, str):
        value = re.sub(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", "[REDACTED]", data)
        value = re.sub(r"\bsk-[A-Za-z0-9_-]+", "[REDACTED]", value)
        value = re.sub(r"(?i)\bbearer\s+\S+", "Bearer [REDACTED]", value)
        return value
    return data


class SafeObservation:
    def __init__(self, observation=None):
        self.observation = observation

    def update(self, **attributes):
        if self.observation is not None:
            try:
                self.observation.update(**redact(attributes))
            except Exception:
                LOGGER.warning("Telemetry update failed; agent continues.")


@contextmanager
def guarded_context(factory):
    """Ignore telemetry enter/exit failures, preserve exceptions from the body."""
    context = None
    result = None
    try:
        if factory is not None:
            candidate = factory()
            result = candidate.__enter__()
            context = candidate
    except Exception:
        LOGGER.warning("Telemetry setup failed; agent continues.")
    try:
        yield result
    finally:
        if context is not None:
            exception_info = sys.exc_info()
            try:
                # Deliberately ignore its return value: business errors propagate.
                context.__exit__(*exception_info)
            except Exception:
                LOGGER.warning("Telemetry cleanup failed; agent outcome preserved.")


class Telemetry:
    def __init__(self, client=None, propagate=None):
        self.client = client
        self.propagate = propagate

    @classmethod
    def create(cls, *, enabled=True):
        if not enabled:
            return cls()
        try:
            from langfuse import Langfuse, propagate_attributes
            client = Langfuse(timeout=5, flush_at=32, flush_interval=2, mask=redact)
            return cls(client, propagate_attributes)
        except Exception:
            LOGGER.warning("Telemetry unavailable; agent continues without tracing.")
            return cls()

    @contextmanager
    def session(self, *, session_id, system):
        factory = None
        if self.propagate is not None:
            factory = lambda: self.propagate(
                session_id=session_id, tags=[system], metadata={"system": system}
            )
        with guarded_context(factory):
            yield

    @contextmanager
    def observation(self, *, name, as_type="span", **attributes):
        factory = None
        if self.client is not None:
            factory = lambda: self.client.start_as_current_observation(
                name=name, as_type=as_type, **redact(attributes)
            )
        with guarded_context(factory) as observation:
            yield SafeObservation(observation)

    def shutdown(self):
        if self.client is not None:
            try:
                self.client.flush()
                self.client.shutdown()
            except Exception:
                LOGGER.warning("Telemetry flush failed; buffered traces may be lost.")

