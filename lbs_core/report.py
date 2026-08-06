"""
Human-readable report of the analysis result.

The report is what the analyst reads. It must be honest about the method's
boundaries (v0.1): an SC verdict != "safe," it means "dispensable in this
scenario under this Σ"; LB is flagged when Σ is incomplete (risk of a false LB).
"""

from __future__ import annotations

from .classify import Report, Label
from .loader import Scenario


def render_report(scenario: Scenario, report: Report) -> str:
    txt = scenario.node_text
    lines: list[str] = []
    add = lines.append

    add("=" * 72)
    add(f"LBS analysis: {scenario.title}")
    add("=" * 72)
    add("")
    add(f"Goal (gamma): {scenario.graph.sink}")
    if scenario.graph.sink in txt:
        add(f"  {txt[scenario.graph.sink]}")
    add("")
    add(f"Σ completeness: {report.sigma_completeness}")
    if report.sigma_completeness == "best_effort":
        add("  NOTE: Σ is incomplete (best_effort). LB verdicts are conditional: a node")
        add("  is marked load-bearing because no substitution was found in the given Σ,")
        add("  not because none exists. Expanding Σ may turn LB -> SC.")
    add("")

    # --- Load-bearing ---
    lb = [n for n, v in report.verdicts.items() if v.label == Label.LB]
    add(f"LOAD-BEARING MECHANISMS (LB) — {len(lb)}:")
    add("  The goal is unreachable without any one of them. These are control points / countermeasure candidates.")
    for n in sorted(lb):
        add(f"  [LB] {n}")
        if n in txt:
            add(f"       {txt[n]}")
    add("")

    # --- Scaffolding ---
    sc = [n for n, v in report.verdicts.items() if v.label == Label.SC]
    add(f"SCAFFOLDING (SC) — {len(sc)}:")
    add("  Present, but individually dispensable: the goal is reachable without them.")
    add("  NOTE: SC does not mean 'safe' or 'useless' — it means 'in this scenario,")
    add("  under this Σ, removing this one node does not break the goal.' See MLBS below.")
    for n in sorted(sc):
        v = report.verdicts[n]
        wit = f"  (witness: {v.witness})" if v.witness else ""
        add(f"  [SC] {n}{wit}")
        if n in txt:
            add(f"       {txt[n]}")
    add("")

    # --- Undetermined ---
    und = [n for n, v in report.verdicts.items() if v.label == Label.UND]
    if und:
        add(f"UNDETERMINED (UND) — {len(und)}:")
        add("  The search budget was exhausted before completion. NOT classified as load-bearing.")
        add("  Needed: raise the budget, or reduce/restructure Σ.")
        for n in sorted(und):
            add(f"  [UND] {n}  ({report.verdicts[n].reason})")
        add("")

    # --- MLBS ---
    add("MINIMAL LOAD-BEARING SETS (MLBS):")
    add("  Each set is a minimal group whose simultaneous removal breaks the goal.")
    add("  Size 1 = a single load-bearing node. Size >= 2 = co-load-bearing:")
    add("  individually scaffolding, jointly necessary. Sets of size >= 2 show")
    add("  ALTERNATIVE paths: to close off the goal, knock out one node from each")
    add("  independent path.")
    singles = [m for m in report.mlbs_sets if len(m) == 1]
    multis = [m for m in report.mlbs_sets if len(m) >= 2]
    for m in sorted(singles, key=lambda s: sorted(s)):
        add(f"  {{{', '.join(sorted(m))}}}  (single load-bearing node)")
    for m in sorted(multis, key=lambda s: (len(s), sorted(s))):
        add(f"  {{{', '.join(sorted(m))}}}  (co-load-bearing, size {len(m)})")
    add("")

    # --- Summary ---
    add("-" * 72)
    c = report.counts
    add(f"Totals: LB={c['LB']}  SC={c['SC']}  UND={c['UND']}  |  MLBS={len(report.mlbs_sets)}")
    add("LB/SC proportions are computed without UND in the denominator (UND = not resolved within budget).")
    add("-" * 72)

    return "\n".join(lines)
