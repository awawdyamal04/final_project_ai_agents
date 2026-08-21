"""Phase H tasks A/D/#5: the negotiate/agreements channel must behave like
the kit's own -- a future round's greeting arriving early is preserved for
the round it actually belongs to, never dropped or misread as the round
currently being awaited -- and a series pins its opponent's identity after
the first handshake, refusing a different group that answers a later round.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from police_thief.config.loader import load_shared_config
from police_thief.interop.exceptions import Refused
from police_thief.interop.negotiation import Agreed, build_greeting, to_wire
from police_thief.interop.series_negotiate_v3 import negotiate_round
from police_thief.interop.series_v3 import run_series

REPO_ROOT = Path(__file__).resolve().parents[2]
SHARED_CONFIG_PATH = REPO_ROOT / "config" / "game.json"


def _cfg():
    return load_shared_config(SHARED_CONFIG_PATH)


@pytest.mark.asyncio
async def test_a_future_rounds_greeting_survives_into_its_own_round():
    """Tasks A/D: round 2's greeting sitting in the queue ahead of round
    1's must not be read as round 1's answer, and must still be there,
    unharmed, when round 2 itself asks."""
    cfg = _cfg()
    q: asyncio.Queue = asyncio.Queue()
    await q.put(to_wire(build_greeting(cfg, group_id="b", role="thief", sub_game_number=2)))
    await q.put(to_wire(build_greeting(cfg, group_id="b", role="thief", sub_game_number=1)))

    pending: dict = {}
    ours1 = build_greeting(cfg, group_id="a", role="police", sub_game_number=1)
    agreed1 = await negotiate_round(q, ours1, sub_game_number=1, timeout=2.0, pending=pending)
    assert agreed1.opponent_group == "b"
    assert 2 in pending  # preserved, not lost, while round 1 was being resolved

    ours2 = build_greeting(cfg, group_id="a", role="police", sub_game_number=2)
    agreed2 = await negotiate_round(q, ours2, sub_game_number=2, timeout=2.0, pending=pending)
    assert agreed2.opponent_group == "b"
    assert 2 not in pending  # consumed exactly once, from the stash, not the queue
    assert q.empty()


@pytest.mark.asyncio
async def test_a_same_round_bystander_is_not_fatal():
    """The kit's own ``handshake()`` behaviour: a same-round greeting that
    fails verification (role collision) does not abort the wait -- it keeps
    polling, bounded by the same budget, for the real counterpart."""
    cfg = _cfg()
    q: asyncio.Queue = asyncio.Queue()
    bystander = build_greeting(cfg, group_id="x", role="police", sub_game_number=1)  # role clash
    real = build_greeting(cfg, group_id="b", role="thief", sub_game_number=1)
    await q.put(to_wire(bystander))
    await q.put(to_wire(real))

    ours = build_greeting(cfg, group_id="a", role="police", sub_game_number=1)
    agreed = await negotiate_round(q, ours, sub_game_number=1, timeout=2.0, pending={})
    assert agreed.opponent_group == "b"


@pytest.mark.asyncio
async def test_handshake_budget_exhausted_raises_refused():
    cfg = _cfg()
    q: asyncio.Queue = asyncio.Queue()
    ours = build_greeting(cfg, group_id="a", role="police", sub_game_number=1)
    with pytest.raises(Refused) as exc:
        await negotiate_round(q, ours, sub_game_number=1, timeout=0.1, pending={})
    assert exc.value.code == "SPAR-N09"


@pytest.mark.asyncio
async def test_a_different_group_answering_a_later_round_refuses_the_series():
    """Task #5: one series, one opponent. A second round's greeting that
    verifies cleanly but names a DIFFERENT group than round 1's must refuse
    the series rather than silently mixing two opponents into one result."""
    agreed_round_1 = Agreed(game_id="g", game_uid="u", opponent_group="b",
                            opponent_role="thief", terms={})
    agreed_round_2 = Agreed(game_id="g", game_uid="u", opponent_group="INTRUDER",
                            opponent_role="police", terms={})

    class _State:
        group_id = "a"
        role_hint = "police"
        config = _cfg()
        sink = _NullSink()
        turn_q: asyncio.Queue = asyncio.Queue()
        audit_q: asyncio.Queue = asyncio.Queue()
        negotiate_q: asyncio.Queue = asyncio.Queue()
        session = None

    with (
        patch(
            "police_thief.interop.series_v3.negotiate_round",
            new=AsyncMock(side_effect=[agreed_round_1, agreed_round_2]),
        ),
        patch("police_thief.interop.series_v3.play_to_outcome", new=AsyncMock()),
        patch(
            "police_thief.interop.series_v3.await_matching_audit",
            new=AsyncMock(return_value=_verified_capture()),
        ),
    ):
        result = await run_series(_State(), outbound=None, timeout=1.0, sub_games=3)

    assert len(result.rows) == 1  # round 1 only -- round 2 refused before it was played
    assert result.refusal is not None
    assert "INTRUDER" in result.refusal
    assert result.settled is False


class _NullSink:
    def emit(self, *args, **kwargs) -> None:
        pass


def _verified_capture():
    from police_thief.interop.series_audit_v3 import AuditOutcome

    return AuditOutcome(remote_terminal="capture", audit_status="verified")
