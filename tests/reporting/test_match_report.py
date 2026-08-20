"""Regression tests for the gmail_status reporting-consistency bug.

The bug: the email body was built from the JSON file on disk, which was
written *before* the send was attempted -- so a successfully sent email's
body could read ``"gmail_status": "not attempted"``. Fixed by never letting
``gmail_status`` reach the emailed payload at all (see
``MatchReport.to_email_dict``) and always finishing the local file with the
real, final status. See ``test_gmail_report.py`` for the send-side half.
"""

from __future__ import annotations

import json

from police_thief.reporting.match_report import write_report
from tests.reporting._helpers import make_report


def test_to_email_dict_never_carries_gmail_status():
    """Whatever ``gmail_status`` currently holds, the emailed payload must
    not contain it -- there is no truthful pre-send value for that field."""
    report = make_report(gmail_status="not attempted")
    payload = report.to_email_dict()
    assert "gmail_status" not in payload

    report.gmail_status = "sent"
    assert "gmail_status" not in report.to_email_dict()


def test_to_email_dict_keeps_every_other_field():
    report = make_report()
    payload = report.to_email_dict()
    full = report.to_dict()
    assert set(payload) == set(full) - {"gmail_status"}
    for key, value in payload.items():
        assert value == full[key]


def test_local_report_reaches_final_gmail_status_after_send():
    """The two-write pattern the runner uses: pre-send write, then a
    rewrite with the real outcome once the send attempt has finished."""
    report = make_report(gmail_status="not attempted")
    report_path = write_report(report)

    report.gmail_status = "sent"
    write_report(report)

    on_disk = json.loads(report_path.read_text(encoding="utf-8"))
    assert on_disk["gmail_status"] == "sent"


def test_local_report_survives_gmail_failure():
    """A failed send must never cost the locally persisted result -- the
    file must exist before the attempt and hold the real failure after it."""
    report = make_report(gmail_status="not attempted")
    report_path = write_report(report)
    assert report_path.exists()

    report.gmail_status = "EMAIL NOT SENT -- send failed: connection reset"
    write_report(report)

    on_disk = json.loads(report_path.read_text(encoding="utf-8"))
    assert on_disk["gmail_status"] == "EMAIL NOT SENT -- send failed: connection reset"
    assert on_disk["exit_status"] == "MATCH COMPLETE"


def test_local_report_survives_gmail_failure_before_any_status_update():
    """Even if the caller never gets to rewrite the file (crash between the
    send attempt and the second ``write_report``), the pre-send write already
    on disk is a truthful "not attempted" -- never a fabricated "sent"."""
    report = make_report(gmail_status="not attempted")
    report_path = write_report(report)
    on_disk = json.loads(report_path.read_text(encoding="utf-8"))
    assert on_disk["gmail_status"] == "not attempted"
