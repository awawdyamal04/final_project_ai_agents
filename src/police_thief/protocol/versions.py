"""Protocol and schema versions, and the capability set.

The PDF prescribes no wire protocol at all -- it prescribes the *obligations* a
protocol must satisfy (E-11, E-17, E-26, E-27) and shows one illustrative
FastMCP tool (PDF p. 28). Everything here is therefore a project decision
(DECISIONS.md D-29) and must be agreed with each opponent before a match.
"""

from __future__ import annotations

SCHEMA_VERSION = "1.0"
"""Version of the envelope shape. A change here changes the key set."""

PROTOCOL_VERSION = "1.0"
"""Version of the message exchange. A change here changes the conversation."""

SOFTWARE_VERSION = "0.2.0"
"""Our build. Informational only -- peers may differ and still interoperate."""


CAP_HANDSHAKE = "handshake.v1"
"""Hello, config-hash exchange and readiness. Mandatory: without it there is no
way to establish that both peers loaded the same physics (E-11)."""

CAP_CANONICAL_JSON = "canonical-json.v1"
"""Canonical JSON with sorted keys and compact separators. Mandatory: both peers
must hash byte-identical input or every later audit fails (Ch. 5, PDF p. 50)."""

CAP_COMMIT_REVEAL = "commit-reveal.v1"
"""Reserved for Phase 5. Advertised as *not* supported yet, so a peer that has
implemented it can tell we have not."""

SUPPORTED_CAPABILITIES: frozenset[str] = frozenset(
    {CAP_HANDSHAKE, CAP_CANONICAL_JSON}
)

MANDATORY_CAPABILITIES: frozenset[str] = frozenset(
    {CAP_HANDSHAKE, CAP_CANONICAL_JSON}
)
"""Capabilities an opponent must advertise for us to agree to play.

Commit-reveal is deliberately absent: it is not implemented on either side yet,
and requiring it now would make every handshake fail. Phase 5 adds it to both
sets together.
"""


def is_protocol_compatible(theirs: str, ours: str = PROTOCOL_VERSION) -> bool:
    """Are two protocol versions compatible?

    Compatible when the **major** components match. Minor differences are
    assumed additive, which is the usual reading of a two-part version and the
    only one that lets a protocol evolve without a flag day between two teams
    who cannot deploy simultaneously.
    """
    try:
        theirs_major = theirs.split(".", 1)[0]
        ours_major = ours.split(".", 1)[0]
    except (AttributeError, IndexError):
        return False
    return bool(theirs_major) and theirs_major == ours_major


def is_schema_supported(theirs: str, ours: str = SCHEMA_VERSION) -> bool:
    """Envelope schemas must match exactly.

    Stricter than the protocol version on purpose: the envelope is a closed key
    set, so a different schema version means a different key set, and there is
    no safe way to guess which keys the other side omitted.
    """
    return theirs == ours
