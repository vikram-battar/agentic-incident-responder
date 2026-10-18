import json

import pytest

from incident_agent.memory import IncidentMemory
from incident_agent.orchestrator import Orchestrator, _run_step
from incident_agent.tools import ToolError


def _orch(incidents, runbook_dir, provider, tmp_path):
    return Orchestrator(provider, incidents, runbook_dir,
                        checkpoint_dir=tmp_path / "ckpt")


def test_full_run_completed(incidents, runbook_dir, provider, tmp_path):
    orch = _orch(incidents, runbook_dir, provider, tmp_path)
    report = orch.run("INC-001", "payments-api",
                      "payments-api CrashLoopBackOff in prod-us-east, restart count 47 in 15m")
    assert report.status == "completed"
    assert report.severity == "P1"
    assert "oomkilled" in report.diagnosis["root_cause"].lower()
    assert report.plan["steps"]
    assert report.note
    assert len(report.timings) == 3
    # checkpoints were written for every step
    ckpts = list((tmp_path / "ckpt").glob("INC-001.*.json"))
    assert len(ckpts) == 3
    # and one of them restores cleanly
    mem = IncidentMemory.restore(tmp_path / "ckpt" / "INC-001.diagnose.json")
    assert mem.get("diagnosis")["root_cause"]


def test_high_risk_stops_at_approval_gate(incidents, runbook_dir, provider, tmp_path):
    orch = _orch(incidents, runbook_dir, provider, tmp_path)
    report = orch.run("INC-007", "orders-db",
                      "orders-db rejecting writes: too many connections")
    assert report.status == "awaiting_approval"
    assert report.plan["requires_approval"] is True


def test_run_step_retries_then_succeeds():
    calls = {"n": 0}

    def flaky():
        calls["n"] += 1
        if calls["n"] == 1:
            raise ToolError("transient")
        return "ok"

    timings = []
    assert _run_step(flaky, "demo", 2, timings) == "ok"
    assert timings[0]["attempts"] == 2


def test_run_step_gives_up():
    def always_fails():
        raise ToolError("down")

    with pytest.raises(ToolError):
        _run_step(always_fails, "demo", 1, [])


def test_failed_run_records_error(incidents, runbook_dir, provider, tmp_path):
    orch = _orch(incidents, runbook_dir, provider, tmp_path)
    report = orch.run("INC-X", "no-such-service", "something broke")
    assert report.status == "failed"
    assert report.error
