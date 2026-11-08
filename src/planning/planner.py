"""
planner.py - Classical Planning Search Engine (STRIPS)

Mengimplementasikan:
  1. BFS (baseline, abaikan biaya)
  2. UCS / Dijkstra (biaya optimal)
  3. A* dengan h_max (admissible, biaya optimal)
  4. A* dengan h_add (heuristik aditif)
  5. Weighted A* dengan h_FF (Fast-Forward, cepat untuk horizon panjang)
  6. IncrementalPlanner (step-by-step per frame max_ms < 20 ms)
  7. AnytimePlanner (rencana instan disempurnakan berkala)
  8. Deteksi cepat masalah tanpa solusi (unsolvable reachability)
"""

from collections import deque
from dataclasses import dataclass, field
from typing import List, Optional, Tuple, Dict, Set, Any
import heapq
import time
import math

from planning.strips import PlanningProblem, GroundAction, STRIPSState, PlanValidator
from planning.heuristics import (
    h_max, h_add, h_ff, check_relaxed_reachability, _build_action_pre_index,
    FastHeuristicEngine
)


@dataclass
class SearchResult:
    """Hasil pencarian rencana oleh STRIPS search engine."""
    success: bool
    plan: List[GroundAction] = field(default_factory=list)
    total_cost: float = 0.0
    total_duration: float = 0.0
    nodes_expanded: int = 0
    nodes_generated: int = 0
    time_ms: float = 0.0
    time_search_ms: float = 0.0
    time_heuristic_ms: float = 0.0
    time_grounding_ms: float = 0.0
    ms_per_node: float = 0.0
    algorithm: str = "WA*_hFF"
    failure_reason: Optional[str] = None

    @property
    def plan_length(self) -> int:
        return len(self.plan)

    def summary(self) -> str:
        if not self.success:
            return (f"[{self.algorithm}] GAGAL: {self.failure_reason} "
                    f"(Node: {self.nodes_expanded}, Waktu: {self.time_ms:.2f} ms)")
        return (f"[{self.algorithm}] SUKSES: {len(self.plan)} langkah, Biaya: {self.total_cost:.2f}s, "
                f"Durasi: {self.total_duration:.2f}s, Node: {self.nodes_expanded}, Waktu: {self.time_ms:.2f} ms "
                f"({self.ms_per_node:.3f} ms/node)")


def _ensure_pre_index(problem: PlanningProblem) -> Any:
    if not hasattr(problem, "actions_by_pre") or getattr(problem, "actions_by_pre", None) is None:
        try:
            problem.actions_by_pre = FastHeuristicEngine(problem.actions, problem.goal, problem.initial_state.facts)
        except Exception:
            problem.actions_by_pre = _build_action_pre_index(problem.actions)
    return problem.actions_by_pre


def _build_action_location_index(actions: List[GroundAction]) -> Tuple[Dict[str, List[GroundAction]], List[GroundAction]]:
    """Mengindeks aksi berdasarkan lokasi hero (precondition 'at' atau 'motor-at')."""
    loc_map: Dict[str, List[GroundAction]] = {}
    universal: List[GroundAction] = []
    for a in actions:
        loc = None
        for pre in a.preconditions:
            if pre.name in ("at", "motor-at") and len(pre.args) == 1:
                loc = pre.args[0]
                break
        if loc:
            loc_map.setdefault(loc, []).append(a)
        else:
            universal.append(a)
    return loc_map, universal


def _get_applicable_actions(state: STRIPSState, loc_map: Dict[str, List[GroundAction]],
                            universal: List[GroundAction], all_actions: List[GroundAction]) -> List[GroundAction]:
    """Mengambil aksi yang berlaku dengan membatasi evaluasi hanya ke lokasi hero saat ini."""
    if not loc_map:
        return [a for a in all_actions if a.is_applicable(state)]
    curr_loc = None
    for f in state.facts:
        if f.name in ("at", "motor-at") and len(f.args) == 1:
            curr_loc = f.args[0]
            break
    if curr_loc and curr_loc in loc_map:
        candidates = loc_map[curr_loc] + universal
    else:
        candidates = all_actions
    return [a for a in candidates if a.is_applicable(state)]


