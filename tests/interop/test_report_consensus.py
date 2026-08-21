"""Cross-team interop audit -- report canonicalization + consensus
signature (CORE, BLOCKER: "the emailed body must be the exact canonical
bytes... never a pretty-printed re-serialization" -- SPEC section 6, the
exact EX06 near-miss this project's own ``gmail_report.py`` was making
before this fix: ``json.dumps(report.to_email_dict(), indent=2)``).

Two separate things are audited here, and only the first exists in this
project's production code today:

1. **Report serialization is canonical bytes.** Fixed in
   ``reporting/gmail_report.py``'s ``_build_message`` -- now
   ``canonical_json_text``, not an indented re-serialization. Verified
   below both directly (no indentation/whitespace survives) and against the
   interop kit's own report vectors (this project's canonical serializer
   reproduces ``compact_form_sha256`` byte-for-byte on Hebrew-keyed, nested,
   float-bearing report bodies -- the same construction, independent of
   report schema).
2. **The mutual `consensus_signature` (a second, spaced-separator form,
   sign-then-insert)** has no production implementation in this project at
   all -- there is no two-team settlement-signing step to test yet. Left
   unimplemented rather than guessed; see docs/OPEN_QUESTIONS.md.
"""

from __future__ import annotations

import hashlib

from police_thief.config.canonical import canonical_json_bytes
from police_thief.reporting.gmail_report import _build_message
from tests.reporting._helpers import make_report

REPORT_VECTORS = [
    (
        {
            "קבוצה_א": "team-aleph", "קבוצה_ב": "team-bet",
            "תוצאה": {"מנצחת": "team-aleph", "ניקוד": [20, 5]},
            "game_uid": "f757f50d-d4f4-17e7-06cf-755905739b16",
            "tokens_total_series": 0, "github_commit": "abc1234",
        },
        "a87d61b5c1b7ea838a8e5fc7acc9f9004e28e50acb8c243431ab6ff78be33397",
    ),
    (
        {
            "סדרה": [
                {"משחקון": 1, "ניקוד": [5, 10]},
                {"משחקון": 2, "ניקוד": [20, 5]},
            ],
            "ram_gb": 31.8, "decay_per_step": 0.1, "mutual_agreement": True,
        },
        "4f9234b867116a1367245a65a0b18ff0f1390bea65f982e42576104321b6845b",
    ),
]


def test_canonical_bytes_reproduce_the_reference_compact_hash():
    """The section-2 form on Hebrew keys, nested lists and floats -- exactly
    the shape a real settlement report takes."""
    for report, expected in REPORT_VECTORS:
        assert hashlib.sha256(canonical_json_bytes(report)).hexdigest() == expected


def test_emailed_body_is_compact_canonical_bytes_not_pretty_printed():
    """Root-cause regression: the email body used to be
    ``json.dumps(..., indent=2)`` -- readable, but a different byte string
    from anything hashed under section 2, which is exactly the EX06 mistake
    the interop kit warns nearly scored a team 0."""
    report = make_report()
    message = _build_message(report, "results/league/g1.json", "team@example.com")
    import base64

    raw = base64.urlsafe_b64decode(message["raw"].encode("ascii"))
    text = raw.split(b"\n\n", 1)[1].decode("utf-8")  # past the MIME headers
    assert "\n" not in text.rstrip("\n")
    assert "  " not in text
    assert text == canonical_json_bytes(report.to_email_dict()).decode("utf-8")
