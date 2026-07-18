"""
Классификация узлов: несущий (LB) / сцена (SC) / неопределённость (UND)
и поиск минимальных несущих множеств (MLBS).

Семантика — замороженное ядро LBS v0.1:
- §2 (N1): узел n НЕСУЩИЙ, если ни одна допустимая замена σ ⊆ Σ, не использующая n,
  не восстанавливает holds(gamma) после удаления n.
- §3 (S1): узел n — СЦЕНА, если такая замена существует (предъявлен свидетель σ).
- §5: при исчерпании бюджета до полного перебора статус → UND (НЕ LB).
  Правило асимметрии: LB требует полного перебора (доказать отсутствие замены),
  SC требует одного свидетеля.
- §9: MLBS M — множество, чьё одновременное удаление ломает holds при всех σ ⊆ Σ,
  и никакое собственное подмножество M этим свойством не обладает.
  LB-узел = MLBS размера 1; co-load-bearing = MLBS размера >= 2.

Детерминированно, без сети и LLM.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from itertools import combinations

from .graph import Hypergraph, Hyperedge, holds


class Label(str, Enum):
    LB = "LB"       # load-bearing (несущий)
    SC = "SC"       # scaffolding (сцена)
    UND = "UND"     # undetermined (неопределённость)


@dataclass
class Substitution:
    """Допустимая замена из пула Σ: набор гипердуг, вводимых при проверке.

    excludes_node — узел, который эта замена НЕ имеет права использовать
    (обходной вывод, не опирающийся на проверяемый узел). v0.1 §2/§3.
    """
    sid: str
    added_edges: list[Hyperedge]
    excludes_node: str | None = None


@dataclass
class NodeVerdict:
    node: str
    label: Label
    witness: str | None = None       # sid замены-свидетеля (для SC)
    reason: str | None = None        # причина (для LB/UND)


@dataclass
class Report:
    verdicts: dict[str, NodeVerdict]
    mlbs_sets: list[frozenset[str]]
    counts: dict[str, int]
    sigma_completeness: str
    budget_hit: bool                 # был ли где-то исчерпан бюджет (→ есть UND)


def _replacement_restores(
    graph: Hypergraph,
    removed: set[str],
    sigma: list[Substitution],
    budget: int,
) -> tuple[bool, str | None, bool]:
    """Ищет замену σ ⊆ Σ (не использующую removed), восстанавливающую holds после
    удаления removed.

    Возвращает (found, witness_sid, exhausted):
      found      — найдена ли восстанавливающая замена (=> removed устранимо => SC),
      witness_sid — идентификатор свидетеля (первой сработавшей замены),
      exhausted  — был ли перебор ПОЛНЫМ (True) или оборван бюджетом (False).

    Перебираются подмножества применимых замен. Применимой считается замена, чей
    excludes_node не входит в removed-конфликт (замена не должна опираться на
    удаляемые узлы). Порядок: сначала пустая (само удаление), затем по возрастанию
    размера комбинации — свидетель минимального размера предпочтительнее.
    """
    base = graph.without_nodes(removed)
    if holds(base):
        # Цель достижима даже без всяких замен — removed заведомо устранимо.
        return True, "∅", True

    # Применимая замена не должна опираться на удаляемые узлы: ни через пометку
    # excludes_node, ни фактически (удаляемый узел в tail/head её дуг). Вводить
    # НОВЫЕ узлы (альтернативный подвывод через другие посылки) замене разрешено.
    applicable = [
        s for s in sigma
        if not (set(removed) & {
            n for e in s.added_edges for n in (set(e.tail) | {e.head})
        })
    ]

    # Если есть применимые замены, но бюджета не хватает даже на одну проверку —
    # это НЕ полный перебор. Нельзя объявлять removed несущим (правило асимметрии
    # §5.2/§5.3: "не проверили" != "замены нет"). Сразу UND.
    if applicable and budget <= 0:
        return False, None, False

    tried = 0
    # Перебор по возрастанию размера комбинации замен.
    for k in range(1, len(applicable) + 1):
        for combo in combinations(applicable, k):
            if tried >= budget:
                return False, None, False  # бюджет исчерпан до полного перебора
            tried += 1
            added: list[Hyperedge] = []
            for s in combo:
                added.extend(s.added_edges)
            candidate = base.with_added_edges(added)
            if holds(candidate):
                sids = "+".join(s.sid for s in combo)
                return True, sids, True
    # Полный перебор всех применимых замен завершён, восстановления нет => несущее.
    # (Если applicable пуст, это тоже корректно: доступных замен нет вообще.)
    return False, None, True


def classify_nodes(
    graph: Hypergraph,
    sigma: list[Substitution] | None = None,
    budget: int = 10_000,
    sigma_completeness: str = "best_effort",
) -> dict[str, NodeVerdict]:
    """Одиночный тест по всем узлам (v0.1 §4 шаг 3, §5).

    Узлы-истоки и сама цель тоже классифицируются (удаление истока обычно ломает
    вывод => LB; это корректно). budget ограничивает перебор замен НА КАЖДЫЙ узел.
    """
    sigma = sigma or []
    verdicts: dict[str, NodeVerdict] = {}

    for n in sorted(graph.nodes):
        found, witness, exhausted = _replacement_restores(graph, {n}, sigma, budget)
        if found:
            verdicts[n] = NodeVerdict(n, Label.SC, witness=witness)
        elif exhausted:
            # Полный перебор, замены нет => необходимость доказана => LB.
            note = "full_search_no_replacement"
            if sigma_completeness == "best_effort":
                note += "; LB_relative_to_incomplete_sigma"
            verdicts[n] = NodeVerdict(n, Label.LB, reason=note)
        else:
            # Бюджет исчерпан до полного перебора => UND, НЕ LB (правило §5.2/§5.3).
            verdicts[n] = NodeVerdict(n, Label.UND, reason="budget_exhausted")

    return verdicts


def find_mlbs(
    graph: Hypergraph,
    sigma: list[Substitution] | None = None,
    max_set_size: int = 3,
    budget: int = 10_000,
    single_verdicts: dict[str, NodeVerdict] | None = None,
) -> list[frozenset[str]]:
    """Поиск минимальных несущих множеств (v0.1 §4 шаг 4, §9).

    Возвращает минимальные M (по включению), чьё одновременное удаление ломает holds
    при всех σ ⊆ Σ. Множества размера 1 (уже найденные LB-узлы) включаются, множества
    большего размера проверяются только среди узлов, НЕ являющихся одиночными LB
    (иначе множество не минимально: его подмножество-LB уже несущее).

    max_set_size ограничивает комбинаторный взрыв (v0.1 E1): полный перебор подмножеств
    экспоненциален, поэтому размер ограничен явно. budget — на каждое проверяемое M.
    """
    sigma = sigma or []
    single = single_verdicts or classify_nodes(graph, sigma, budget)

    mlbs: list[frozenset[str]] = []

    # Размер 1: несущие узлы — это MLBS-одиночки.
    lb_singletons = {n for n, v in single.items() if v.label == Label.LB}
    for n in lb_singletons:
        mlbs.append(frozenset({n}))

    # Размеры >= 2: только среди узлов, не покрытых одиночными LB.
    # (Если M содержит LB-узел, M не минимально.)
    candidates = sorted(n for n in graph.nodes if n not in lb_singletons)

    for size in range(2, max_set_size + 1):
        for combo in combinations(candidates, size):
            M = set(combo)
            # Минимальность: ни одно собственное подмножество M уже не в mlbs.
            if any(existing < frozenset(M) for existing in mlbs):
                continue
            found, _, exhausted = _replacement_restores(graph, M, sigma, budget)
            # M несущее <=> замены нет (found=False) при полном переборе (exhausted).
            if (not found) and exhausted:
                # Проверка минимальности: удаление любого элемента M должно ДЕЛАТЬ
                # множество устранимым (иначе несущее подмножество, M не минимально).
                is_minimal = True
                for x in M:
                    sub = M - {x}
                    if not sub:
                        continue
                    sub_found, _, sub_exh = _replacement_restores(graph, sub, sigma, budget)
                    if (not sub_found) and sub_exh:
                        is_minimal = False  # подмножество тоже несущее
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
    """Полный прогон: одиночный тест + MLBS + агрегация (v0.1 §4).

    counts держит UND отдельной строкой; доли LB/SC НЕ считаются по знаменателю
    с UND (v0.1 §5 шаг 5).
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
