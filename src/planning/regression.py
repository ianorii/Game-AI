"""
regression.py - Backward Search (Regression Planning)

Menerapkan pencarian mundur dari sasaran (subgoal regression) sesuai materi kuliah:
  - Subgoal g' = (g - add(a)) U pre(a)
  - Relevan: add(a) beririsan dengan g (menambah minimal satu fakta sasaran)
  - Konsisten: del(a) tidak beririsan dengan g (tidak menghapus fakta sasaran)
  - Terminasi: g' subset dari initial state (seluruh fakta pada g' sudah benar di s0)
  - Pembalikan aksi: urutan mundur [a_k, ..., a_1] dibalik menjadi [a_1, ..., a_k]
"""

import time
import heapq
from collections import deque
from dataclasses import dataclass
from typing import List, Set, Tuple, Dict, Optional, FrozenSet, Any

from planning.strips import Predicate, STRIPSState, GroundAction, PlanningProblem, PlanValidator
from planning.planner import SearchResult


@dataclass
class RegressionStep:
    step_num: int
    action: GroundAction
    subgoal_before: FrozenSet[Predicate]
    subgoal_after: FrozenSet[Predicate]
    added_to_subgoal: FrozenSet[Predicate]
    removed_from_subgoal: FrozenSet[Predicate]


@dataclass
class RegressionTrace:
    initial_goal: FrozenSet[Predicate]
    steps: List[RegressionStep]
    final_subgoal: FrozenSet[Predicate]
    is_satisfied_in_init: bool
    forward_plan: List[GroundAction]


def get_static_predicates(actions: List[GroundAction]) -> Set[str]:
    """Mengidentifikasi nama predikat statis (tidak pernah berubah oleh add/del efek aksi)."""
    dynamic_preds = set()
    for a in actions:
        for p in a.add_effects:
            dynamic_preds.add(p.name)
        for p in a.delete_effects:
            dynamic_preds.add(p.name)
    all_preds = set()
    for a in actions:
        for p in a.preconditions:
            all_preds.add(p.name)
    return all_preds - dynamic_preds


def get_relevant_consistent_actions(subgoal: FrozenSet[Predicate],
                                   actions: List[GroundAction],
                                   init_facts: Optional[FrozenSet[Predicate]] = None,
                                   static_preds: Optional[Set[str]] = None) -> List[GroundAction]:
    """
    Menyaring aksi yang RELEVAN dan KONSISTEN terhadap subgoal g.
    - Relevan: add(a) beririsan dengan g (menghasilkan minimal 1 fakta g).
    - Konsisten: del(a) tidak beririsan dengan g (tidak menghancurkan fakta g).
    - Prasyarat Statis: diverifikasi benar di initial state (Slide 29).
    """
    candidates = []
    for a in actions:
        # Relevansi: a harus menambahkan setidaknya satu literal pada subgoal
        if not (a.add_effects & subgoal):
            continue
        # Konsistensi: a tidak boleh menghapus literal yang dibutuhkan pada subgoal
        if a.delete_effects & subgoal:
            continue
        # Verifikasi prasyarat statis di initial state (Slide 29)
        if init_facts is not None and static_preds:
            static_pre = {p for p in a.preconditions if p.name in static_preds}
            if not static_pre <= init_facts:
                continue
        candidates.append(a)
    return candidates


def regress_subgoal(subgoal: FrozenSet[Predicate], action: GroundAction,
                    static_preds: Optional[Set[str]] = None) -> FrozenSet[Predicate]:
    """
    Melakukan regresi mundur:
    g' = (g - add(a)) U pre_dynamic(a)
    Fakta statis (mis. road, connected) diverifikasi tapi tidak dimasukkan ke subgoal baru (Slide 29).
    """
    if static_preds:
        pre_dynamic = {p for p in action.preconditions if p.name not in static_preds}
    else:
        pre_dynamic = action.preconditions
    new_facts = (subgoal - action.add_effects) | pre_dynamic
    return frozenset(new_facts)


