from incident_agent.memory import IncidentMemory


def test_update_and_get():
    mem = IncidentMemory("INC-1")
    mem.update("severity", "P1")
    assert mem.get("severity") == "P1"
    assert mem.get("missing", "dflt") == "dflt"


def test_turn_log():
    mem = IncidentMemory("INC-1")
    mem.log_turn("triage", "severity_assigned", "P1")
    assert len(mem.turns) == 1
    assert mem.turns[0]["agent"] == "triage"


def test_checkpoint_restore_roundtrip(tmp_path):
    mem = IncidentMemory("INC-9")
    mem.update("severity", "P2")
    mem.log_turn("diagnosis", "hypothesis", "disk pressure")
    path = mem.checkpoint(tmp_path / "mem.json")
    assert path.exists()

    restored = IncidentMemory.restore(path)
    assert restored.incident_id == "INC-9"
    assert restored.get("severity") == "P2"
    assert restored.turns[0]["action"] == "hypothesis"
