"""
Загрузка сценария (attack graph) из JSON в объекты ядра.

Формат входного файла — простой и человекочитаемый; это единственный формат,
который аналитик правит руками. Схема (все поля обязательны, кроме sigma):

{
  "title": "человекочитаемое имя сценария",
  "goal": "g",                       // целевой узел (атака достигнута / инвариант нарушен)
  "nodes": {
     "g":  "злоумышленник проводит расчёт в обход оценщика",
     "n1": "оценщик и исполнитель разделяют канал ввода",
     ...
  },
  "edges": [
     { "id": "e1", "tail": ["n1","n2"], "head": "g" },   // tail СОВМЕСТНО дают head
     ...
  ],
  "sigma": [                          // допустимые замены (обходные подвыводы); опционально
     { "id": "s1", "excludes_node": "n1",
       "added_edges": [ { "id": "s1e1", "tail": ["n9"], "head": "g" } ] }
  ],
  "sigma_completeness": "best_effort" // enumerated | rule_closed | best_effort
}

Тексты узлов носят только пояснительный характер (для отчёта); на классификацию
влияет исключительно структура (edges, sigma). Это соответствие v0.1: вердикт —
функция графа, не формулировок.
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
    node_text: dict[str, str]        # id -> человекочитаемое описание (для отчёта)


def _parse_edge(raw: dict, ctx: str) -> Hyperedge:
    for key in ("id", "tail", "head"):
        if key not in raw:
            raise ValueError(f"{ctx}: в ребре отсутствует поле {key!r}: {raw}")
    if not isinstance(raw["tail"], list) or not raw["tail"]:
        raise ValueError(f"{ctx}: tail ребра {raw['id']!r} должен быть непустым списком")
    return Hyperedge(eid=str(raw["id"]),
                     tail=frozenset(str(t) for t in raw["tail"]),
                     head=str(raw["head"]))


def load_scenario(path: str | Path) -> Scenario:
    """Прочитать и провалидировать сценарий из JSON-файла."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))

    for key in ("goal", "nodes", "edges"):
        if key not in data:
            raise ValueError(f"в сценарии отсутствует обязательное поле {key!r}")

    node_text: dict[str, str] = {str(k): str(v) for k, v in data["nodes"].items()}
    nodes = set(node_text.keys())
    goal = str(data["goal"])
    if goal not in nodes:
        raise ValueError(f"goal {goal!r} отсутствует среди nodes")

    edges = [_parse_edge(e, "edges") for e in data["edges"]]

    sigma: list[Substitution] = []
    for s in data.get("sigma", []):
        if "id" not in s or "added_edges" not in s:
            raise ValueError(f"замена sigma требует полей id и added_edges: {s}")
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