def search_regression_bfs(problem: PlanningProblem, max_nodes: int = 15000,
                          timeout_sec: float = 10.0) -> SearchResult:
    """
    Pencarian Backward (Regression) menggunakan Breadth-First Search (BFS).
    """
    t0 = time.perf_counter()
    init_facts = problem.initial_state.facts
    goal_subgoal = problem.goal
    static_preds = get_static_predicates(problem.actions)

    # Cek apakah initial state sudah langsung memenuhi goal
    if goal_subgoal <= init_facts:
        ms = (time.perf_counter() - t0) * 1000.0
        return SearchResult(success=True, plan=[], total_cost=0.0, total_duration=0.0,
                            nodes_expanded=0, nodes_generated=1, time_ms=ms,
                            algorithm="Regression_BFS")

    # Queue menyimpan (subgoal, backward_actions_list, cost, duration)
    queue = deque([(goal_subgoal, [], 0.0, 0.0)])
    visited = {goal_subgoal}

    nodes_expanded = 0
    nodes_generated = 1

    while queue:
        if nodes_expanded >= max_nodes:
            ms = (time.perf_counter() - t0) * 1000.0
            return SearchResult(success=False, nodes_expanded=nodes_expanded,
                                nodes_generated=nodes_generated, time_ms=ms,
                                ms_per_node=ms / max(1, nodes_expanded),
                                algorithm="Regression_BFS",
                                failure_reason="Batas maksimum node tercapai (node limit).")

        if (time.perf_counter() - t0) > timeout_sec:
            ms = (time.perf_counter() - t0) * 1000.0
            return SearchResult(success=False, nodes_expanded=nodes_expanded,
                                nodes_generated=nodes_generated, time_ms=ms,
                                ms_per_node=ms / max(1, nodes_expanded),
                                algorithm="Regression_BFS",
                                failure_reason="Waktu pencarian habis (timeout).")

        current_subgoal, backward_path, cost, duration = queue.popleft()
        nodes_expanded += 1

        # Dapatkan aksi yang relevan dan konsisten
        applicable_actions = get_relevant_consistent_actions(current_subgoal, problem.actions, init_facts, static_preds)

        for act in applicable_actions:
            next_subgoal = regress_subgoal(current_subgoal, act, static_preds)
            next_path = [act] + backward_path  # mundur: tambahkan di depan
            next_cost = cost + act.cost
            next_duration = duration + act.duration
            nodes_generated += 1

            # Evaluasi apakah subgoal sudah terpenuhi seluruhnya oleh initial state
            if next_subgoal <= init_facts:
                ms = (time.perf_counter() - t0) * 1000.0
                return SearchResult(
                    success=True,
                    plan=next_path,  # next_path sudah terurut maju karena konstruksi [act] + backward_path
                    total_cost=next_cost,
                    total_duration=next_duration,
                    nodes_expanded=nodes_expanded,
                    nodes_generated=nodes_generated,
                    time_ms=ms,
                    ms_per_node=ms / max(1, nodes_expanded),
                    algorithm="Regression_BFS"
                )

            if next_subgoal not in visited:
                visited.add(next_subgoal)
                queue.append((next_subgoal, next_path, next_cost, next_duration))

    ms = (time.perf_counter() - t0) * 1000.0
    return SearchResult(success=False, nodes_expanded=nodes_expanded,
                        nodes_generated=nodes_generated, time_ms=ms,
                        ms_per_node=ms / max(1, nodes_expanded),
                        algorithm="Regression_BFS",
                        failure_reason="Ruang pencarian backward habis tanpa menemukan solusi.")


def search_regression_astar(problem: PlanningProblem, max_nodes: int = 15000,
                            timeout_sec: float = 10.0) -> SearchResult:
    """
    Pencarian Backward (Regression) menggunakan A* Search.
    Heuristik h(g) = jumlah fakta g yang belum terpenuhi di initial state s0.
    """
    t0 = time.perf_counter()
    init_facts = problem.initial_state.facts
    goal_subgoal = problem.goal
    static_preds = get_static_predicates(problem.actions)

    if goal_subgoal <= init_facts:
        ms = (time.perf_counter() - t0) * 1000.0
        return SearchResult(success=True, plan=[], total_cost=0.0, total_duration=0.0,
                            nodes_expanded=0, nodes_generated=1, time_ms=ms,
                            algorithm="Regression_A*")

    def calc_h(subgoal: FrozenSet[Predicate]) -> float:
        # Heuristik menghitung selisih fakta g yang belum ada di s0
        unmet = subgoal - init_facts
        return float(len(unmet))

    counter = 0
    h0 = calc_h(goal_subgoal)
    pq = [(h0, 0.0, counter, goal_subgoal, [])]
    best_g: Dict[FrozenSet[Predicate], float] = {goal_subgoal: 0.0}

    nodes_expanded = 0
    nodes_generated = 1

    while pq:
        if nodes_expanded >= max_nodes:
            ms = (time.perf_counter() - t0) * 1000.0
            return SearchResult(success=False, nodes_expanded=nodes_expanded,
                                nodes_generated=nodes_generated, time_ms=ms,
                                ms_per_node=ms / max(1, nodes_expanded),
                                algorithm="Regression_A*",
                                failure_reason="Batas maksimum node tercapai (node limit).")

        if (time.perf_counter() - t0) > timeout_sec:
            ms = (time.perf_counter() - t0) * 1000.0
            return SearchResult(success=False, nodes_expanded=nodes_expanded,
                                nodes_generated=nodes_generated, time_ms=ms,
                                ms_per_node=ms / max(1, nodes_expanded),
                                algorithm="Regression_A*",
                                failure_reason="Waktu pencarian habis (timeout).")

        f_val, g_cost, _, current_subgoal, backward_path = heapq.heappop(pq)

        if g_cost > best_g.get(current_subgoal, float("inf")):
            continue

        nodes_expanded += 1

        if current_subgoal <= init_facts:
            ms = (time.perf_counter() - t0) * 1000.0
            tot_cost = sum(a.cost for a in backward_path)
            tot_dur = sum(a.duration for a in backward_path)
            return SearchResult(
                success=True,
                plan=backward_path,
                total_cost=tot_cost,
                total_duration=tot_dur,
                nodes_expanded=nodes_expanded,
                nodes_generated=nodes_generated,
                time_ms=ms,
                ms_per_node=ms / max(1, nodes_expanded),
                algorithm="Regression_A*"
            )

        applicable_actions = get_relevant_consistent_actions(current_subgoal, problem.actions, init_facts, static_preds)

        for act in applicable_actions:
            next_subgoal = regress_subgoal(current_subgoal, act, static_preds)
            next_g = g_cost + act.cost
            nodes_generated += 1

            if next_g < best_g.get(next_subgoal, float("inf")):
                best_g[next_subgoal] = next_g
                h_val = calc_h(next_subgoal)
                counter += 1
                heapq.heappush(pq, (next_g + h_val, next_g, counter, next_subgoal, [act] + backward_path))

    ms = (time.perf_counter() - t0) * 1000.0
    return SearchResult(success=False, nodes_expanded=nodes_expanded,
                        nodes_generated=nodes_generated, time_ms=ms,
                        ms_per_node=ms / max(1, nodes_expanded),
                        algorithm="Regression_A*",
                        failure_reason="Ruang pencarian backward habis tanpa menemukan solusi.")


