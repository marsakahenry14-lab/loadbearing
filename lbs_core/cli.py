"""
CLI: load-bearing/scaffolding scenario analysis.

Usage:
    python -m lbs_core.cli examples/erc8183_evaluator_independence.json
    python -m lbs_core.cli scenario.json --json        # machine-readable output
    python -m lbs_core.cli scenario.json --budget 5000 --max-set-size 3
"""

from __future__ import annotations

import argparse
import json
import sys

from .loader import load_scenario
from .classify import analyze, Label
from .report import render_report

# Output contains non-ASCII characters (→, Σ); Windows consoles default to
# cp1252/cp866 and fail to encode them. Force stdout/stderr to UTF-8 whenever
# the interpreter allows it.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")


def _report_to_dict(scenario, report) -> dict:
    return {
        "title": scenario.title,
        "goal": scenario.graph.sink,
        "sigma_completeness": report.sigma_completeness,
        "verdicts": [
            {"node": n, "label": v.label.value,
             "witness": v.witness, "reason": v.reason}
            for n, v in sorted(report.verdicts.items())
        ],
        "mlbs_sets": [sorted(m) for m in report.mlbs_sets],
        "counts": report.counts,
        "budget_hit": report.budget_hit,
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="loadbearing",
        description="Deterministic load-bearing/scaffolding (LBS) analysis for attack graphs.",
    )
    p.add_argument("scenario", help="path to the JSON scenario (attack graph)")
    p.add_argument("--json", action="store_true", help="machine-readable output (JSON)")
    p.add_argument("--budget", type=int, default=10_000,
                   help="substitution search budget per node (default 10000)")
    p.add_argument("--max-set-size", type=int, default=3,
                   help="max size of MLBS sets checked (default 3)")
    args = p.parse_args(argv)

    try:
        scenario = load_scenario(args.scenario)
    except (OSError, ValueError) as e:
        print(f"Error loading scenario: {e}", file=sys.stderr)
        return 2

    report = analyze(
        scenario.graph,
        sigma=scenario.sigma,
        budget=args.budget,
        max_set_size=args.max_set_size,
        sigma_completeness=scenario.sigma_completeness,
    )

    if args.json:
        print(json.dumps(_report_to_dict(scenario, report),
                         ensure_ascii=False, indent=2))
    else:
        print(render_report(scenario, report))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
