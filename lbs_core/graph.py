"""
Inference hypergraph and the reachability predicate.

Semantics are fixed by the LBS v0.1 specification, section 9 (frozen core):
- Nodes V — atomic claims/steps.
- Hyperedge e = (tail, head): the set of premises tail is JOINTLY sufficient
  for head. An ordinary edge of a causal DAG is the special case of a
  hyperedge with |tail| == 1.
- Disjunction ("head is reachable via e1 OR e2") is expressed as several
  hyperedges sharing the same head.
- holds(gamma) == does a hyperpath exist from the sources (nodes with no
  incoming hyperedges, i.e. premises/axioms) to gamma, entirely within the
  current hypergraph.
- Removing a node n: drop n and ALL hyperedges where n appears in tail or is
  the head.

The module has no non-determinism and makes no network calls (a core
invariant).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable


@dataclass(frozen=True)
class Hyperedge:
    """Hyperedge: tail is JOINTLY sufficient for head.

    tail — an immutable set of node names (frozenset for hashability).
    head — a single node name.
    eid  — a stable hyperedge identifier (for logs and witnesses).
    """
    eid: str
    tail: frozenset[str]
    head: str

    def uses(self, node: str) -> bool:
        """True if the node participates in this hyperedge (in tail or as head)."""
        return node in self.tail or node == self.head


@dataclass
class Hypergraph:
    """An inference hypergraph with a single sink gamma.

    nodes  — the set of all nodes.
    edges  — the list of hyperedges.
    sink   — the target node gamma (single; spec assumption A7).
    """
    nodes: set[str]
    edges: list[Hyperedge]
    sink: str
    # Sources of the original graph. Set only on initial construction; when
    # deriving subgraphs (without_nodes / with_added_edges) they're carried
    # through unchanged, so holds() can distinguish "gamma is a premise" from
    # "gamma was orphaned."
    _original_sources: set[str] | None = field(default=None, repr=False)

    def __post_init__(self) -> None:
        # Validate structure on input — a cheap guard against a broken graph.
        # sink must be among the nodes ONLY on the initial graph
        # (_original_sources not yet set). In derived subgraphs the goal may
        # have been legitimately removed — then holds() honestly returns
        # False instead of raising.
        if self._original_sources is None and self.sink not in self.nodes:
            raise ValueError(f"sink {self.sink!r} is missing from nodes")
        for e in self.edges:
            missing = (set(e.tail) | {e.head}) - self.nodes
            if missing:
                raise ValueError(
                    f"hyperedge {e.eid!r} references unknown nodes: {sorted(missing)}"
                )
        # On initial construction, fix the sources as premises of the
        # original problem.
        if self._original_sources is None:
            heads = {e.head for e in self.edges}
            self._original_sources = {n for n in self.nodes if n not in heads}

    def sources(self) -> set[str]:
        """Sources: nodes that are not the head of any hyperedge (premises/axioms)."""
        heads = {e.head for e in self.edges}
        return {n for n in self.nodes if n not in heads}

    def original_sources(self) -> set[str]:
        """Sources of the ORIGINAL graph (premises fixed as such at construction time).

        Needed to distinguish "gamma was a premise" from "gamma ended up with
        no incoming edges after nodes were removed." In the second case the
        goal is NOT considered achieved: removing every edge that derives it
        must break holds. Fixed once when the graph is created."""
        return self._original_sources

    def __hash__(self):  # noqa: D401 - dataclass isn't frozen, hash by id for caching
        return id(self)

    def without_nodes(self, removed: Iterable[str]) -> "Hypergraph":
        """Return a copy of the graph without the given nodes and every incident hyperedge.

        Implements the removal operation from v0.1 §9: H ⊖ M.
        """
        removed_set = set(removed)
        new_nodes = self.nodes - removed_set
        new_edges = [e for e in self.edges if not any(e.uses(n) for n in removed_set)]
        # sink may be removed — then the graph loses its goal; holds() on it
        # returns False. Original sources are carried through unchanged
        # (minus the removed nodes).
        return Hypergraph(
            nodes=new_nodes,
            edges=new_edges,
            sink=self.sink,
            _original_sources=(self._original_sources or set()) - removed_set,
        )

    def with_added_edges(self, added: Iterable[Hyperedge]) -> "Hypergraph":
        """Return a copy of the graph with hyperedges added (applying a substitution from Σ)."""
        added_list = list(added)
        # Nodes appearing for the first time in the added edges are introduced
        # into the graph.
        extra_nodes: set[str] = set()
        for e in added_list:
            extra_nodes |= set(e.tail) | {e.head}
        all_edges = self.edges + added_list
        # New nodes that aren't the head of any edge are legitimate premises
        # of the alternative sub-derivation: register them as sources.
        heads = {e.head for e in all_edges}
        genuinely_new_sources = {n for n in extra_nodes if n not in heads}
        return Hypergraph(
            nodes=self.nodes | extra_nodes,
            edges=all_edges,
            sink=self.sink,
            _original_sources=(self._original_sources or set()) | genuinely_new_sources,
        )


def holds(graph: Hypergraph) -> bool:
    """Goal-reachability predicate: is gamma reachable from the sources via hyperpaths?

    Algorithm — bottom-up closure (forward chaining):
      derived := sources
      repeat: if a hyperedge's ENTIRE tail ⊆ derived, add head to derived
      until derived stops growing.
    gamma is reachable ⟺ gamma ∈ derived.

    Polynomial complexity: each pass is O(|E|), at most |V| passes.
    This is holds(H, gamma) from v0.1 §9 for kind="reachability".
    """
    if graph.sink not in graph.nodes:
        return False  # the goal was removed along with a node

    # A premise is a node that was a source IN THE ORIGINAL graph. A node
    # orphaned after all the edges deriving it are removed does NOT become a
    # premise — otherwise removing a load-bearing mechanism would falsely
    # "derive" the nodes that depend on it. This rule applies to ANY node
    # (not just the sink): an intermediate node that lost all its incoming
    # edges stops being reachable, it doesn't turn into an axiom.
    derived: set[str] = set(graph.original_sources()) & graph.nodes
    if graph.sink in derived:
        return True  # gamma really was a premise of the original problem

    changed = True
    while changed:
        changed = False
        for e in graph.edges:
            if e.head not in derived and e.tail <= derived:
                derived.add(e.head)
                changed = True
        if graph.sink in derived:
            return True
    return graph.sink in derived
