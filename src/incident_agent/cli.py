"""CLI: run one incident, or run the full eval suite."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .eval_harness import evaluate, write_report
from .orchestrator import Orchestrator
from .providers import MockProvider, OpenAICompatibleProvider
from .tools import load_incidents

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data" / "incidents.json"
RUNBOOKS = ROOT / "data" / "runbooks"


def _provider(use_mock: bool):
    return MockProvider() if use_mock else OpenAICompatibleProvider()


def cmd_run(args):
    orch = Orchestrator(_provider(args.mock), load_incidents(DATA), RUNBOOKS,
                        checkpoint_dir=ROOT / "checkpoints" if args.checkpoint else None)
    report = orch.run(args.id, args.service, args.alert)
    print(json.dumps({
        "incident": report.incident_id, "service": report.service,
        "severity": report.severity, "category": report.category,
        "status": report.status, "diagnosis": report.diagnosis,
        "plan": report.plan, "note": report.note,
        "timings": report.timings, "error": report.error,
    }, indent=2))


def cmd_eval(args):
    results = evaluate(DATA, RUNBOOKS, _provider(args.mock))
    out = write_report(results, ROOT / "eval_report.md")
    print(f"wrote {out}")
    print(json.dumps({k: v for k, v in results.items() if k != "cases"}, indent=2))


def main():
    ap = argparse.ArgumentParser(prog="incident-agent")
    sub = ap.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("run", help="run the agent on one incident")
    r.add_argument("--id", default="INC-MANUAL")
    r.add_argument("--service", required=True)
    r.add_argument("--alert", required=True)
    r.add_argument("--mock", action="store_true", default=True,
                   help="use the deterministic mock provider (default)")
    r.add_argument("--live-model", dest="mock", action="store_false",
                   help="use a real model via OPENAI_API_KEY")
    r.add_argument("--checkpoint", action="store_true")
    r.set_defaults(func=cmd_run)

    e = sub.add_parser("eval", help="run the labeled eval suite")
    e.add_argument("--mock", action="store_true", default=True)
    e.add_argument("--live-model", dest="mock", action="store_false")
    e.set_defaults(func=cmd_eval)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
