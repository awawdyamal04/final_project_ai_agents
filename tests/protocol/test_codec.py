"""Wire codec: determinism, bounds, and refusal to deserialise anything odd."""

from __future__ import annotations

import json

import pytest

from police_thief.domain.enums import Role
from police_thief.protocol.codec import (
    MAX_PAYLOAD_BYTES,
    decode_envelope,
    encode_envelope,
    encode_envelope_text,
)
from police_thief.protocol.exceptions import (
    PayloadTooLargeError,
    ProtocolDecodeError,
)
from police_thief.protocol.messages import MessageType, new_envelope


def sample(**overrides):
    payload = {
        "peer_name": "team-a",
        "software_version": "0.2.0",
        "capabilities": ["handshake.v1", "canonical-json.v1"],
    }
    return new_envelope(
        game_id=overrides.get("game_id", "g1"),
        sender_role=Role.POLICE,
        receiver_role=Role.THIEF,
        message_type=MessageType.HELLO,
        payload=payload,
        message_id=overrides.get("message_id", "fixed-id"),
        timestamp="2026-07-28T00:00:00.000+00:00",
    )


def test_encoding_is_deterministic():
    first = encode_envelope(sample())
    for _ in range(20):
        assert encode_envelope(sample()) == first


def test_encoding_is_canonical_sorted_and_compact():
    text = encode_envelope_text(sample())
    assert text.startswith('{"game_id":')  # sorted keys put game_id first
    assert ", " not in text
    keys = list(json.loads(text))
    assert keys == sorted(keys)


def test_encoding_is_utf8():
    raw = encode_envelope(sample())
    assert isinstance(raw, bytes)
    assert raw.decode("utf-8")


def test_round_trip_preserves_every_field():
    original = sample()
    restored = decode_envelope(encode_envelope(original))
    assert restored.to_wire() == original.to_wire()


def test_decode_accepts_text_and_bytes():
    raw = encode_envelope(sample())
    assert decode_envelope(raw) == decode_envelope(raw.decode("utf-8"))


def test_malformed_json_is_rejected():
    with pytest.raises(ProtocolDecodeError, match="not valid JSON"):
        decode_envelope(b'{"schema_version": "1.0",,}')


def test_non_utf8_is_rejected():
    with pytest.raises(ProtocolDecodeError, match="not valid UTF-8"):
        decode_envelope(b"\xff\xfe\x00")


def test_non_object_json_is_rejected():
    from police_thief.protocol.exceptions import ProtocolValidationError

    with pytest.raises(ProtocolValidationError, match="must be an object"):
        decode_envelope(b"[1,2,3]")


def test_wrong_input_type_is_rejected():
    with pytest.raises(ProtocolDecodeError, match="expected bytes or str"):
        decode_envelope(12345)  # type: ignore[arg-type]


def test_oversized_message_is_rejected_before_parsing():
    """A bound that only applies after parsing is not a bound."""
    oversized = b"x" * (MAX_PAYLOAD_BYTES + 1)
    with pytest.raises(PayloadTooLargeError, match="over the"):
        decode_envelope(oversized)


def test_oversized_encode_is_rejected():
    envelope = new_envelope(
        game_id="g1",
        sender_role=Role.POLICE,
        receiver_role=Role.THIEF,
        message_type=MessageType.ERROR,
        payload={"code": "x", "detail": "y" * (MAX_PAYLOAD_BYTES + 10)},
    )
    with pytest.raises(PayloadTooLargeError):
        encode_envelope(envelope)


def _code_only(module) -> str:
    """Module source with docstrings and comments stripped.

    Scanning raw text would match the prose that *documents* the ban, so the
    check has to look at code.
    """
    import ast
    import io
    import tokenize
    from pathlib import Path

    source = Path(module.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef,
                             ast.AsyncFunctionDef)) and ast.get_docstring(node):
            node.body = node.body[1:] or [ast.Pass()]
    stripped = ast.unparse(tree)
    # Drop string literals too, so a docstring-like constant cannot match.
    return "".join(
        "" if tok.type == tokenize.STRING else tok.string
        for tok in tokenize.generate_tokens(io.StringIO(stripped).readline)
    )


def test_codec_does_not_deserialise_arbitrary_objects():
    """No pickle, no object hooks: the decoder only ever produces an Envelope."""
    import police_thief.protocol.codec as codec_module

    code = _code_only(codec_module)
    assert "pickle" not in code
    assert "eval(" not in code
    assert "object_hook" not in code


def test_codec_uses_the_single_canonical_implementation():
    """There must be exactly one canonical serialiser in the project."""
    import police_thief.protocol.codec as codec_module

    code = _code_only(codec_module)
    assert "canonical_json_bytes" in code
    assert "sort_keys" not in code  # not reimplemented here
