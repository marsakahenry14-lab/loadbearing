"""
Tests for loadbearing.

Each test in the "regression" group corresponds to a specific gap found while
implementing the frozen LBS v0.1 specification — a place where the spec text
was underdetermined and the code exposed it. These tests pin the closed
behavior.
"""

from lbs_core.graph import Hypergraph, Hyperedge, holds
from lbs_core.classify import analyze, classify_nodes, Substitution, Label


def _g(nodes, edges, sink):
    return Hypergraph(nodes=set(nodes),
                      edges=[Hyperedge(i, frozenset(t), h) for i, t, h in edges],
                      sink=sink)


# ---------- basic holds() semantics ----------

def test_conjunction_all_carrying():
    g = _g({"n1", "n2", "g"}, [("e1", {"n1", "n2"}, "g")], "g")
    assert holds(g)
    assert not holds(g.without_nodes(["n1"]))
    assert not holds(g.without_nodes(["n2"]))


def test_disjunction_alternative_paths():
    g = _g({"n1", "n2", "g"},
           [("e1", {"n1"}, "g"), ("e2", {"n2"}, "g")], "g")
    assert holds(g)
    assert holds(g.without_nodes(["n1"]))          # second path still lives
    assert not holds(g.without_nodes(["n1", "n2"]))  # both paths closed off


# ---------- regressions for spec gaps found during implementation ----------

def test_regression_orphaned_sink_not_a_premise():
    """Gap #1: removing every path to the goal left gamma with no incoming
    edges, and it was falsely treated as an achieved premise."""
    g = _g({"n1", "n2", "g"},
           [("e1", {"n1"}, "g"), ("e2", {"n2"}, "g")], "g")
    assert not holds(g.without_nodes(["n1", "n2"]))


def test_regression_removing_sink_returns_false_not_raises():
    """Gap #2: removing the sink itself crashed the validator instead of
    returning an honest False."""
    g = _g({"n1", "g"}, [("e1", {"n1"}, "g")], "g")
    assert holds(g.without_nodes(["g"])) is False


def test_regression_budget_zero_gives_und_not_lb():
    """Gap #3: budget=0 produced a false LB (an empty search counted as
    complete). Asymmetry rule: "not checked" != "no substitution exists"."""
    g = _g({"x", "g"}, [("e", {"x"}, "g")], "g")
    sub = Substitution("s1", [Hyperedge("e2", frozenset({"y"}), "g")], excludes_node="x")
    v = analyze(g, sigma=[sub], budget=0).verdicts["x"]
    assert v.label == Label.UND


def test_regression_substitution_may_introduce_new_nodes():
    """Gap #4+#5: a substitution couldn't introduce new nodes, and holds()
    didn't recognize new sources coming from substitutions. A substitution
    through a new node y makes x scaffolding."""
    g = _g({"x", "g"}, [("e", {"x"}, "g")], "g")
    sub = Substitution("s1", [Hyperedge("e2", frozenset({"y"}), "g")], excludes_node="x")
    v = analyze(g, sigma=[sub], budget=100).verdicts["x"]
    assert v.label == Label.SC
    assert v.witness == "s1"


def test_regression_orphaned_intermediate_node_not_a_premise():
    """Gap #6: an orphaned INTERMEDIATE node (not the sink) was falsely
    treated as a premise. Generalizes gap #1 to any derived node."""
    # m is derived from a; g is derived from m. Remove a => m is orphaned =>
    # g is unreachable.
    g = _g({"a", "m", "g"},
           [("e1", {"a"}, "m"), ("e2", {"m"}, "g")], "g")
    assert holds(g)
    assert not holds(g.without_nodes(["a"]))       # m orphaned, not a premise


# ---------- co-load-bearing (E1) ----------

def test_co_load_bearing_pair_detected():
    """Two nodes individually scaffolding, jointly load-bearing: the
    single-node test must label them SC, and the MLBS search must catch
    the pair."""
    g = _g({"a", "b", "g"},
           [("ea", {"a"}, "g"), ("eb", {"b"}, "g")], "g")
    rep = analyze(g, sigma=[], sigma_completeness="enumerated")
    assert rep.verdicts["a"].label == Label.SC
    assert rep.verdicts["b"].label == Label.SC
    assert frozenset({"a", "b"}) in rep.mlbs_sets


# ---------- integration: real example ----------

def test_erc8183_example_shape():
    """The real example classifies stably: 3 load-bearing nodes, decorative
    nodes as scaffolding, co-load-bearing sets found."""
    from pathlib import Path
    from lbs_core.loader import load_scenario
    path = Path(__file__).parent.parent / "examples" / "erc8183_evaluator_independence.json"
    sc = load_scenario(path)
    rep = analyze(sc.graph, sigma=sc.sigma, sigma_completeness=sc.sigma_completeness)
    # load-bearing core
    assert rep.verdicts["eval_output_trusted"].label == Label.LB
    assert rep.verdicts["eval_compromised"].label == Label.LB
    # decorative -> scaffolding
    assert rep.verdicts["cosmetic_audit_badge"].label == Label.SC
    assert rep.verdicts["verbose_logging"].label == Label.SC
    # a co-load-bearing set of size 2 exists
    assert any(len(m) == 2 for m in rep.mlbs_sets)