# ==============================================================================
# 1. BREADTH-FIRST SEARCH (BFS)
# ==============================================================================
def search_bfs(problem: PlanningProblem, max_nodes: int = 40000, timeout_sec: float = 10.0) -> SearchResult:
    t0 = time.perf_counter()

    reachable, _, missing = check_relaxed_reachability(problem.initial_state, problem.goal, problem.actions)
    if not reachable:
        ms = (time.perf_counter() - t0) * 1000.0
        return SearchResult(
            success=False, algorithm="BFS", time_ms=ms,
            failure_reason=f"Problem tidak memiliki solusi! Sasaran {missing} mustahil tercapai di dunia saat ini."
        )

    if problem.is_goal(problem.initial_state):
        return SearchResult(success=True, plan=[], total_cost=0.0, algorithm="BFS",
                            time_ms=(time.perf_counter() - t0) * 1000.0)

    queue = deque([(problem.initial_state, [])])
    visited = {problem.initial_state.facts}
    nodes_expanded = 0
    nodes_generated = 1

    while queue:
        if nodes_expanded >= max_nodes:
            ms = (time.perf_counter() - t0) * 1000.0
            return SearchResult(success=False, nodes_expanded=nodes_expanded, nodes_generated=nodes_generated,
                                time_ms=ms, ms_per_node=ms / max(1, nodes_expanded), algorithm="BFS",
                                failure_reason="Batas maksimum node tercapai (node limit).")
        if (time.perf_counter() - t0) > timeout_sec:
            ms = (time.perf_counter() - t0) * 1000.0
            return SearchResult(success=False, nodes_expanded=nodes_expanded, nodes_generated=nodes_generated,
                                time_ms=ms, ms_per_node=ms / max(1, nodes_expanded), algorithm="BFS",
                                failure_reason="Waktu pencarian habis (timeout).")

        state, path = queue.popleft()
        nodes_expanded += 1

        for act in problem.actions:
            if not act.is_applicable(state):
                continue
            next_state = act.apply(state)
            nodes_generated += 1

            if problem.is_goal(next_state):
                final_plan = path + [act]
                cost = sum(a.cost for a in final_plan)
                dur = sum(a.duration for a in final_plan)
                ms = (time.perf_counter() - t0) * 1000.0
                return SearchResult(success=True, plan=final_plan, total_cost=cost, total_duration=dur,
                                    nodes_expanded=nodes_expanded, nodes_generated=nodes_generated,
                                    time_ms=ms, ms_per_node=ms / max(1, nodes_expanded), algorithm="BFS")

            if next_state.facts not in visited:
                visited.add(next_state.facts)
                queue.append((next_state, path + [act]))

    ms = (time.perf_counter() - t0) * 1000.0
    return SearchResult(success=False, nodes_expanded=nodes_expanded, nodes_generated=nodes_generated,
                        time_ms=ms, ms_per_node=ms / max(1, nodes_expanded), algorithm="BFS",
                        failure_reason="Ruang pencarian habis tanpa menemukan goal.")