def build_regression_trace(problem: PlanningProblem, forward_plan: List[GroundAction]) -> RegressionTrace:
    """
    Menghasilkan rekaman trace eksekusi backward persis seperti format slide 27.
    Dimulai dari goal, mundur langkah demi langkah hingga initial state.
    """
    static_preds = get_static_predicates(problem.actions)
    current_subgoal = problem.goal
    steps: List[RegressionStep] = []

    # Balik rencana maju untuk menelusuri mundur
    backward_actions = list(reversed(forward_plan))

    for idx, act in enumerate(backward_actions, start=1):
        prev_subgoal = current_subgoal
        next_subgoal = regress_subgoal(prev_subgoal, act, static_preds)
        added = next_subgoal - prev_subgoal
        removed = prev_subgoal - next_subgoal

        steps.append(RegressionStep(
            step_num=idx,
            action=act,
            subgoal_before=prev_subgoal,
            subgoal_after=next_subgoal,
            added_to_subgoal=added,
            removed_from_subgoal=removed
        ))
        current_subgoal = next_subgoal

    is_satisfied = current_subgoal <= problem.initial_state.facts

    return RegressionTrace(
        initial_goal=problem.goal,
        steps=steps,
        final_subgoal=current_subgoal,
        is_satisfied_in_init=is_satisfied,
        forward_plan=forward_plan
    )


def format_regression_trace(trace: RegressionTrace) -> str:
    """Format string untuk mencetak trace backward seperti slide 27."""
    lines = []
    lines.append("=" * 70)
    lines.append("TRACE BACKWARD SEARCH (REGRESSION) - SESUAI SLIDE 27")
    lines.append("=" * 70)
    goal_str = ", ".join(str(p) for p in sorted(trace.initial_goal, key=lambda x: str(x)))
    lines.append(f"Subgoal 0 (Goal Awal) : {{ {goal_str} }}")

    for s in trace.steps:
        lines.append("-" * 70)
        lines.append(f"Langkah Mundur {s.step_num}: Aksi '{s.action.signature}'")
        rel_eff = ", ".join(str(p) for p in sorted(s.action.add_effects & s.subgoal_before, key=lambda x: str(x)))
        pre_str = ", ".join(str(p) for p in sorted(s.action.preconditions, key=lambda x: str(x)))
        lines.append(f"  Fakta Sasaran Terpenuhi  : {{ {rel_eff} }}")
        lines.append(f"  Prasyarat Ditambahkan   : {{ {pre_str} }}")
        after_str = ", ".join(str(p) for p in sorted(s.subgoal_after, key=lambda x: str(x)))
        lines.append(f"  Subgoal {s.step_num}                    : {{ {after_str} }}")

    lines.append("=" * 70)
    final_str = ", ".join(str(p) for p in sorted(trace.final_subgoal, key=lambda x: str(x)))
    lines.append(f"Subgoal Akhir: {{ {final_str} }}")
    lines.append(f"Subset dari Initial State: {'YA (SOLUSI DITEMUKAN!)' if trace.is_satisfied_in_init else 'TIDAK'}")
    fwd_str = " -> ".join(a.signature for a in trace.forward_plan)
    lines.append(f"Forward Plan: {fwd_str}")
    lines.append("=" * 70)
    return "\n".join(lines)