def test_potpie_case_shape():
    """Real case (cases/potpie-context-provenance): the load-bearing core is
    the missing trust field in the schema and the point where the claim is
    written; all 4 ingress + 7 egress channels are individually scaffolding
    (patching one doesn't break the attack while an alternative survives).
    See cases/potpie-context-provenance/WRITEUP.md and SOURCES.md."""
    from pathlib import Path
    from lbs_core.loader import load_scenario
    path = Path(__file__).parent.parent / "cases" / "potpie-context-provenance" / "scenario.json"
    sc = load_scenario(path)
    rep = analyze(sc.graph, sigma=sc.sigma, sigma_completeness=sc.sigma_completeness)
    assert rep.verdicts["schema_no_trust_field"].label == Label.LB
    assert rep.verdicts["claim_written"].label == Label.LB
    assert rep.counts[Label.LB.value] == 3       # goal + 2 root-cause nodes
    assert rep.counts[Label.SC.value] == 11       # 4 ingress + 7 egress (E-7 disproved & removed)
    assert rep.counts[Label.UND.value] == 0
    assert "e7_context_engine_api" not in sc.graph.nodes  # disproved at code level, see SOURCES.md


def test_erc8183_evaluator_integrity_case_shape():
    """Real case (cases/erc8183-evaluator-integrity): the load-bearing core is
    the whole chain from provider control over the deliverable through
    verdict_flipped (7 nodes, including the goal); the two downstream branches
    (escrow / reputation) are individually scaffolding but yield 4
    co-load-bearing pairs (crossing two independent paths) - the same
    structural signature as the synthetic examples/erc8183_evaluator_independence.json.
    See cases/erc8183-evaluator-integrity/WRITEUP.md and SOURCES.md."""
    from pathlib import Path
    from lbs_core.loader import load_scenario
    path = Path(__file__).parent.parent / "cases" / "erc8183-evaluator-integrity" / "scenario.json"
    sc = load_scenario(path)
    rep = analyze(sc.graph, sigma=sc.sigma, sigma_completeness=sc.sigma_completeness)
    assert rep.verdicts["channel_collapse_no_boundary"].label == Label.LB
    assert rep.verdicts["verdict_flipped"].label == Label.LB
    assert rep.verdicts["sink_atomic_no_dispute"].label == Label.SC
    assert rep.verdicts["reputation_write_on_complete"].label == Label.SC
    assert rep.counts[Label.LB.value] == 7
    assert rep.counts[Label.SC.value] == 4
    assert rep.counts[Label.UND.value] == 0
    pairs = [m for m in rep.mlbs_sets if len(m) == 2]
    assert len(pairs) == 4


def test_potpie_graphrag_case_shape():
    """Real case (cases/potpie-graphrag-prompt-injection): a strictly
    sequential chain (March 2026, pre-v2.0.0 Potpie) - all 6 nodes plus the
    goal classify as LB, no scaffolding at all. Control case: the tool
    doesn't invent structure where there is none. Model choice and the tool
    allowlist are deliberately NOT encoded as Sigma - see SOURCES.md.
    See cases/potpie-graphrag-prompt-injection/WRITEUP.md."""
    from pathlib import Path
    from lbs_core.loader import load_scenario
    path = Path(__file__).parent.parent / "cases" / "potpie-graphrag-prompt-injection" / "scenario.json"
    sc = load_scenario(path)
    rep = analyze(sc.graph, sigma=sc.sigma, sigma_completeness=sc.sigma_completeness)
    assert rep.verdicts["parsing_no_data_instruction_tag"].label == Label.LB
    assert rep.verdicts["injected_instruction_executed"].label == Label.LB
    assert rep.counts[Label.LB.value] == 7
    assert rep.counts[Label.SC.value] == 0
    assert rep.counts[Label.UND.value] == 0
    assert len(rep.mlbs_sets) == 7
    assert all(len(m) == 1 for m in rep.mlbs_sets)


def test_acp_node_v2_case_shape():
    """Real case (cases/acp-node-v2-evaluator-injection): an original finding
    (not a formalization of someone else's disclosure). A live chain in the
    current acp-node-v2 fork - a deliverable tagged role:"system" in the core
    SDK collapses into role:"user" in the shipped LLM examples, exactly when
    the evaluator gains access to complete()/reject(). All 6 nodes plus the
    goal are LB, no scaffolding (same shape as potpie-graphrag, but this
    chain is LIVE, not historical). See cases/acp-node-v2-evaluator-injection/WRITEUP.md
    and SOURCES.md (including the disclosure status section)."""
    from pathlib import Path
    from lbs_core.loader import load_scenario
    path = Path(__file__).parent.parent / "cases" / "acp-node-v2-evaluator-injection" / "scenario.json"
    sc = load_scenario(path)
    rep = analyze(sc.graph, sigma=sc.sigma, sigma_completeness=sc.sigma_completeness)
    assert rep.verdicts["deliverable_tagged_system_role"].label == Label.LB
    assert rep.verdicts["escrow_released_on_injected_verdict"].label == Label.LB
    assert rep.counts[Label.LB.value] == 7
    assert rep.counts[Label.SC.value] == 0
    assert rep.counts[Label.UND.value] == 0
    assert len(rep.mlbs_sets) == 7