# ==============================================================================
# 2. UNIFORM-COST SEARCH (UCS / Dijkstra)
# ==============================================================================
def search_ucs(problem: PlanningProblem, max_nodes: int = 40000, timeout_sec: float = 10.0) -> SearchResult:
    t0 = time.perf_counter()

    reachable, _, missing = check_relaxed_reachability(problem.initial_state, problem.goal, problem.actions)
    if not reachable:
        ms = (time.perf_counter() - t0) * 1000.0
        return SearchResult(
            success=False, algorithm="UCS", time_ms=ms,
            failure_reason=f"Problem tidak memiliki solusi! Sasaran {missing} mustahil tercapai di dunia saat ini."
        )

    if problem.is_goal(problem.initial_state):
        return SearchResult(success=True, plan=[], total_cost=0.0, algorithm="UCS",
                            time_ms=(time.perf_counter() - t0) * 1000.0)

    counter = 0
    pq = [(0.0, counter, problem.initial_state, [])]
    best_g: Dict[Any, float] = {problem.initial_state.facts: 0.0}
    nodes_expanded = 0
    nodes_generated = 1

    while pq:
        if nodes_expanded >= max_nodes:
            ms = (time.perf_counter() - t0) * 1000.0
            return SearchResult(success=False, nodes_expanded=nodes_expanded, nodes_generated=nodes_generated,
                                time_ms=ms, ms_per_node=ms / max(1, nodes_expanded), algorithm="UCS",
                                failure_reason="Batas maksimum node tercapai (node limit).")
        if (time.perf_counter() - t0) > timeout_sec:
            ms = (time.perf_counter() - t0) * 1000.0
            return SearchResult(success=False, nodes_expanded=nodes_expanded, nodes_generated=nodes_generated,
                                time_ms=ms, ms_per_node=ms / max(1, nodes_expanded), algorithm="UCS",
                                failure_reason="Waktu pencarian habis (timeout).")

        g_cost, _, state, path = heapq.heappop(pq)

        if g_cost > best_g.get(state.facts, float("inf")):
            continue

        nodes_expanded += 1

        if problem.is_goal(state):
            dur = sum(a.duration for a in path)
            ms = (time.perf_counter() - t0) * 1000.0
            return SearchResult(success=True, plan=path, total_cost=g_cost, total_duration=dur,
                                nodes_expanded=nodes_expanded, nodes_generated=nodes_generated,
                                time_ms=ms, ms_per_node=ms / max(1, nodes_expanded), algorithm="UCS")

        for act in problem.actions:
            if not act.is_applicable(state):
                continue
            next_state = act.apply(state)
            nodes_generated += 1
            new_g = g_cost + act.cost

            if new_g < best_g.get(next_state.facts, float("inf")):
                best_g[next_state.facts] = new_g
                counter += 1
                heapq.heappush(pq, (new_g, counter, next_state, path + [act]))

    ms = (time.perf_counter() - t0) * 1000.0
    return SearchResult(success=False, nodes_expanded=nodes_expanded, nodes_generated=nodes_generated,
                        time_ms=ms, ms_per_node=ms / max(1, nodes_expanded), algorithm="UCS",
                        failure_reason="Ruang pencarian habis tanpa menemukan goal.")


# ==============================================================================
# 3. A* DENGAN h_max (Admissible)
# ==============================================================================
def search_astar_hmax(problem: PlanningProblem, max_nodes: int = 40000, timeout_sec: float = 10.0) -> SearchResult:
    t0 = time.perf_counter()
    pre_index = _ensure_pre_index(problem)

    reachable, _, missing = check_relaxed_reachability(problem.initial_state, problem.goal, problem.actions)
    if not reachable:
        ms = (time.perf_counter() - t0) * 1000.0
        return SearchResult(
            success=False, algorithm="A*_hmax", time_ms=ms,
            failure_reason=f"Problem tidak memiliki solusi! Sasaran {missing} mustahil tercapai di dunia saat ini."
        )

    if problem.is_goal(problem.initial_state):
        return SearchResult(success=True, plan=[], total_cost=0.0, algorithm="A*_hmax",
                            time_ms=(time.perf_counter() - t0) * 1000.0)

    h_memo: Dict[Any, float] = {}

    def get_h(s: STRIPSState) -> float:
        k = s.facts
        if k in h_memo:
            return h_memo[k]
        val = h_max(s, problem.goal, problem.actions, pre_index=pre_index)
        h_memo[k] = val
        return val

    h0 = get_h(problem.initial_state)
    counter = 0
    pq = [(h0, 0.0, counter, problem.initial_state, [])]
    best_g: Dict[Any, float] = {problem.initial_state.facts: 0.0}
    nodes_expanded = 0
    nodes_generated = 1

    while pq:
        if nodes_expanded >= max_nodes:
            ms = (time.perf_counter() - t0) * 1000.0
            return SearchResult(success=False, nodes_expanded=nodes_expanded, nodes_generated=nodes_generated,
                                time_ms=ms, ms_per_node=ms / max(1, nodes_expanded), algorithm="A*_hmax",
                                failure_reason="Batas maksimum node tercapai (node limit).")
        if (time.perf_counter() - t0) > timeout_sec:
            ms = (time.perf_counter() - t0) * 1000.0
            return SearchResult(success=False, nodes_expanded=nodes_expanded, nodes_generated=nodes_generated,
                                time_ms=ms, ms_per_node=ms / max(1, nodes_expanded), algorithm="A*_hmax",
                                failure_reason="Waktu pencarian habis (timeout).")

        f_cost, g_cost, _, state, path = heapq.heappop(pq)

        if g_cost > best_g.get(state.facts, float("inf")):
            continue

        nodes_expanded += 1

        if problem.is_goal(state):
            dur = sum(a.duration for a in path)
            ms = (time.perf_counter() - t0) * 1000.0
            return SearchResult(success=True, plan=path, total_cost=g_cost, total_duration=dur,
                                nodes_expanded=nodes_expanded, nodes_generated=nodes_generated,
                                time_ms=ms, ms_per_node=ms / max(1, nodes_expanded), algorithm="A*_hmax")

        for act in problem.actions:
            if not act.is_applicable(state):
                continue
            next_state = act.apply(state)
            nodes_generated += 1
            new_g = g_cost + act.cost

            if new_g < best_g.get(next_state.facts, float("inf")):
                best_g[next_state.facts] = new_g
                h_val = get_h(next_state)
                if math.isinf(h_val):
                    continue
                counter += 1
                heapq.heappush(pq, (new_g + h_val, new_g, counter, next_state, path + [act]))

    ms = (time.perf_counter() - t0) * 1000.0
    return SearchResult(success=False, nodes_expanded=nodes_expanded, nodes_generated=nodes_generated,
                        time_ms=ms, ms_per_node=ms / max(1, nodes_expanded), algorithm="A*_hmax",
                        failure_reason="Ruang pencarian habis tanpa menemukan goal.")


