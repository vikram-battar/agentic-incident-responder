from incident_agent.eval_harness import _recall, evaluate, score_case, write_report


def test_recall():
    assert _recall(["a", "b"], "a and b here") == 1.0
    assert _recall(["a", "b"], "only a") == 0.5
    assert _recall([], "anything") == 1.0


def test_score_case_perfect():
    case = {"id": "X", "labels": {
        "severity": "P1",
        "root_cause_keywords": ["oomkilled"],
        "remediation_keywords": ["memory"],
    }}

    class R:
        severity = "P1"
        status = "completed"
        diagnosis = {"root_cause": "Container OOMKilled", "evidence": []}
        plan = {"steps": ["Increase the container memory limit"]}

    s = score_case(case, R())
    assert s["overall"] == 1.0
    assert s["pass"] is True


def test_score_case_wrong_severity():
    case = {"id": "X", "labels": {
        "severity": "P1",
        "root_cause_keywords": ["oomkilled"],
        "remediation_keywords": ["memory"],
    }}

    class R:
        severity = "P3"
        status = "completed"
        diagnosis = {"root_cause": "Container OOMKilled", "evidence": []}
        plan = {"steps": ["Increase the container memory limit"]}

    s = score_case(case, R())
    assert s["severity_accuracy"] == 0.0
    assert s["overall"] == round(0.35 + 0.25, 3)


def test_evaluate_end_to_end(provider, tmp_path):
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    results = evaluate(root / "data" / "incidents.json",
                       root / "data" / "runbooks", provider)
    assert results["n"] == 12
    assert results["overall"] >= 0.7, f"eval overall too low: {results}"
    assert results["pass_rate"] >= 0.8
    out = write_report(results, tmp_path / "report.md")
    assert out.exists()
