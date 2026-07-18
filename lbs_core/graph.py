"""
Гиперграф вывода и предикат достижимости.

Семантика зафиксирована спецификацией LBS v0.1, раздел 9 (замороженное ядро):
- Узлы V — атомарные утверждения/шаги.
- Гипердуга e = (tail, head): множество посылок tail СОВМЕСТНО достаточно для head.
  Обычное ребро причинного DAG — частный случай гипердуги с |tail| == 1.
- Дизъюнкция ("head достижим через e1 ЛИБО e2") выражается несколькими гипердугами
  с одним и тем же head.
- holds(gamma) == существует ли гиперпуть от истоков (узлы без входящих гипердуг,
  т.е. посылки/аксиомы) к gamma целиком внутри текущего гиперграфа.
- Удаление узла n: убрать n и ВСЕ гипердуги, где n входит в tail или является head.

Модуль не содержит недетерминизма и не обращается к сети (инвариант ядра).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable


@dataclass(frozen=True)
class Hyperedge:
    """Гипердуга: tail СОВМЕСТНО достаточно для head.

    tail — неизменяемое множество имён узлов (frozenset для хешируемости).
    head — имя одного узла.
    eid  — стабильный идентификатор гипердуги (для журналов и свидетелей).
    """
    eid: str
    tail: frozenset[str]
    head: str

    def uses(self, node: str) -> bool:
        """True, если узел участвует в этой гипердуге (в tail или как head)."""
        return node in self.tail or node == self.head


@dataclass
class Hypergraph:
    """Гиперграф вывода с единственным стоком gamma.

    nodes  — множество всех узлов.
    edges  — список гипердуг.
    sink   — целевой узел gamma (единственный; предположение A7 спецификации).
    """
    nodes: set[str]
    edges: list[Hyperedge]
    sink: str
    # Истоки исходного графа. Задаются только при первичном построении; при
    # порождении подграфов (without_nodes / with_added_edges) пробрасываются
    # неизменными, чтобы holds различал "gamma-посылка" и "gamma-осиротела".
    _original_sources: set[str] | None = field(default=None, repr=False)

    def __post_init__(self) -> None:
        # Валидация структуры на входе — дешёвая защита от битого графа.
        # sink обязан быть среди узлов ТОЛЬКО в первичном графе (_original_sources
        # ещё не задан). В порождённых подграфах цель могла быть легально удалена —
        # тогда holds() честно вернёт False, а не бросит исключение.
        if self._original_sources is None and self.sink not in self.nodes:
            raise ValueError(f"sink {self.sink!r} отсутствует среди узлов")
        for e in self.edges:
            missing = (set(e.tail) | {e.head}) - self.nodes
            if missing:
                raise ValueError(
                    f"гипердуга {e.eid!r} ссылается на неизвестные узлы: {sorted(missing)}"
                )
        # При первичном построении фиксируем истоки как посылки исходной задачи.
        if self._original_sources is None:
            heads = {e.head for e in self.edges}
            self._original_sources = {n for n in self.nodes if n not in heads}

    def sources(self) -> set[str]:
        """Истоки: узлы, не являющиеся head ни одной гипердуги (посылки/аксиомы)."""
        heads = {e.head for e in self.edges}
        return {n for n in self.nodes if n not in heads}

    def original_sources(self) -> set[str]:
        """Истоки ИСХОДНОГО графа (посылки, заданные как таковые при построении).

        Нужны, чтобы отличить "gamma была посылкой" от "gamma осталась без входящих
        дуг после удаления узлов". Во втором случае цель НЕ считается достигнутой:
        удаление всех выводящих её дуг обязано ломать holds. Фиксируется один раз
        при создании графа."""
        return self._original_sources

    def __hash__(self):  # noqa: D401 - dataclass не frozen, хеш по id для кеша
        return id(self)

    def without_nodes(self, removed: Iterable[str]) -> "Hypergraph":
        """Вернуть копию графа без указанных узлов и всех инцидентных им гипердуг.

        Реализует операцию удаления из v0.1 §9: H ⊖ M.
        """
        removed_set = set(removed)
        new_nodes = self.nodes - removed_set
        new_edges = [e for e in self.edges if not any(e.uses(n) for n in removed_set)]
        # sink может быть удалён — тогда граф теряет цель; holds на нём вернёт False.
        # Исходные истоки пробрасываем неизменными (за вычетом удалённых узлов).
        return Hypergraph(
            nodes=new_nodes,
            edges=new_edges,
            sink=self.sink,
            _original_sources=(self._original_sources or set()) - removed_set,
        )

    def with_added_edges(self, added: Iterable[Hyperedge]) -> "Hypergraph":
        """Вернуть копию графа с добавленными гипердугами (применение замены из Σ)."""
        added_list = list(added)
        # Узлы, впервые появляющиеся в добавленных дугах, вводятся в граф.
        extra_nodes: set[str] = set()
        for e in added_list:
            extra_nodes |= set(e.tail) | {e.head}
        all_edges = self.edges + added_list
        # Новые узлы, не являющиеся head ни одной дуги, — законные посылки
        # альтернативного подвывода: регистрируем их как истоки.
        heads = {e.head for e in all_edges}
        genuinely_new_sources = {n for n in extra_nodes if n not in heads}
        return Hypergraph(
            nodes=self.nodes | extra_nodes,
            edges=all_edges,
            sink=self.sink,
            _original_sources=(self._original_sources or set()) | genuinely_new_sources,
        )


def holds(graph: Hypergraph) -> bool:
    """Предикат достижения цели: достижим ли gamma из истоков по гиперпутям.

    Алгоритм — восходящее замыкание (forward chaining):
      derived := истоки
      повторять: если у гипердуги ВЕСЬ tail ⊆ derived, добавить head в derived
      пока derived растёт.
    gamma достижим ⟺ gamma ∈ derived.

    Сложность полиномиальна: каждый проход O(|E|), проходов не больше |V|.
    Это и есть holds(H, gamma) из v0.1 §9 для kind="reachability".
    """
    if graph.sink not in graph.nodes:
        return False  # цель была удалена вместе с узлом

    # Посылка = узел, бывший истоком В ИСХОДНОМ графе. Узел, осиротевший после
    # удаления всех выводящих его дуг, посылкой НЕ становится — иначе удаление
    # несущего механизма ложно "выводило" бы зависящие от него узлы. Это правило
    # действует для ЛЮБОГО узла (не только sink): промежуточный узел, потерявший
    # все входящие дуги, перестаёт быть достижимым, а не превращается в аксиому.
    derived: set[str] = set(graph.original_sources()) & graph.nodes
    if graph.sink in derived:
        return True  # gamma действительно была посылкой исходной задачи

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