# ==============================================================================
# 4. A* DENGAN h_add (Heuristik Aditif)
# ==============================================================================
def search_astar_hadd(problem: PlanningProblem, max_nodes: int = 40000, timeout_sec: float = 10.0) -> SearchResult:
    t0 = time.perf_counter()
    pre_index = _ensure_pre_index(problem)

    reachable, _, missing = check_relaxed_reachability(problem.initial_state, problem.goal, problem.actions)
    if not reachable:
        ms = (time.perf_counter() - t0) * 1000.0
        return SearchResult(
            success=False, algorithm="A*_hadd", time_ms=ms,
            failure_reason=f"Problem tidak memiliki solusi! Sasaran {missing} mustahil tercapai di dunia saat ini."
        )

    if problem.is_goal(problem.initial_state):
        return SearchResult(success=True, plan=[], total_cost=0.0, algorithm="A*_hadd",
                            time_ms=(time.perf_counter() - t0) * 1000.0)

    h_memo: Dict[Any, float] = {}

    def get_h(s: STRIPSState) -> float:
        k = s.facts
        if k in h_memo:
            return h_memo[k]
        val = h_add(s, problem.goal, problem.actions, pre_index=pre_index)
        h_memo[k] = val
        return val

    h0 = get_h(problem.initial_state)
    counter = 0
    pq = [(h0, 0.0, counter, problem.initial_state, [])]
    best_g: Dict[Any, float] = {problem.initial_state.facts: 0.0}
    nodes_expanded = 0
    nodes_generated = 1

    while pq:
        if nodes_expanded >= max_nodes:
            ms = (time.perf_counter() - t0) * 1000.0
            return SearchResult(success=False, nodes_expanded=nodes_expanded, nodes_generated=nodes_generated,
                                time_ms=ms, ms_per_node=ms / max(1, nodes_expanded), algorithm="A*_hadd",
                                failure_reason="Batas maksimum node tercapai (node limit).")
        if (time.perf_counter() - t0) > timeout_sec:
            ms = (time.perf_counter() - t0) * 1000.0
            return SearchResult(success=False, nodes_expanded=nodes_expanded, nodes_generated=nodes_generated,
                                time_ms=ms, ms_per_node=ms / max(1, nodes_expanded), algorithm="A*_hadd",
                                failure_reason="Waktu pencarian habis (timeout).")

        f_cost, g_cost, _, state, path = heapq.heappop(pq)

        if g_cost > best_g.get(state.facts, float("inf")):
            continue

        nodes_expanded += 1

        if problem.is_goal(state):
            dur = sum(a.duration for a in path)
            ms = (time.perf_counter() - t0) * 1000.0
            return SearchResult(success=True, plan=path, total_cost=g_cost, total_duration=dur,
                                nodes_expanded=nodes_expanded, nodes_generated=nodes_generated,
                                time_ms=ms, ms_per_node=ms / max(1, nodes_expanded), algorithm="A*_hadd")

        for act in problem.actions:
            if not act.is_applicable(state):
                continue
            next_state = act.apply(state)
            nodes_generated += 1
            new_g = g_cost + act.cost

            if new_g < best_g.get(next_state.facts, float("inf")):
                best_g[next_state.facts] = new_g
                h_val = get_h(next_state)
                if math.isinf(h_val):
                    continue
                counter += 1
                heapq.heappush(pq, (new_g + h_val, new_g, counter, next_state, path + [act]))

    ms = (time.perf_counter() - t0) * 1000.0
    return SearchResult(success=False, nodes_expanded=nodes_expanded, nodes_generated=nodes_generated,
                        time_ms=ms, ms_per_node=ms / max(1, nodes_expanded), algorithm="A*_hadd",
                        failure_reason="Ruang pencarian habis tanpa menemukan goal.")


