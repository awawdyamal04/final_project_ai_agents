"""Replay-time check for capture_claim (E-21, E-22): does the offline,
authoritative reconstruction agree with what was claimed and answered live?

D-41 augmented, not replaced (prd.md Sec 14.12): the live confirm/deny is
evidence, gathered under E-8/E-9's information boundary. This module turns
that evidence into a verdict, using the *same* recomputed ``TerminalResult``
the rest of :mod:`police_thief.replay.verifier` already produces -- no new
capture-detection logic here, only a comparison.

Findings, by construction:

* a claim the thief confirmed, matching the reconstruction -- agreement,
  no disagreement string;
* a claim the thief confirmed that the reconstruction contradicts -- a
  false cop claim colluded with by the thief, or a false confirmation;
* a claim the thief denied that the reconstruction shows was true -- a
  false thief denial (the live evidence E-21 exists to catch);
* a claim with no logged response in either log -- incomplete, reported the
  same way;
* a claim the thief answered ``audit_required`` (currently only ``landed``
  without a supplied ``movement``, E-8/E-9) -- never itself a disagreement,
  since it asserted nothing that could be false. Whether the claim was in
  fact true or false is still fully determined -- by ``terminal`` itself,
  the same independent reconstruction every other ground uses; a caller
  comparing the claim's ``claim_kind``/turn against ``terminal`` gets the
  authoritative answer even though this function reports no tampering.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from police_thief.audit.capture_claim_records import (
    find_claim_records,
    find_response_records,
)
from police_thief.domain.capture_claim import claim_kind_for_reason
from police_thief.domain.terminal import TerminalResult
from police_thief.protocol.capture_claim import (
    VERDICT_AUDIT_REQUIRED,
    VERDICT_CONFIRM,
    VERDICT_DENY,
)


def check_capture_claims(
    cop_records: Sequence[Mapping[str, Any]],
    thief_records: Sequence[Mapping[str, Any]],
    terminal: TerminalResult | None,
) -> list[str]:
    """Disagreement strings; empty if every logged claim/response checks out.

    Meant to be appended to the same ``ReplayVerdict.disagreements`` list the
    existing ``sub_game_end`` claimed-score check already populates -- a
    capture_claim disagreement is TAMPERED for exactly the same reason a
    score disagreement is: a peer's live account contradicts the
    independently recomputed truth.
    """
    claims = list(find_claim_records(cop_records)) + list(
        find_claim_records(thief_records)
    )
    responses = list(find_response_records(cop_records)) + list(
        find_response_records(thief_records)
    )
    responses_by_claim_id = {r["payload"]["claim_id"]: r for r in responses}

    disagreements: list[str] = []
    seen: set[str] = set()
    for record in claims:
        payload = record["payload"]
        claim_id = payload["claim_id"]
        if claim_id in seen:
            continue  # defensive: a claim logged in both peers' logs
        seen.add(claim_id)
        claim_turn = record["turn_number"]
        claim_kind = payload["claim_kind"]

        response = responses_by_claim_id.get(claim_id)
        if response is None:
            disagreements.append(
                f"capture_claim {claim_id}: claimed at turn {claim_turn} but "
                f"never answered in either log"
            )
            continue

        verdict = response["payload"]["verdict"]
        truly_captured = (
            terminal is not None
            and terminal.is_capture
            and terminal.turn == claim_turn
            and terminal.capture_reason is not None
            and claim_kind_for_reason(terminal.capture_reason) == claim_kind
        )

        if verdict == VERDICT_CONFIRM and not truly_captured:
            disagreements.append(
                f"capture_claim {claim_id}: thief confirmed {claim_kind!r} at "
                f"turn {claim_turn}, but the reconstruction disagrees"
            )
        elif verdict == VERDICT_DENY and truly_captured:
            disagreements.append(
                f"capture_claim {claim_id}: thief denied {claim_kind!r} at "
                f"turn {claim_turn}, but the reconstruction shows it was true"
            )
        elif verdict == VERDICT_AUDIT_REQUIRED:
            # Asserts nothing -- never a disagreement by itself. `terminal`
            # (compared against claim_kind/claim_turn the same way as above)
            # already carries the authoritative true/false answer for
            # whoever wants it; this function's job is only to catch lies.
            pass

    return disagreements
