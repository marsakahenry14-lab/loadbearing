"""loadbearing: детерминированный анализатор несущий/сцена для attack graphs.

Ядро семантики зафиксировано спецификацией LBS v0.1. Пакет не обращается к сети
и не использует LLM — это чистый анализатор графа.
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