# ==============================================================================
# 5. WEIGHTED A* DENGAN h_FF (Fast-Forward Relaxed Plan)
# ==============================================================================
def search_weighted_astar_hff(problem: PlanningProblem, weight: float = 1.5,
                              use_helpful_actions: bool = True,
                              max_nodes: int = 40000, timeout_sec: float = 4.0) -> SearchResult:
    t0 = time.perf_counter()
    pre_index = _ensure_pre_index(problem)
    loc_map, univ = _build_action_location_index(problem.actions)

    reachable, _, missing = check_relaxed_reachability(problem.initial_state, problem.goal, problem.actions)
    if not reachable:
        ms = (time.perf_counter() - t0) * 1000.0
        return SearchResult(
            success=False, algorithm=f"WA*_hFF(w={weight})", time_ms=ms,
            failure_reason=f"Problem tidak memiliki solusi! Sasaran {missing} mustahil tercapai di dunia saat ini."
        )

    if problem.is_goal(problem.initial_state):
        return SearchResult(success=True, plan=[], total_cost=0.0, algorithm=f"WA*_hFF(w={weight})",
                            time_ms=(time.perf_counter() - t0) * 1000.0)

    h_memo: Dict[Any, Tuple[float, Set[GroundAction]]] = {}

    def get_h(s: STRIPSState) -> Tuple[float, Set[GroundAction]]:
        k = s.facts
        if k in h_memo:
            return h_memo[k]
        val, ha = h_ff(s, problem.goal, problem.actions, pre_index=pre_index)
        h_memo[k] = (val, ha)
        return val, ha

    h0, _ = get_h(problem.initial_state)
    counter = 0
    pq = [(weight * h0, 0.0, counter, problem.initial_state, [])]
    best_g: Dict[Any, float] = {problem.initial_state.facts: 0.0}
    nodes_expanded = 0
    nodes_generated = 1

    while pq:
        if nodes_expanded >= max_nodes:
            ms = (time.perf_counter() - t0) * 1000.0
            return SearchResult(success=False, nodes_expanded=nodes_expanded, nodes_generated=nodes_generated,
                                time_ms=ms, ms_per_node=ms / max(1, nodes_expanded),
                                algorithm=f"WA*_hFF(w={weight})",
                                failure_reason="Batas maksimum node tercapai (node limit).")
        if (time.perf_counter() - t0) > timeout_sec:
            ms = (time.perf_counter() - t0) * 1000.0
            return SearchResult(success=False, nodes_expanded=nodes_expanded, nodes_generated=nodes_generated,
                                time_ms=ms, ms_per_node=ms / max(1, nodes_expanded),
                                algorithm=f"WA*_hFF(w={weight})",
                                failure_reason="Waktu pencarian habis (timeout).")

        f_cost, g_cost, _, state, path = heapq.heappop(pq)

        if g_cost > best_g.get(state.facts, float("inf")):
            continue

        nodes_expanded += 1

        if problem.is_goal(state):
            dur = sum(a.duration for a in path)
            ms = (time.perf_counter() - t0) * 1000.0
            return SearchResult(success=True, plan=path, total_cost=g_cost, total_duration=dur,
                                nodes_expanded=nodes_expanded, nodes_generated=nodes_generated,
                                time_ms=ms, ms_per_node=ms / max(1, nodes_expanded),
                                algorithm=f"WA*_hFF(w={weight})")

        applicable = _get_applicable_actions(state, loc_map, univ, problem.actions)
        if use_helpful_actions:
            _, ha_set = get_h(state)
            if ha_set:
                matched = [a for a in applicable if a in ha_set]
                if matched:
                    non_goto = [a for a in matched if a.name not in ("goto", "goto_through_gate")]
                    if non_goto:
                        applicable = non_goto
                    else:
                        applicable = matched

        for act in applicable:
            next_state = act.apply(state)
            nodes_generated += 1
            new_g = g_cost + act.cost

            if new_g < best_g.get(next_state.facts, float("inf")):
                best_g[next_state.facts] = new_g
                h_val, _ = get_h(next_state)
                if math.isinf(h_val):
                    continue
                counter += 1
                heapq.heappush(pq, (new_g + weight * h_val, new_g, counter, next_state, path + [act]))

    ms = (time.perf_counter() - t0) * 1000.0
    return SearchResult(success=False, nodes_expanded=nodes_expanded, nodes_generated=nodes_generated,
                        time_ms=ms, ms_per_node=ms / max(1, nodes_expanded),
                        algorithm=f"WA*_hFF(w={weight})",
                        failure_reason="Ruang pencarian habis tanpa menemukan goal.")


