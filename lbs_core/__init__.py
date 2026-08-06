"""loadbearing: deterministic load-bearing/scaffolding analyzer for attack graphs.

The core semantics are fixed by the LBS v0.1 specification. The package makes
no network calls and uses no LLM — it's a pure graph analyzer.
"""

from .graph import Hypergraph, Hyperedge, holds
from .classify import (
    Label, Substitution, NodeVerdict, Report,
    classify_nodes, find_mlbs, analyze,
)
from .loader import Scenario, load_scenario
from .report import render_report

__version__ = "0.1.0"

__all__ = [
    "Hypergraph", "Hyperedge", "holds",
    "Label", "Substitution", "NodeVerdict", "Report",
    "classify_nodes", "find_mlbs", "analyze",
    "Scenario", "load_scenario",
    "render_report",
    "__version__",
]
