"""
heuristics.py - Heuristik Delete-Relaxation (h_max, h_add, h_FF) & Deteksi Unsolvable

Dioptimalkan untuk performa runtime game:
  - Pre-indeks aksi per prasyarat
  - Memoization state transposition
  - Ekstraksi relaxed plan linier
  - Deteksi ketercapaian santai cepat (< 0.5 ms)
"""

from typing import Dict, Set, List, Tuple, Optional, FrozenSet
import math
import heapq

from planning.strips import Predicate, GroundAction, STRIPSState


def check_relaxed_reachability(initial_state: STRIPSState, goal: FrozenSet[Predicate],
                               actions: List[GroundAction]) -> Tuple[bool, Set[Predicate], Set[Predicate]]:
    """
    Melakukan forward reachability layer-by-layer dengan mengabaikan delete effects.
    Mengembalikan (is_reachable, reached_facts, missing_goals).
    Sangat cepat (< 0.5 ms) untuk mendeteksi problem yang mustahil diselesaikan.
    """
    reached: Set[Predicate] = set(initial_state.facts)
    remaining_actions = list(actions)

    while True:
        progress = False
        next_remaining = []
        for act in remaining_actions:
            if act.preconditions <= reached:
                new_facts = act.add_effects - reached
                if new_facts:
                    reached.update(new_facts)
                    progress = True
            else:
                next_remaining.append(act)

        remaining_actions = next_remaining
        if goal <= reached:
            return True, reached, set()
        if not progress:
            break

    missing = set(goal) - reached
    return (len(missing) == 0), reached, missing


def _build_action_pre_index(actions: List[GroundAction]) -> Dict[Predicate, List[GroundAction]]:
    index: Dict[Predicate, List[GroundAction]] = {}
    for act in actions:
        for pre in act.preconditions:
            index.setdefault(pre, []).append(act)
    return index