# ==============================================================================
# 5b. A* DENGAN h_level (Planning Graph Heuristic - Slide 34-35)
# ==============================================================================
def search_astar_hlevel(problem: PlanningProblem, recompute_per_state: bool = False,
                        max_nodes: int = 40000, timeout_sec: float = 10.0) -> SearchResult:
    """
    Pencarian A* menggunakan heuristik level kemunculan goal di Planning Graph (h_level).
    - recompute_per_state=False: menghitung kemunculan fakta sekali dari s0 (cepat, admissible).
    - recompute_per_state=True: membangun planning graph per state (akurasi mutex penuh, overhead waktu).
    """
    t0 = time.perf_counter()
    pre_index = _ensure_pre_index(problem)

    reachable, _, missing = check_relaxed_reachability(problem.initial_state, problem.goal, problem.actions)
    if not reachable:
        ms = (time.perf_counter() - t0) * 1000.0
        return SearchResult(
            success=False, algorithm="A*_hlevel", time_ms=ms,
            failure_reason=f"Problem tidak memiliki solusi! Sasaran {missing} mustahil tercapai di dunia saat ini."
        )

    if problem.is_goal(problem.initial_state):
        return SearchResult(success=True, plan=[], total_cost=0.0, algorithm="A*_hlevel",
                            time_ms=(time.perf_counter() - t0) * 1000.0)

    from planning.planning_graph import PlanningGraph, compute_h_level

    fact_levels: Dict[Any, int] = {}
    if not recompute_per_state:
        # Bangun planning graph dari s0 untuk ekstraksi tingkat kemunculan tiap proposisi (Static Level)
        pg_s0 = PlanningGraph(problem)
        for f in pg_s0.state_levels[0].facts:
            fact_levels[f] = 0

        curr_lvl = 0
        while not pg_s0.leveled_off and curr_lvl < 8:
            if problem.goal <= pg_s0.state_levels[-1].facts:
                break
            expanded = pg_s0.expand_one_level()
            if not expanded:
                break
            curr_lvl += 1
            st = pg_s0.state_levels[-1]
            for f in st.facts:
                if f not in fact_levels:
                    fact_levels[f] = curr_lvl

    h_memo: Dict[Any, float] = {}

    def get_h(s: STRIPSState) -> float:
        k = s.facts
        if k in h_memo:
            return h_memo[k]
        if recompute_per_state:
            if (time.perf_counter() - t0) > timeout_sec:
                return 50.0
            sub_prob = PlanningProblem(
                initial_state=s,
                goal=problem.goal,
                actions=problem.actions,
                problem_name="sub"
            )
            val = compute_h_level(sub_prob, max_levels=8)
            if math.isinf(val):
                val = 50.0
        else:
            unmet = [g for g in problem.goal if not s.has(g)]
            if not unmet:
                val = 0.0
            else:
                val = float(max(fact_levels.get(g, 10) for g in unmet))
        h_memo[k] = val
        return val

    h0 = get_h(problem.initial_state)
    counter = 0
    pq = [(h0, 0.0, counter, problem.initial_state, [])]
    best_g: Dict[Any, float] = {problem.initial_state.facts: 0.0}
    nodes_expanded = 0
    nodes_generated = 1

    while pq:
        if nodes_expanded >= max_nodes:
            ms = (time.perf_counter() - t0) * 1000.0
            return SearchResult(success=False, nodes_expanded=nodes_expanded, nodes_generated=nodes_generated,
                                time_ms=ms, ms_per_node=ms / max(1, nodes_expanded), algorithm="A*_hlevel",
                                failure_reason="Batas maksimum node tercapai (node limit).")

        if (time.perf_counter() - t0) > timeout_sec:
            ms = (time.perf_counter() - t0) * 1000.0
            return SearchResult(success=False, nodes_expanded=nodes_expanded, nodes_generated=nodes_generated,
                                time_ms=ms, ms_per_node=ms / max(1, nodes_expanded), algorithm="A*_hlevel",
                                failure_reason="Waktu pencarian habis (timeout).")

        f_val, g_cost, _, current_state, path = heapq.heappop(pq)

        if g_cost > best_g.get(current_state.facts, float("inf")):
            continue

        nodes_expanded += 1

        if problem.is_goal(current_state):
            ms = (time.perf_counter() - t0) * 1000.0
            tot_dur = sum(a.duration for a in path)
            return SearchResult(
                success=True, plan=path, total_cost=g_cost, total_duration=tot_dur,
                nodes_expanded=nodes_expanded, nodes_generated=nodes_generated,
                time_ms=ms, ms_per_node=ms / max(1, nodes_expanded), algorithm="A*_hlevel"
            )

        for act in problem.actions:
            if (time.perf_counter() - t0) > timeout_sec:
                break
            if not act.is_applicable(current_state):
                continue
            next_state = act.apply(current_state)
            new_g = g_cost + act.cost
            nodes_generated += 1

            if new_g < best_g.get(next_state.facts, float("inf")):
                best_g[next_state.facts] = new_g
                h_val = get_h(next_state)
                counter += 1
                heapq.heappush(pq, (new_g + h_val, new_g, counter, next_state, path + [act]))

    ms = (time.perf_counter() - t0) * 1000.0
    return SearchResult(success=False, nodes_expanded=nodes_expanded, nodes_generated=nodes_generated,
                        time_ms=ms, ms_per_node=ms / max(1, nodes_expanded), algorithm="A*_hlevel",
                        failure_reason="Ruang pencarian habis tanpa menemukan goal.")


