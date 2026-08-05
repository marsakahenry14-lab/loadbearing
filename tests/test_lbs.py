"""
Тесты loadbearing.

Каждый тест из группы "регрессия" соответствует конкретной дыре, найденной при
реализации замороженной спецификации LBS v0.1 — то есть месту, где текст спеки был
недоопределён и код это вскрыл. Тесты фиксируют закрытое поведение.
"""

from lbs_core.graph import Hypergraph, Hyperedge, holds
from lbs_core.classify import analyze, classify_nodes, Substitution, Label


def _g(nodes, edges, sink):
    return Hypergraph(nodes=set(nodes),
                      edges=[Hyperedge(i, frozenset(t), h) for i, t, h in edges],
                      sink=sink)


# ---------- базовая семантика holds ----------

def test_conjunction_all_carrying():
    g = _g({"n1", "n2", "g"}, [("e1", {"n1", "n2"}, "g")], "g")
    assert holds(g)
    assert not holds(g.without_nodes(["n1"]))
    assert not holds(g.without_nodes(["n2"]))


def test_disjunction_alternative_paths():
    g = _g({"n1", "n2", "g"},
           [("e1", {"n1"}, "g"), ("e2", {"n2"}, "g")], "g")
    assert holds(g)
    assert holds(g.without_nodes(["n1"]))          # второй путь жив
    assert not holds(g.without_nodes(["n1", "n2"]))  # оба пути перекрыты


# ---------- регрессии найденных дыр ----------

def test_regression_orphaned_sink_not_a_premise():
    """Дыра #1: удаление всех путей к цели оставляло gamma без входящих дуг,
    и она ложно считалась достигнутой посылкой."""
    g = _g({"n1", "n2", "g"},
           [("e1", {"n1"}, "g"), ("e2", {"n2"}, "g")], "g")
    assert not holds(g.without_nodes(["n1", "n2"]))


def test_regression_removing_sink_returns_false_not_raises():
    """Дыра #2: удаление самого sink роняло валидатор вместо честного False."""
    g = _g({"n1", "g"}, [("e1", {"n1"}, "g")], "g")
    assert holds(g.without_nodes(["g"])) is False


def test_regression_budget_zero_gives_und_not_lb():
    """Дыра #3: budget=0 давал ложный LB (пустой перебор считался полным).
    Правило асимметрии: 'не проверили' != 'замены нет'."""
    g = _g({"x", "g"}, [("e", {"x"}, "g")], "g")
    sub = Substitution("s1", [Hyperedge("e2", frozenset({"y"}), "g")], excludes_node="x")
    v = analyze(g, sigma=[sub], budget=0).verdicts["x"]
    assert v.label == Label.UND


def test_regression_substitution_may_introduce_new_nodes():
    """Дыра #4+#5: замена не могла вводить новые узлы, и holds не признавал
    новые истоки из замен. Замена через новый узел y делает x сценой."""
    g = _g({"x", "g"}, [("e", {"x"}, "g")], "g")
    sub = Substitution("s1", [Hyperedge("e2", frozenset({"y"}), "g")], excludes_node="x")
    v = analyze(g, sigma=[sub], budget=100).verdicts["x"]
    assert v.label == Label.SC
    assert v.witness == "s1"


def test_regression_orphaned_intermediate_node_not_a_premise():
    """Дыра #6: осиротевший ПРОМЕЖУТОЧНЫЙ узел (не sink) ложно считался посылкой.
    Обобщение дыры #1 на любой выводимый узел."""
    # m выводится из a; g выводится из m. Удаляем a => m осиротел => g недостижим.
    g = _g({"a", "m", "g"},
           [("e1", {"a"}, "m"), ("e2", {"m"}, "g")], "g")
    assert holds(g)
    assert not holds(g.without_nodes(["a"]))       # m осиротел, не стал посылкой


# ---------- co-load-bearing (E1) ----------

def test_co_load_bearing_pair_detected():
    """Два узла по отдельности сцена, вместе несущие: одиночный тест метит их SC,
    а поиск MLBS обязан поймать пару."""
    g = _g({"a", "b", "g"},
           [("ea", {"a"}, "g"), ("eb", {"b"}, "g")], "g")
    rep = analyze(g, sigma=[], sigma_completeness="enumerated")
    assert rep.verdicts["a"].label == Label.SC
    assert rep.verdicts["b"].label == Label.SC
    assert frozenset({"a", "b"}) in rep.mlbs_sets


# ---------- интеграция: реальный пример ----------

def test_erc8183_example_shape():
    """Реальный пример классифицируется устойчиво: 3 несущих, декоративные узлы —
    сцена, найдены совместно несущие множества."""
    from pathlib import Path
    from lbs_core.loader import load_scenario
    path = Path(__file__).parent.parent / "examples" / "erc8183_evaluator_independence.json"
    sc = load_scenario(path)
    rep = analyze(sc.graph, sigma=sc.sigma, sigma_completeness=sc.sigma_completeness)
    # несущее ядро
    assert rep.verdicts["eval_output_trusted"].label == Label.LB
    assert rep.verdicts["eval_compromised"].label == Label.LB
    # декоративные — сцена
    assert rep.verdicts["cosmetic_audit_badge"].label == Label.SC
    assert rep.verdicts["verbose_logging"].label == Label.SC
    # есть совместно несущие множества размера 2
    assert any(len(m) == 2 for m in rep.mlbs_sets)


def test_potpie_case_shape():
    """Реальный кейс (cases/potpie-context-provenance): несущее ядро — отсутствие
    trust-поля в схеме и точка записи claim; все 4 ingress + 7 egress каналов —
    сцена по отдельности (патч одного не ломает атаку, пока жив альтернативный).
    См. cases/potpie-context-provenance/WRITEUP.md и SOURCES.md."""
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
    """Реальный кейс (cases/erc8183-evaluator-integrity): несущее ядро — вся цепочка
    от контроля провайдера над deliverable до verdict_flipped (7 узлов, включая
    цель); две downstream-ветки (escrow / reputation) — сцена по отдельности, но
    дают 4 совместно несущих пары (crossing двух независимых путей) — тот же
    сигнатурный паттерн, что и в синтетическом examples/erc8183_evaluator_independence.json.
    См. cases/erc8183-evaluator-integrity/WRITEUP.md и SOURCES.md."""
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
    """Реальный кейс (cases/potpie-graphrag-prompt-injection): строго
    последовательная цепочка (март 2026, pre-v2.0.0 Potpie) — все 6 узлов +
    цель классифицируются как LB, сцены нет вообще. Контрольный кейс:
    инструмент не изобретает структуру там, где её нет. Model choice и
    tool allowlist намеренно НЕ закодированы как Σ — см. SOURCES.md.
    См. cases/potpie-graphrag-prompt-injection/WRITEUP.md."""
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
