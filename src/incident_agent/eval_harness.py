"""Evaluation harness: runs every labeled incident through the orchestrator
and scores the agents like you'd score a model.

Metrics:
- severity_accuracy: exact match on P1-P4
- root_cause_recall: fraction of expected keywords found in the diagnosis
- remediation_recall: fraction of expected action keywords found in the plan
- overall: weighted mean (0.4 / 0.35 / 0.25)
- pass: overall >= 0.70
Plus p50/p95 end-to-end latency across cases.
"""
from __future__ import annotations

import statistics
import time
from pathlib import Path

from .orchestrator import Orchestrator
from .providers import Provider
from .tools import load_incidents


def _recall(expected: list[str], text: str) -> float:
    if not expected:
        return 1.0
    text = text.lower()
    hits = sum(1 for kw in expected if kw.lower() in text)
    return hits / len(expected)


def score_case(case: dict, report) -> dict:
    labels = case["labels"]
    sev_ok = 1.0 if report.severity == labels["severity"] else 0.0
    cause_text = report.diagnosis.get("root_cause", "") + " " + \
        " ".join(report.diagnosis.get("evidence", []))
    cause_recall = _recall(labels.get("root_cause_keywords", []), cause_text)
    plan_text = " ".join(report.plan.get("steps", []))
    rem_recall = _recall(labels.get("remediation_keywords", []), plan_text)
    overall = 0.4 * sev_ok + 0.35 * cause_recall + 0.25 * rem_recall
    return {
        "id": case["id"],
        "severity_accuracy": sev_ok,
        "root_cause_recall": round(cause_recall, 3),
        "remediation_recall": round(rem_recall, 3),
        "overall": round(overall, 3),
        "pass": overall >= 0.70,
        "status": report.status,
    }


def evaluate(incidents_path: str | Path, runbook_dir: str | Path,
             provider: Provider, checkpoint_dir: str | Path | None = None) -> dict:
    cases = load_incidents(incidents_path)
    orch = Orchestrator(provider, cases, runbook_dir, checkpoint_dir=checkpoint_dir)
    results = []
    latencies = []
    for case in cases:
        start = time.time()
        report = orch.run(case["id"], case["service"], case["alert"])
        latencies.append(time.time() - start)
        results.append(score_case(case, report))
    latencies.sort()
    p50 = latencies[len(latencies) // 2]
    p95 = latencies[int(len(latencies) * 0.95) - 1] if len(latencies) > 1 else latencies[0]
    return {
        "n": len(results),
        "provider": provider.name,
        "severity_accuracy": round(sum(r["severity_accuracy"] for r in results) / len(results), 3),
        "root_cause_recall": round(sum(r["root_cause_recall"] for r in results) / len(results), 3),
        "remediation_recall": round(sum(r["remediation_recall"] for r in results) / len(results), 3),
        "overall": round(sum(r["overall"] for r in results) / len(results), 3),
        "pass_rate": round(sum(1 for r in results if r["pass"]) / len(results), 3),
        "latency_p50_s": round(p50, 3),
        "latency_p95_s": round(p95, 3),
        "cases": results,
    }


def write_report(results: dict, path: str | Path) -> Path:
    path = Path(path)
    lines = [
        "# eval report",
        "",
        f"provider: `{results['provider']}` — {results['n']} labeled incidents",
        "",
        "| metric | value |",
        "|---|---|",
        f"| severity accuracy | {results['severity_accuracy']} |",
        f"| root-cause recall | {results['root_cause_recall']} |",
        f"| remediation recall | {results['remediation_recall']} |",
        f"| **overall** | **{results['overall']}** |",
        f"| pass rate (>=0.70) | {results['pass_rate']} |",
        f"| latency p50 | {results['latency_p50_s']}s |",
        f"| latency p95 | {results['latency_p95_s']}s |",
        "",
        "| case | severity | cause recall | remediation recall | overall | pass | status |",
        "|---|---|---|---|---|---|---|",
    ]
    for c in results["cases"]:
        lines.append(f"| {c['id']} | {c['severity_accuracy']} | {c['root_cause_recall']} | "
                     f"{c['remediation_recall']} | {c['overall']} | "
                     f"{'yes' if c['pass'] else 'no'} | {c['status']} |")
    path.write_text("\n".join(lines) + "\n")
    return path