# ==============================================================================
# 6. INCREMENTAL STEP PLANNER (FRAME-BUDGETED FOR GAME LOOP < 20 ms)
# ==============================================================================
class IncrementalPlanner:
    """
    Search engine yang dapat dieksekusi secara bertahap (time-sliced) per frame.
    Memastikan frame time maksimal pada main loop selalu < max_frame_ms (default 15 ms).
    """

    def __init__(self, problem: PlanningProblem, weight: float = 2.0,
                 use_helpful_actions: bool = True):
        self.problem = problem
        self.weight = weight
        self.use_helpful_actions = use_helpful_actions
        self.pre_index = _ensure_pre_index(problem)
        self.h_memo: Dict[Any, Tuple[float, Set[GroundAction]]] = {}

        self.reachable, _, self.missing = check_relaxed_reachability(
            problem.initial_state, problem.goal, problem.actions
        )

        self.loc_map, self.univ = _build_action_location_index(problem.actions)
        self.frames_spent = 0
        self.counter = 0
        self.nodes_expanded = 0
        self.nodes_generated = 1
        self.total_search_ms = 0.0

        if not self.reachable:
            self.done = True
            self.result = SearchResult(
                success=False, algorithm=f"Incremental-WA*_hFF",
                failure_reason=f"Problem tidak memiliki solusi! Sasaran {self.missing} mustahil tercapai."
            )
            return

        h0, _ = self._get_h(problem.initial_state)
        self.pq = [(weight * h0, 0.0, self.counter, problem.initial_state, [])]
        self.best_g = {problem.initial_state.facts: 0.0}
        self.done = False
        self.result = None

    def _get_h(self, s: STRIPSState) -> Tuple[float, Set[GroundAction]]:
        k = s.facts
        if k in self.h_memo:
            return self.h_memo[k]
        val, ha = h_ff(s, self.problem.goal, self.problem.actions, pre_index=self.pre_index)
        self.h_memo[k] = (val, ha)
        return val, ha

    def step(self, max_frame_ms: float = 15.0) -> Tuple[bool, Optional[SearchResult]]:
        """
        Menjalankan pencarian maksimal selama max_frame_ms.
        Mengembalikan (is_done, SearchResult).
        """
        if self.done:
            return True, self.result

        self.frames_spent += 1
        t_start = time.perf_counter()

        while self.pq:
            # Periksa anggaran waktu frame
            elapsed_ms = (time.perf_counter() - t_start) * 1000.0
            if elapsed_ms >= max_frame_ms:
                self.total_search_ms += elapsed_ms
                return False, None

            f_cost, g_cost, _, state, path = heapq.heappop(self.pq)

            if g_cost > self.best_g.get(state.facts, float("inf")):
                continue

            self.nodes_expanded += 1

            if self.problem.is_goal(state):
                self.done = True
                elapsed_ms = (time.perf_counter() - t_start) * 1000.0
                self.total_search_ms += elapsed_ms
                dur = sum(a.duration for a in path)
                self.result = SearchResult(
                    success=True, plan=path, total_cost=g_cost, total_duration=dur,
                    nodes_expanded=self.nodes_expanded, nodes_generated=self.nodes_generated,
                    time_ms=self.total_search_ms,
                    ms_per_node=self.total_search_ms / max(1, self.nodes_expanded),
                    algorithm="Incremental-WA*_hFF"
                )
                return True, self.result

            applicable = _get_applicable_actions(state, self.loc_map, self.univ, self.problem.actions)
            if self.use_helpful_actions:
                _, ha_set = self._get_h(state)
                if ha_set:
                    matched = [a for a in applicable if a in ha_set]
                    if matched:
                        non_goto = [a for a in matched if a.name not in ("goto", "goto_through_gate")]
                        if non_goto:
                            applicable = non_goto
                        else:
                            applicable = matched

            for act in applicable:
                next_state = act.apply(state)
                self.nodes_generated += 1
                new_g = g_cost + act.cost

                if new_g < self.best_g.get(next_state.facts, float("inf")):
                    self.best_g[next_state.facts] = new_g
                    h_val, _ = self._get_h(next_state)
                    if math.isinf(h_val):
                        continue
                    self.counter += 1
                    heapq.heappush(self.pq, (new_g + self.weight * h_val, new_g, self.counter, next_state, path + [act]))

        self.done = True
        elapsed_ms = (time.perf_counter() - t_start) * 1000.0
        self.total_search_ms += elapsed_ms
        self.result = SearchResult(
            success=False, nodes_expanded=self.nodes_expanded, nodes_generated=self.nodes_generated,
            time_ms=self.total_search_ms, ms_per_node=self.total_search_ms / max(1, self.nodes_expanded),
            algorithm="Incremental-WA*_hFF", failure_reason="Ruang pencarian habis tanpa menemukan goal."
        )
        return True, self.result


# ==============================================================================
# UNIFIED SOLVER API
# ==============================================================================
def solve(problem: PlanningProblem, algorithm: str = "weighted_astar_hff",
          weight: float = 1.5, max_nodes: int = 40000, timeout_sec: float = 10.0) -> SearchResult:
    algo = algorithm.lower().strip()
    if algo == "bfs":
        return search_bfs(problem, max_nodes=max_nodes, timeout_sec=timeout_sec)
    elif algo in ("ucs", "dijkstra"):
        return search_ucs(problem, max_nodes=max_nodes, timeout_sec=timeout_sec)
    elif algo in ("astar_hmax", "a*_hmax", "hmax"):
        return search_astar_hmax(problem, max_nodes=max_nodes, timeout_sec=timeout_sec)
    elif algo in ("astar_hadd", "a*_hadd", "hadd"):
        return search_astar_hadd(problem, max_nodes=max_nodes, timeout_sec=timeout_sec)
    elif algo in ("weighted_astar_hff", "wa*_hff", "hff", "fastforward"):
        return search_weighted_astar_hff(problem, weight=weight, max_nodes=max_nodes, timeout_sec=timeout_sec)
    else:
        raise ValueError(f"Algoritma '{algorithm}' tidak dikenal!")
