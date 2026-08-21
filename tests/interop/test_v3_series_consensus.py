"""Phase D: the machine-readable per-sub-game terminal-consensus struct
(``series_v3.SubGameRow``). Direct unit coverage of the struct itself --
the disagreement/agreement shapes it must represent -- rather than another
full two-peer live run (already covered end to end in
``test_v3_series.py``).
"""

from __future__ import annotations

from police_thief.interop.series_v3 import SeriesResult, SubGameRow


def test_row_marks_agreement_when_terminals_match():
    row = SubGameRow(
        sub_game_number=1, role="police", local_terminal="capture",
        remote_terminal="capture", audit_status="verified",
        agreement=("capture" == "capture"),
    )
    assert row.agreement is True


def test_row_marks_disagreement_when_terminals_differ():
    """The exact live shape this sprint set out to fix: our side settles
    ``capture`` while the opponent's own reported terminal was
    ``timeout``. The struct must surface this as ``agreement=False``, not
    silently prefer one side's view."""
    row = SubGameRow(
        sub_game_number=1, role="thief", local_terminal="capture",
        remote_terminal="timeout", audit_status="no_audit", agreement=False,
    )
    assert row.agreement is False
    assert row.local_terminal != row.remote_terminal


def test_row_represents_survival_terminal():
    row = SubGameRow(
        sub_game_number=2, role="thief", local_terminal="survival",
        remote_terminal="survival", audit_status="verified", agreement=True,
    )
    assert row.local_terminal == "survival"
    assert row.agreement is True


def test_row_represents_no_audit_as_its_own_status_not_a_failure():
    """A classified, zeroed sub-game (timeout on both sides) owes no
    reveal -- ``no_audit`` is a distinct, legitimate status, not folded
    into ``unverified`` (which means an audit arrived and failed)."""
    row = SubGameRow(
        sub_game_number=3, role="police", local_terminal="timeout",
        remote_terminal="timeout", audit_status="no_audit", agreement=True,
    )
    assert row.audit_status == "no_audit"
    assert row.agreement is True


def test_series_settled_requires_every_row_to_agree():
    rows = [
        SubGameRow(1, "police", "capture", "capture", "verified", True),
        SubGameRow(2, "thief", "capture", "timeout", "no_audit", False),
    ]
    result = SeriesResult(rows=rows, settled=(len(rows) == 2 and all(r.agreement for r in rows)))
    assert result.settled is False


def test_series_settled_true_only_when_all_rows_present_and_agree():
    rows = [SubGameRow(n, "police", "capture", "capture", "verified", True) for n in range(1, 7)]
    result = SeriesResult(rows=rows, settled=(len(rows) == 6 and all(r.agreement for r in rows)))
    assert result.settled is True
