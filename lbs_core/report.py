"""
Человекочитаемый отчёт по результату анализа.

Отчёт — то, что читает аналитик. Он обязан быть честен относительно границ
метода (v0.1): вердикт SC != "безопасно", а "устранимо в этом сценарии при этом Σ";
LB помечается флагом, если Σ неполон (риск ложного LB).
"""

from __future__ import annotations

from .classify import Report, Label
from .loader import Scenario


def render_report(scenario: Scenario, report: Report) -> str:
    txt = scenario.node_text
    lines: list[str] = []
    add = lines.append

    add("=" * 72)
    add(f"LBS-анализ: {scenario.title}")
    add("=" * 72)
    add("")
    add(f"Цель (gamma): {scenario.graph.sink}")
    if scenario.graph.sink in txt:
        add(f"  {txt[scenario.graph.sink]}")
    add("")
    add(f"Полнота Σ: {report.sigma_completeness}")
    if report.sigma_completeness == "best_effort":
        add("  ВНИМАНИЕ: Σ неполон (best_effort). Вердикты LB условны: узел помечен")
        add("  несущим, потому что замена не найдена в заданном Σ, а не потому что её")
        add("  не существует. Пополнение Σ может перевести LB → SC.")
    add("")

    # --- Несущие ---
    lb = [n for n, v in report.verdicts.items() if v.label == Label.LB]
    add(f"НЕСУЩИЕ МЕХАНИЗМЫ (LB) — {len(lb)}:")
    add("  Без любого из них цель недостижима. Это точки контроля / кандидаты в контрмеры.")
    for n in sorted(lb):
        add(f"  [LB] {n}")
        if n in txt:
            add(f"       {txt[n]}")
    add("")

    # --- Сцена ---
    sc = [n for n, v in report.verdicts.items() if v.label == Label.SC]
    add(f"СЦЕНА (SC) — {len(sc)}:")
    add("  Присутствуют, но по отдельности устранимы: цель достижима и без них.")
    add("  ВНИМАНИЕ: SC не означает 'безопасно' или 'бесполезно' — означает 'в этом")
    add("  сценарии при этом Σ удаление одного этого узла не ломает цель'. См. MLBS ниже.")
    for n in sorted(sc):
        v = report.verdicts[n]
        wit = f"  (свидетель: {v.witness})" if v.witness else ""
        add(f"  [SC] {n}{wit}")
        if n in txt:
            add(f"       {txt[n]}")
    add("")

    # --- Неопределённость ---
    und = [n for n, v in report.verdicts.items() if v.label == Label.UND]
    if und:
        add(f"НЕОПРЕДЕЛЁННОСТЬ (UND) — {len(und)}:")
        add("  Бюджет перебора исчерпан до полного. НЕ классифицированы как несущие.")
        add("  Требуется: поднять бюджет либо сократить/структурировать Σ.")
        for n in sorted(und):
            add(f"  [UND] {n}  ({report.verdicts[n].reason})")
        add("")

    # --- MLBS ---
    add("МИНИМАЛЬНЫЕ НЕСУЩИЕ МНОЖЕСТВА (MLBS):")
    add("  Каждое множество — минимальный набор, одновременное удаление которого ломает")
    add("  цель. Размер 1 = одиночный несущий узел. Размер >= 2 = совместно несущие")
    add("  (co-load-bearing): по отдельности сцена, вместе необходимы. Множества размера")
    add("  >= 2 показывают АЛЬТЕРНАТИВНЫЕ пути: чтобы перекрыть цель, надо выбить по")
    add("  одному узлу из каждого независимого пути.")
    singles = [m for m in report.mlbs_sets if len(m) == 1]
    multis = [m for m in report.mlbs_sets if len(m) >= 2]
    for m in sorted(singles, key=lambda s: sorted(s)):
        add(f"  {{{', '.join(sorted(m))}}}  (одиночный несущий)")
    for m in sorted(multis, key=lambda s: (len(s), sorted(s))):
        add(f"  {{{', '.join(sorted(m))}}}  (совместно несущее, size {len(m)})")
    add("")

    # --- Сводка ---
    add("-" * 72)
    c = report.counts
    add(f"Итог: LB={c['LB']}  SC={c['SC']}  UND={c['UND']}  |  MLBS={len(report.mlbs_sets)}")
    add("Доли по LB/SC считаются без UND в знаменателе (UND = не разрешено при бюджете).")
    add("-" * 72)

    return "\n".join(lines)
