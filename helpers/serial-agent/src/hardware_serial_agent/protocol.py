"""Versioned JSON Lines protocol primitives for the serial agent."""

import base64
import binascii
import json
from collections.abc import Mapping

PROTOCOL_VERSION = 1
MAX_JSON_LINE_BYTES = 1_048_576
MAX_PAYLOAD_BYTES = 262_144
MAX_READ_BYTES = 262_144
MAX_TIMEOUT_SECONDS = 120.0

type JsonValue = bool | int | float | str | list[JsonValue] | dict[str, JsonValue] | None
type Request = dict[str, JsonValue]
type Response = dict[str, JsonValue]


class AgentError(Exception):
    """Expected request or serial-operation failure returned to the caller."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def decode_request(line: bytes) -> Request:
    """Decode and validate one JSON object received from stdin."""
    try:
        value: object = json.loads(line)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise AgentError("invalid_json", "Request must be one valid JSON object") from error
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise AgentError("invalid_request", "Request must be a JSON object with string keys")
    return value


def encode_response(response: Response) -> bytes:
    """Encode one compact JSON response for stdout."""
    return f"{json.dumps(response, separators=(',', ':'))}\n".encode()


def success(**values: JsonValue) -> Response:
    """Create a successful protocol response."""
    return {"version": PROTOCOL_VERSION, "ok": True, **values}


def failure(error: AgentError) -> Response:
    """Create a stable structured error response."""
    return {
        "version": PROTOCOL_VERSION,
        "ok": False,
        "error": {"code": error.code, "message": str(error)},
    }


def validate_envelope(request: Request) -> str:
    """Validate common protocol fields and return the operation name."""
    if request.get("version") != PROTOCOL_VERSION:
        raise AgentError("unsupported_version", f"Supported protocol version is {PROTOCOL_VERSION}")
    operation = request.get("operation")
    if not isinstance(operation, str) or not operation:
        raise AgentError("invalid_request", "operation must be a non-empty string")
    return operation


def validate_fields(
    request: Request,
    *,
    required: set[str],
    optional: set[str] | None = None,
) -> None:
    """Reject missing and unexpected operation fields."""
    optional = optional or set()
    common = {"version", "operation"}
    missing = required - request.keys()
    if missing:
        names = ", ".join(sorted(missing))
        raise AgentError("invalid_request", f"Missing required fields: {names}")
    unexpected = request.keys() - required - optional - common
    if unexpected:
        names = ", ".join(sorted(unexpected))
        raise AgentError("invalid_request", f"Unexpected fields: {names}")


def require_string(request: Mapping[str, JsonValue], name: str) -> str:
    """Return a required non-empty string field."""
    value = request.get(name)
    if not isinstance(value, str) or not value:
        raise AgentError("invalid_request", f"{name} must be a non-empty string")
    return value


def require_int(
    request: Mapping[str, JsonValue],
    name: str,
    *,
    minimum: int,
    maximum: int,
) -> int:
    """Return a bounded integer field, excluding booleans."""
    value = request.get(name)
    if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
        raise AgentError(
            "invalid_request",
            f"{name} must be an integer between {minimum} and {maximum}",
        )
    return value


def require_timeout(request: Mapping[str, JsonValue]) -> float:
    """Return a bounded numeric timeout."""
    value = request.get("timeout")
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise AgentError("invalid_request", "timeout must be a number")
    timeout = float(value)
    if not 0 <= timeout <= MAX_TIMEOUT_SECONDS:
        raise AgentError(
            "invalid_request",
            f"timeout must be between 0 and {MAX_TIMEOUT_SECONDS}",
        )
    return timeout


def decode_payload(request: Mapping[str, JsonValue]) -> bytes:
    """Decode one bounded Base64 request payload."""
    encoded = require_string(request, "data")
    try:
        payload = base64.b64decode(encoded, validate=True)
    except (ValueError, binascii.Error) as error:
        raise AgentError("invalid_base64", "data must contain valid Base64") from error
    if len(payload) > MAX_PAYLOAD_BYTES:
        raise AgentError("payload_too_large", f"Decoded data exceeds {MAX_PAYLOAD_BYTES} bytes")
    return payload


def encode_payload(payload: bytes) -> str:
    """Encode serial bytes for a JSON response."""
    return base64.b64encode(payload).decode("ascii")