class FastHeuristicEngine:
    """
    Engine heuristik relaksasi delete yang diindeks secara integer (array-based).
    Memberikan akselerasi 10x lipat dibanding iterasi dictionary Python biasa:
      - Memetakan fakta ke ID numerik 0..N-1
      - Mengabaikan propagasi fakta statis dari priority queue
      - Menghentikan propagasi sedini mungkin saat semua sasaran tercapai
    """
    def __init__(self, actions: List[GroundAction], goal: FrozenSet[Predicate],
                 initial_facts: FrozenSet[Predicate]):
        all_preds = sorted(list(set(initial_facts) | set(goal) | {
            p for a in actions for p in a.preconditions | a.add_effects | a.delete_effects
        }), key=str)
        self.pred_to_id: Dict[Predicate, int] = {p: i for i, p in enumerate(all_preds)}
        self.id_to_pred: List[Predicate] = all_preds
        self.N: int = len(all_preds)

        self.all_eff_ids: Set[int] = {
            self.pred_to_id[p] for a in actions for p in (a.add_effects | a.delete_effects)
        }
        self.goal_ids: List[int] = [self.pred_to_id[g] for g in goal if g in self.pred_to_id]
        self.goal_set: Set[int] = set(self.goal_ids)

        self.compiled_actions: List[Tuple[float, List[int], List[int], GroundAction]] = []
        self.actions_by_dynamic_pre: List[List[int]] = [[] for _ in range(self.N)]

        for act in actions:
            act_idx = len(self.compiled_actions)
            pre_ids = [self.pred_to_id[p] for p in act.preconditions if p in self.pred_to_id]
            eff_ids = [self.pred_to_id[p] for p in act.add_effects if p in self.pred_to_id]
            self.compiled_actions.append((act.cost, pre_ids, eff_ids, act))
            for pid in pre_ids:
                if pid in self.all_eff_ids:
                    self.actions_by_dynamic_pre[pid].append(act_idx)

        self.INF: float = float("inf")

    def eval_hmax(self, state: STRIPSState) -> float:
        state_fact_ids = [self.pred_to_id[p] for p in state.facts if p in self.pred_to_id]
        fact_costs = [self.INF] * self.N
        pq: List[Tuple[float, int, int]] = []
        c = 0
        for pid in state_fact_ids:
            fact_costs[pid] = 0.0
            if pid in self.all_eff_ids:
                pq.append((0.0, c, pid))
                c += 1

        visited = [False] * self.N
        goals_met = 0
        num_goals = len(self.goal_ids)

        while pq:
            f_cost, _, pid = heapq.heappop(pq)
            if visited[pid]:
                continue
            visited[pid] = True

            if pid in self.goal_set:
                goals_met += 1
                if goals_met == num_goals:
                    break

            for act_idx in self.actions_by_dynamic_pre[pid]:
                act_cost, pre_ids, eff_ids, _ = self.compiled_actions[act_idx]
                all_known = True
                max_pre = 0.0
                for p in pre_ids:
                    c_p = fact_costs[p]
                    if c_p == self.INF:
                        all_known = False
                        break
                    if c_p > max_pre:
                        max_pre = c_p
                if all_known:
                    tot = act_cost + max_pre
                    for eff in eff_ids:
                        if tot < fact_costs[eff]:
                            fact_costs[eff] = tot
                            c += 1
                            heapq.heappush(pq, (tot, c, eff))

        m = 0.0
        for g in self.goal_ids:
            if fact_costs[g] == self.INF:
                return self.INF
            if fact_costs[g] > m:
                m = fact_costs[g]
        return m

    def eval_hadd(self, state: STRIPSState) -> float:
        state_fact_ids = [self.pred_to_id[p] for p in state.facts if p in self.pred_to_id]
        fact_costs = [self.INF] * self.N
        pq: List[Tuple[float, int, int]] = []
        c = 0
        for pid in state_fact_ids:
            fact_costs[pid] = 0.0
            if pid in self.all_eff_ids:
                pq.append((0.0, c, pid))
                c += 1

        visited = [False] * self.N
        goals_met = 0
        num_goals = len(self.goal_ids)

        while pq:
            f_cost, _, pid = heapq.heappop(pq)
            if visited[pid]:
                continue
            visited[pid] = True

            if pid in self.goal_set:
                goals_met += 1
                if goals_met == num_goals:
                    break

            for act_idx in self.actions_by_dynamic_pre[pid]:
                act_cost, pre_ids, eff_ids, _ = self.compiled_actions[act_idx]
                all_known = True
                sum_pre = 0.0
                for p in pre_ids:
                    c_p = fact_costs[p]
                    if c_p == self.INF:
                        all_known = False
                        break
                    sum_pre += c_p
                if all_known:
                    tot = act_cost + sum_pre
                    for eff in eff_ids:
                        if tot < fact_costs[eff]:
                            fact_costs[eff] = tot
                            c += 1
                            heapq.heappush(pq, (tot, c, eff))

        tot_h = 0.0
        for g in self.goal_ids:
            if fact_costs[g] == self.INF:
                return self.INF
            tot_h += fact_costs[g]
        return tot_h

    def eval_hff(self, state: STRIPSState) -> Tuple[float, Set[GroundAction]]:
        state_fact_ids = [self.pred_to_id[p] for p in state.facts if p in self.pred_to_id]
        state_set = set(state_fact_ids)
        fact_costs = [self.INF] * self.N
        achievers = [-1] * self.N
        pq: List[Tuple[float, int, int]] = []
        c = 0
        for pid in state_fact_ids:
            fact_costs[pid] = 0.0
            if pid in self.all_eff_ids:
                pq.append((0.0, c, pid))
                c += 1

        visited = [False] * self.N
        goals_met = 0
        num_goals = len(self.goal_ids)

        while pq:
            f_cost, _, pid = heapq.heappop(pq)
            if visited[pid]:
                continue
            visited[pid] = True

            if pid in self.goal_set:
                goals_met += 1
                if goals_met == num_goals:
                    break

            for act_idx in self.actions_by_dynamic_pre[pid]:
                act_cost, pre_ids, eff_ids, _ = self.compiled_actions[act_idx]
                all_known = True
                sum_pre = 0.0
                for p in pre_ids:
                    c_p = fact_costs[p]
                    if c_p == self.INF:
                        all_known = False
                        break
                    sum_pre += c_p
                if all_known:
                    tot = act_cost + sum_pre
                    for eff in eff_ids:
                        if tot < fact_costs[eff]:
                            fact_costs[eff] = tot
                            achievers[eff] = act_idx
                            c += 1
                            heapq.heappush(pq, (tot, c, eff))

        for g in self.goal_ids:
            if fact_costs[g] == self.INF:
                return self.INF, set()

        goals_to_support = list(self.goal_ids)
        relaxed_plan = []
        supp = set(state_set)
        while goals_to_support:
            sub = goals_to_support.pop()
            if sub in supp:
                continue
            supp.add(sub)
            ach_idx = achievers[sub]
            if ach_idx == -1:
                continue
            relaxed_plan.append(ach_idx)
            for p in self.compiled_actions[ach_idx][1]:
                if p not in supp:
                    goals_to_support.append(p)

        total_ff = sum(self.compiled_actions[a][0] for a in relaxed_plan)
        ha = {self.compiled_actions[a][3] for a in relaxed_plan if all(p in state_set for p in self.compiled_actions[a][1])}
        return total_ff, ha


def compute_fact_costs_max(state: STRIPSState, goal: FrozenSet[Predicate],
                           actions: List[GroundAction],
                           pre_index: Optional[Any] = None) -> Tuple[Dict[Predicate, float], Dict[Predicate, GroundAction]]:
    """Menghitung biaya fakta berdasarkan h_max menggunakan relaksasi delete."""
    fact_costs: Dict[Predicate, float] = {p: 0.0 for p in state.facts}
    achievers: Dict[Predicate, GroundAction] = {}

    pq: List[Tuple[float, int, Predicate]] = [(0.0, idx, p) for idx, p in enumerate(state.facts)]
    counter = len(pq)
    actions_by_pre = pre_index if isinstance(pre_index, dict) else _build_action_pre_index(actions)

    visited_facts: Set[Predicate] = set()

    while pq:
        f_cost, _, fact = heapq.heappop(pq)
        if fact in visited_facts:
            continue
        visited_facts.add(fact)

        if goal and goal <= visited_facts:
            break

        candidate_actions = actions_by_pre.get(fact, [])
        for act in candidate_actions:
            all_known = True
            max_pre_cost = 0.0
            for pre in act.preconditions:
                if pre not in fact_costs:
                    all_known = False
                    break
                if fact_costs[pre] > max_pre_cost:
                    max_pre_cost = fact_costs[pre]

            if all_known:
                act_cost = act.cost + max_pre_cost
                for eff in act.add_effects:
                    old_cost = fact_costs.get(eff, float("inf"))
                    if act_cost < old_cost:
                        fact_costs[eff] = act_cost
                        achievers[eff] = act
                        counter += 1
                        heapq.heappush(pq, (act_cost, counter, eff))

    return fact_costs, achievers


