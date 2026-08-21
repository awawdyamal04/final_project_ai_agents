"""Cross-team interop audit -- canonical JSON (CORE).

Fixture values embedded from copthief-league-protocol
``vectors/canonical_json.json`` (external interop kit, not vendored code --
only its published data). Calls this project's OWN production
``canonical_json_text``/``canonical_json_bytes`` and compares the output to
the vector's expected bytes and digest. A mismatch here would fail every
other hash in the protocol, since everything else is built on this.
"""

from __future__ import annotations

import hashlib

import pytest

from police_thief.config.canonical import canonical_json_bytes, canonical_json_text

VECTORS = [
    (
        {"b": 1, "a": {"d": 4, "c": 3}},
        '{"a":{"c":3,"d":4},"b":1}',
        "943d56ce0b02b80a8afcd12d849426226b68f2d8cd2840af8f6f93067f14c360",
    ),
    (
        {"hint": "אני ליד הכיכר", "move": "MOVE:N"},
        '{"hint":"אני ליד הכיכר","move":"MOVE:N"}',
        "7461690c1167e6a4b44927a507e81aa38f290d9be8f662a1c0ea689d76b8bcc7",
    ),
    (
        {"emoji": "🙂", "x": 1},
        '{"emoji":"🙂","x":1}',
        "a16621d5cba0b8a1ce5909e74c0d2679295ae11eec4ccbf5f7e8550ecea3690d",
    ),
    (
        {
            "decay_per_step": 0.1, "emit_intensity": 0.9,
            "min_center_intensity": 0.5, "ram_gb": 31.8, "vram_gb": 6.0,
        },
        '{"decay_per_step":0.1,"emit_intensity":0.9,"min_center_intensity":0.5,'
        '"ram_gb":31.8,"vram_gb":6.0}',
        "62469a4afd756d527d881563440dbd82e2bc694cfd97516adacecb40a178483e",
    ),
    (
        {"a": True, "b": None, "c": [1, 2, 3]},
        '{"a":true,"b":null,"c":[1,2,3]}',
        "6e96c2da7b746f9e47d1bd8ee49e5e385de926c51e3a7f3fe9886ca02a29d351",
    ),
    (
        {"🙂": "astral key", "～": "high-BMP key"},
        '{"～":"high-BMP key","🙂":"astral key"}',
        "46193c64b2be01fac9662e4f211b64ff39a95d0c5f803b6971e4415186f3f146",
    ),
    (
        {"tiny": 1e-07, "huge": 1e16},
        '{"huge":1e+16,"tiny":1e-07}',
        "e4d847a30f5a6af84ea0b57471959195ad037f50a30f34534c1ee101e1b1cfc6",
    ),
]


@pytest.mark.parametrize(("obj", "expected_text", "expected_sha256"), VECTORS)
def test_canonical_text_matches_vector(obj, expected_text, expected_sha256):
    assert canonical_json_text(obj) == expected_text


@pytest.mark.parametrize(("obj", "expected_text", "expected_sha256"), VECTORS)
def test_canonical_sha256_matches_vector(obj, expected_text, expected_sha256):
    assert hashlib.sha256(canonical_json_bytes(obj)).hexdigest() == expected_sha256


def test_high_bmp_vs_astral_key_sort_is_by_code_point():
    """U+FF5E (~) sorts before U+1F642 (slightly smiling face) by Unicode
    CODE POINT -- a UTF-16 code-unit sort would order these the other way."""
    text = canonical_json_text({"🙂": "astral key", "～": "high-BMP key"})
    assert text.index('"～"') < text.index('"🙂"')
