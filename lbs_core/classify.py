"""
Node classification: load-bearing (LB) / scaffolding (SC) / undetermined (UND),
and the search for minimal load-bearing sets (MLBS).

Semantics — the frozen LBS v0.1 core:
- §2 (N1): node n is LOAD-BEARING if no admissible substitution σ ⊆ Σ, not
  using n, restores holds(gamma) after n is removed.
- §3 (S1): node n is SCAFFOLDING if such a substitution exists (a witness σ
  is produced).
- §5: if the budget is exhausted before a full search, status → UND (NOT LB).
  Asymmetry rule: LB requires a full search (prove no substitution exists),
  SC requires a single witness.
- §9: an MLBS M is a set whose simultaneous removal breaks holds under every
  σ ⊆ Σ, and no proper subset of M has that property.
  An LB node = an MLBS of size 1; co-load-bearing = an MLBS of size >= 2.

Deterministic, no network, no LLM.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from itertools import combinations

from .graph import Hypergraph, Hyperedge, holds


class Label(str, Enum):
    LB = "LB"       # load-bearing
    SC = "SC"       # scaffolding
    UND = "UND"     # undetermined


@dataclass
class Substitution:
    """An admissible substitution from the Σ pool: a set of hyperedges introduced during a check.

    excludes_node — the node this substitution is NOT allowed to rely on
    (an alternative derivation that doesn't lean on the node under test).
    v0.1 §2/§3.
    """
    sid: str
    added_edges: list[Hyperedge]
    excludes_node: str | None = None


@dataclass
class NodeVerdict:
    node: str
    label: Label
    witness: str | None = None       # witness substitution's sid (for SC)
    reason: str | None = None        # reason (for LB/UND)


@dataclass
class Report:
    verdicts: dict[str, NodeVerdict]
    mlbs_sets: list[frozenset[str]]
    counts: dict[str, int]
    sigma_completeness: str
    budget_hit: bool                 # whether the budget was exhausted anywhere (=> UND exists)


def _replacement_restores(
    graph: Hypergraph,
    removed: set[str],
    sigma: list[Substitution],
    budget: int,
) -> tuple[bool, str | None, bool]:
    """Searches for a substitution σ ⊆ Σ (not using removed) that restores holds after
    removed is dropped.

    Returns (found, witness_sid, exhausted):
      found      — was a restoring substitution found (=> removed is dispensable => SC),
      witness_sid — the witness's identifier (the first substitution that worked),
      exhausted  — was the search FULLY completed (True) or cut off by budget (False).

    Subsets of applicable substitutions are enumerated. A substitution is
    considered applicable if its excludes_node doesn't fall in the removed
    set (a substitution must not rely on the nodes being removed). Order:
    the empty combination first (removal alone), then increasing combination
    size — a smaller witness is preferred.
    """
    base = graph.without_nodes(removed)
    if holds(base):
        # The goal is reachable even with no substitutions at all — removed
        # is trivially dispensable.
        return True, "∅", True

    # An applicable substitution must not rely on the removed nodes: neither
    # via the excludes_node marker, nor in fact (a removed node appearing in
    # its edges' tail/head). A substitution IS allowed to introduce NEW nodes
    # (an alternative sub-derivation through other premises).
    applicable = [
        s for s in sigma
        if not (set(removed) & {
            n for e in s.added_edges for n in (set(e.tail) | {e.head})
        })
    ]

    # If applicable substitutions exist but the budget doesn't cover even one
    # check, this is NOT a full search. removed cannot be declared
    # load-bearing (asymmetry rule §5.2/§5.3: "not checked" != "no
    # substitution exists"). Immediately UND.
    if applicable and budget <= 0:
        return False, None, False

    tried = 0
    # Enumerate combinations of substitutions in increasing size.
    for k in range(1, len(applicable) + 1):
        for combo in combinations(applicable, k):
            if tried >= budget:
                return False, None, False  # budget exhausted before a full search
            tried += 1
            added: list[Hyperedge] = []
            for s in combo:
                added.extend(s.added_edges)
            candidate = base.with_added_edges(added)
            if holds(candidate):
                sids = "+".join(s.sid for s in combo)
                return True, sids, True
    # The full search over every applicable substitution is complete, no
    # restoration found => load-bearing. (If applicable is empty, this is
    # also correct: no substitutions are available at all.)
    return False, None, True


def classify_nodes(
    graph: Hypergraph,
    sigma: list[Substitution] | None = None,
    budget: int = 10_000,
    sigma_completeness: str = "best_effort",
) -> dict[str, NodeVerdict]:
    """Single-node test over every node (v0.1 §4 step 3, §5).

    Source nodes and the goal itself are also classified (removing a source
    usually breaks the derivation => LB; this is correct). budget bounds the
    substitution search PER NODE.
    """
    sigma = sigma or []
    verdicts: dict[str, NodeVerdict] = {}

    for n in sorted(graph.nodes):
        found, witness, exhausted = _replacement_restores(graph, {n}, sigma, budget)
        if found:
            verdicts[n] = NodeVerdict(n, Label.SC, witness=witness)
        elif exhausted:
            # Full search, no substitution found => necessity proven => LB.
            note = "full_search_no_replacement"
            if sigma_completeness == "best_effort":
                note += "; LB_relative_to_incomplete_sigma"
            verdicts[n] = NodeVerdict(n, Label.LB, reason=note)
        else:
            # Budget exhausted before a full search => UND, NOT LB (rule §5.2/§5.3).
            verdicts[n] = NodeVerdict(n, Label.UND, reason="budget_exhausted")

    return verdicts


def find_mlbs(
    graph: Hypergraph,
    sigma: list[Substitution] | None = None,
    max_set_size: int = 3,
    budget: int = 10_000,
    single_verdicts: dict[str, NodeVerdict] | None = None,
) -> list[frozenset[str]]:
    """Search for minimal load-bearing sets (v0.1 §4 step 4, §9).

    Returns the minimal M (by inclusion) whose simultaneous removal breaks
    holds under every σ ⊆ Σ. Sets of size 1 (already-found LB nodes) are
    included; larger sets are checked only among nodes that are NOT singleton
    LB (otherwise the set wouldn't be minimal: its LB subset is already
    load-bearing).

    max_set_size bounds the combinatorial blowup (v0.1 E1): a full subset
    search is exponential, so the size is explicitly capped. budget applies
    to each candidate M checked.
    """
    sigma = sigma or []
    single = single_verdicts or classify_nodes(graph, sigma, budget)

    mlbs: list[frozenset[str]] = []

    # Size 1: load-bearing nodes are the singleton MLBS.
    lb_singletons = {n for n, v in single.items() if v.label == Label.LB}
    for n in lb_singletons:
        mlbs.append(frozenset({n}))

    # Sizes >= 2: only among nodes not covered by a singleton LB.
    # (If M contains an LB node, M isn't minimal.)
    candidates = sorted(n for n in graph.nodes if n not in lb_singletons)

    for size in range(2, max_set_size + 1):
        for combo in combinations(candidates, size):
            M = set(combo)
            # Minimality: no proper subset of M is already in mlbs.
            if any(existing < frozenset(M) for existing in mlbs):
                continue
            found, _, exhausted = _replacement_restores(graph, M, sigma, budget)
            # M is load-bearing <=> no substitution (found=False) under a full search (exhausted).
            if (not found) and exhausted:
                # Minimality check: removing any single element of M must
                # make the set dispensable (otherwise a subset is already
                # load-bearing and M isn't minimal).
                is_minimal = True
                for x in M:
                    sub = M - {x}
                    if not sub:
                        continue
                    sub_found, _, sub_exh = _replacement_restores(graph, sub, sigma, budget)
                    if (not sub_found) and sub_exh:
                        is_minimal = False  # the subset is also load-bearing
                        break
                if is_minimal:
                    mlbs.append(frozenset(M))

    return mlbs


def analyze(
    graph: Hypergraph,
    sigma: list[Substitution] | None = None,
    budget: int = 10_000,
    max_set_size: int = 3,
    sigma_completeness: str = "best_effort",
) -> Report:
    """Full run: single-node test + MLBS + aggregation (v0.1 §4).

    counts keeps UND as its own line; LB/SC proportions are NOT computed with
    UND in the denominator (v0.1 §5 step 5).
    """
    sigma = sigma or []
    verdicts = classify_nodes(graph, sigma, budget, sigma_completeness)
    mlbs = find_mlbs(graph, sigma, max_set_size, budget, single_verdicts=verdicts)

    counts = {Label.LB.value: 0, Label.SC.value: 0, Label.UND.value: 0}
    for v in verdicts.values():
        counts[v.label.value] += 1

    budget_hit = any(v.label == Label.UND for v in verdicts.values())

    return Report(
        verdicts=verdicts,
        mlbs_sets=mlbs,
        counts=counts,
        sigma_completeness=sigma_completeness,
        budget_hit=budget_hit,
    )