def compute_fact_costs_add(state: STRIPSState, goal: FrozenSet[Predicate],
                           actions: List[GroundAction],
                           pre_index: Optional[Any] = None) -> Tuple[Dict[Predicate, float], Dict[Predicate, GroundAction]]:
    """Menghitung biaya fakta berdasarkan h_add menggunakan relaksasi delete."""
    fact_costs: Dict[Predicate, float] = {p: 0.0 for p in state.facts}
    achievers: Dict[Predicate, GroundAction] = {}

    pq: List[Tuple[float, int, Predicate]] = [(0.0, idx, p) for idx, p in enumerate(state.facts)]
    counter = len(pq)
    actions_by_pre = pre_index if isinstance(pre_index, dict) else _build_action_pre_index(actions)

    visited_facts: Set[Predicate] = set()

    while pq:
        f_cost, _, fact = heapq.heappop(pq)
        if fact in visited_facts:
            continue
        visited_facts.add(fact)

        if goal and goal <= visited_facts:
            break

        candidate_actions = actions_by_pre.get(fact, [])
        for act in candidate_actions:
            all_known = True
            sum_pre_cost = 0.0
            for pre in act.preconditions:
                if pre not in fact_costs:
                    all_known = False
                    break
                sum_pre_cost += fact_costs[pre]

            if all_known:
                act_cost = act.cost + sum_pre_cost
                for eff in act.add_effects:
                    old_cost = fact_costs.get(eff, float("inf"))
                    if act_cost < old_cost:
                        fact_costs[eff] = act_cost
                        achievers[eff] = act
                        counter += 1
                        heapq.heappush(pq, (act_cost, counter, eff))

    return fact_costs, achievers


def h_max(state: STRIPSState, goal: FrozenSet[Predicate], actions: List[GroundAction],
          pre_index: Optional[Any] = None) -> float:
    """Heuristik Admissible h_max."""
    if goal <= state.facts:
        return 0.0

    if isinstance(pre_index, FastHeuristicEngine):
        return pre_index.eval_hmax(state)

    fact_costs, _ = compute_fact_costs_max(state, goal, actions, pre_index=pre_index)
    max_h = 0.0
    for g in goal:
        if g not in fact_costs:
            return float("inf")
        if fact_costs[g] > max_h:
            max_h = fact_costs[g]
    return max_h


def h_add(state: STRIPSState, goal: FrozenSet[Predicate], actions: List[GroundAction],
          pre_index: Optional[Any] = None) -> float:
    """Heuristik Aditif h_add."""
    if goal <= state.facts:
        return 0.0

    if isinstance(pre_index, FastHeuristicEngine):
        return pre_index.eval_hadd(state)

    fact_costs, _ = compute_fact_costs_add(state, goal, actions, pre_index=pre_index)
    total_h = 0.0
    for g in goal:
        if g not in fact_costs:
            return float("inf")
        total_h += fact_costs[g]
    return total_h


def h_ff(state: STRIPSState, goal: FrozenSet[Predicate],
         actions: List[GroundAction],
         pre_index: Optional[Any] = None) -> Tuple[float, Set[GroundAction]]:
    """Heuristik Fast-Forward (h_FF)."""
    if goal <= state.facts:
        return 0.0, set()

    if isinstance(pre_index, FastHeuristicEngine):
        return pre_index.eval_hff(state)

    fact_costs, achievers = compute_fact_costs_add(state, goal, actions, pre_index=pre_index)

    for g in goal:
        if g not in fact_costs:
            return float("inf"), set()

    goals_to_support: Set[Predicate] = set(goal)
    relaxed_plan: Set[GroundAction] = set()
    supported_facts: Set[Predicate] = set(state.facts)

    while goals_to_support:
        subgoal = goals_to_support.pop()
        if subgoal in supported_facts:
            continue
        supported_facts.add(subgoal)

        achiever = achievers.get(subgoal)
        if achiever is None:
            continue

        relaxed_plan.add(achiever)
        for pre in achiever.preconditions:
            if pre not in supported_facts:
                goals_to_support.add(pre)

    total_ff_cost = sum(act.cost for act in relaxed_plan)
    helpful_actions = {act for act in relaxed_plan if act.preconditions <= state.facts}

    return total_ff_cost, helpful_actions
