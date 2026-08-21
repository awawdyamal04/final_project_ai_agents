"""Cross-team interop identifiers (copthief-league-protocol kit, SPEC S4).

Optional, additive constructions used only if this peer ever negotiates a
match against an opponent outside this project's own two-repo submission.
**Nothing here is wired into the book-mandated handshake**
(``peer/orchestrator.py``'s ``config_sha256`` gate, PDF p.127) and nothing
here changes it: that gate hashes this peer's *whole* shared config and is
a book requirement (Appendix B) with its own signing question already
tracked as docs/OPEN_QUESTIONS.md Q-12. The interop kit's ``terms_signature``
is a *different* construction -- a nonce-signed hash over a flat, extracted
14-key subset of the negotiated terms -- required only for play against a
foreign implementation, and is not itself a book requirement.

Which of this project's own config keys correspond 1:1 to the kit's flat
14-key set (``board_size``, ``smell_grid_size``, ``decay_per_step``, ...) was
left unresolved here deliberately at first -- rather than guessed, per
CLAUDE.md's rule against fabricating an unresolved mapping. It is now
resolved: see ``interop/wire.py``'s ``terms_from_config``, built by reading
the kit's own ``sparring/config.py`` (``TERMS_KEYS``/``SparConfig.terms()``)
directly rather than inferring it, and docs/OPEN_QUESTIONS.md Q-21 point 3.
The functions below still take their ``terms`` mapping as a plain argument
rather than deriving it themselves, so this module stays agnostic to where
that mapping came from.
"""

from __future__ import annotations

import uuid
from typing import Any

from police_thief.config.canonical import canonical_json_text
from police_thief.config.hashing import pipe_nonce_commitment

__all__ = ["terms_signature", "game_uid", "game_id"]


def terms_signature(terms: dict[str, Any], nonce: str) -> str:
    """The pre-game agreement signature: the section-3 commit construction
    applied to the agreed ``terms`` instead of a turn payload."""
    return pipe_nonce_commitment(terms, nonce)


def game_uid(terms: dict[str, Any], group_a: str, group_b: str) -> str:
    """The deterministic shared match id both peers reproduce with no
    round-trip: ``UUID(SHA256(canonical(terms) + "|" + sorted(pair))[:16])``.

    Sorts the group-id pair so neither peer has to be told which name goes
    first -- a peer that names itself first instead produces a different id
    on each side of the same match.
    """
    import hashlib

    pair = sorted([group_a, group_b])
    seed = f"{canonical_json_text(terms)}|{'|'.join(pair)}"
    return str(uuid.UUID(bytes=hashlib.sha256(seed.encode("utf-8")).digest()[:16]))


def game_id(group_a: str, group_b: str) -> str:
    """The human-readable match id that names the four submission
    artifacts: ``"-vs-".join(sorted([group_a, group_b]))`` -- sorted, the
    same pair term as :func:`game_uid`, for the same reason."""
    return "-vs-".join(sorted([group_a, group_b]))
