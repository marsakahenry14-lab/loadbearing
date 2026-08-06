"""
Load a scenario (attack graph) from JSON into core objects.

The input file format is simple and human-readable; it's the only format an
analyst edits by hand. Schema (all fields required except sigma):

{
  "title": "human-readable scenario name",
  "goal": "g",                       // target node (attack achieved / invariant broken)
  "nodes": {
     "g":  "the attacker completes the payout, bypassing the evaluator",
     "n1": "the evaluator and the executor share the same input channel",
     ...
  },
  "edges": [
     { "id": "e1", "tail": ["n1","n2"], "head": "g" },   // tail JOINTLY gives head
     ...
  ],
  "sigma": [                          // admissible substitutions (alternative sub-derivations); optional
     { "id": "s1", "excludes_node": "n1",
       "added_edges": [ { "id": "s1e1", "tail": ["n9"], "head": "g" } ] }
  ],
  "sigma_completeness": "best_effort" // enumerated | rule_closed | best_effort
}

Node texts are explanatory only (for the report); classification is driven
solely by structure (edges, sigma). This matches v0.1: the verdict is a
function of the graph, not of the wording.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from .graph import Hypergraph, Hyperedge
from .classify import Substitution


@dataclass
class Scenario:
    title: str
    graph: Hypergraph
    sigma: list[Substitution]
    sigma_completeness: str
    node_text: dict[str, str]        # id -> human-readable description (for the report)


def _parse_edge(raw: dict, ctx: str) -> Hyperedge:
    for key in ("id", "tail", "head"):
        if key not in raw:
            raise ValueError(f"{ctx}: edge is missing field {key!r}: {raw}")
    if not isinstance(raw["tail"], list) or not raw["tail"]:
        raise ValueError(f"{ctx}: tail of edge {raw['id']!r} must be a non-empty list")
    return Hyperedge(eid=str(raw["id"]),
                     tail=frozenset(str(t) for t in raw["tail"]),
                     head=str(raw["head"]))


def load_scenario(path: str | Path) -> Scenario:
    """Read and validate a scenario from a JSON file."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))

    for key in ("goal", "nodes", "edges"):
        if key not in data:
            raise ValueError(f"scenario is missing required field {key!r}")

    node_text: dict[str, str] = {str(k): str(v) for k, v in data["nodes"].items()}
    nodes = set(node_text.keys())
    goal = str(data["goal"])
    if goal not in nodes:
        raise ValueError(f"goal {goal!r} is missing from nodes")

    edges = [_parse_edge(e, "edges") for e in data["edges"]]

    sigma: list[Substitution] = []
    for s in data.get("sigma", []):
        if "id" not in s or "added_edges" not in s:
            raise ValueError(f"sigma substitution requires id and added_edges fields: {s}")
        added = [_parse_edge(e, f"sigma[{s['id']}]") for e in s["added_edges"]]
        sigma.append(Substitution(
            sid=str(s["id"]),
            added_edges=added,
            excludes_node=(str(s["excludes_node"]) if s.get("excludes_node") else None),
        ))

    graph = Hypergraph(nodes=nodes, edges=edges, sink=goal)
    completeness = str(data.get("sigma_completeness", "best_effort"))

    return Scenario(
        title=str(data.get("title", Path(path).stem)),
        graph=graph,
        sigma=sigma,
        sigma_completeness=completeness,
        node_text=node_text,
    )
