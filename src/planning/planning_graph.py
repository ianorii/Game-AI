"""
planning_graph.py - Planning Graph & Mutex Reasoning (Sesuai Materi Kuliah Slide 31-35)

Menerapkan:
  - Struktur berlapapis berselang-seling: S0, A0, S1, A1, S2, ...
  - Persistence / No-Op untuk tiap fakta pada state level
  - Action Mutex (A_i):
      1. Inconsistent Effects: del(a) beririsan dengan add(b) atau sebaliknya
      2. Interference: del(a) beririsan dengan pre(b) atau sebaliknya
      3. Competing Needs: ada p in pre(a), q in pre(b) yang mutex pada S_i
  - Fact Mutex (S_{i+1}):
      Inconsistent Support: setiap aksi yang menambah p mutex dengan setiap aksi yang menambah q
  - Heuristik h_level: level pertama di mana seluruh goal ada tanpa mutex
  - Ekstraksi Rencana GraphPlan (Blum & Furst 1997)
"""

import time
from dataclasses import dataclass, field
from typing import List, Set, Tuple, Dict, Optional, FrozenSet, Any

from planning.strips import Predicate, STRIPSState, GroundAction, PlanningProblem, PlanValidator
from planning.planner import SearchResult


@dataclass(frozen=True)
class PGAction:
    """Representasi aksi dalam Planning Graph (termasuk No-Op)."""
    name: str
    params: Tuple[str, ...]
    preconditions: FrozenSet[Predicate]
    add_effects: FrozenSet[Predicate]
    delete_effects: FrozenSet[Predicate]
    is_noop: bool = False
    original_action: Optional[GroundAction] = None

    @property
    def signature(self) -> str:
        if self.is_noop:
            p = next(iter(self.add_effects)) if self.add_effects else ""
            return f"no-op({p})"
        if not self.params:
            return self.name
        return f"{self.name}({', '.join(self.params)})"

    def __repr__(self) -> str:
        return self.signature


@dataclass
class StateLevel:
    level: int
    facts: Set[Predicate]
    mutex_pairs: Set[Tuple[Predicate, Predicate]] = field(default_factory=set)

    def is_mutex(self, p1: Predicate, p2: Predicate) -> bool:
        return (p1, p2) in self.mutex_pairs or (p2, p1) in self.mutex_pairs


@dataclass
class ActionLevel:
    level: int
    actions: List[PGAction]
    mutex_pairs: Set[Tuple[PGAction, PGAction]] = field(default_factory=set)

    def is_mutex(self, a1: PGAction, a2: PGAction) -> bool:
        return (a1, a2) in self.mutex_pairs or (a2, a1) in self.mutex_pairs


class PlanningGraph:
    """
    Mesin Planning Graph dengan inferensi relasi Mutual Exclusion (Mutex).
    """

    def __init__(self, problem: PlanningProblem):
        self.problem = problem
        self.state_levels: List[StateLevel] = []
        self.action_levels: List[ActionLevel] = []
        self.leveled_off = False

        # Identifikasi predikat statis (Slide 34)
        dynamic_preds = set()
        for a in problem.actions:
            for p in a.add_effects: dynamic_preds.add(p.name)
            for p in a.delete_effects: dynamic_preds.add(p.name)
        all_preds = {p.name for a in problem.actions for p in a.preconditions}
        self.static_preds = all_preds - dynamic_preds

        # Inisialisasi S0 HANYA dengan fakta dinamis (Slide 34)
        s0_facts = {p for p in problem.initial_state.facts if p.name not in self.static_preds}
        self.state_levels.append(StateLevel(level=0, facts=s0_facts, mutex_pairs=set()))

    def expand_one_level(self) -> bool:
        """
        Mengekspansi satu tingkat: S_i -> A_i -> S_{i+1}.
        Mengembalikan True jika graph bertambah, False jika mendatar (leveled off).
        """
        curr_state_idx = len(self.state_levels) - 1
        curr_state = self.state_levels[curr_state_idx]

        # 1. Bangun A_i
        applicable_actions: List[PGAction] = []

        # Aksi nyata dari domain
        for ga in self.problem.actions:
            # Prasyarat statis diverifikasi terhadap initial state (Slide 34)
            static_pre = {p for p in ga.preconditions if p.name in self.static_preds}
            if not static_pre <= self.problem.initial_state.facts:
                continue

            # Prasyarat dinamis diverifikasi terhadap S_i
            dyn_pre = {p for p in ga.preconditions if p.name not in self.static_preds}
            if not dyn_pre <= curr_state.facts:
                continue

            # Tidak boleh ada sepasang dynamic precondition yang mutex di S_i
            dyn_pre_list = list(dyn_pre)
            has_mutex_pre = False
            for i in range(len(dyn_pre_list)):
                for j in range(i + 1, len(dyn_pre_list)):
                    if curr_state.is_mutex(dyn_pre_list[i], dyn_pre_list[j]):
                        has_mutex_pre = True
                        break
                if has_mutex_pre:
                    break
            if not has_mutex_pre:
                pga = PGAction(
                    name=ga.name,
                    params=ga.params,
                    preconditions=frozenset(dyn_pre),
                    add_effects=ga.add_effects,
                    delete_effects=ga.delete_effects,
                    is_noop=False,
                    original_action=ga
                )
                applicable_actions.append(pga)

        # Tambahkan no-op (persistence) untuk setiap fakta di S_i
        for f in curr_state.facts:
            noop = PGAction(
                name=f"no-op_{f.name}",
                params=f.args,
                preconditions=frozenset([f]),
                add_effects=frozenset([f]),
                delete_effects=frozenset(),
                is_noop=True,
                original_action=None
            )
            applicable_actions.append(noop)

        # 2. Hitung Mutex antar Aksi di A_i
        action_mutexes: Set[Tuple[PGAction, PGAction]] = set()
        n_act = len(applicable_actions)
        for i in range(n_act):
            a1 = applicable_actions[i]
            for j in range(i + 1, n_act):
                a2 = applicable_actions[j]

                # (1) Inconsistent Effects: del(a1) ∩ add(a2) != ∅ atau sebaliknya
                if (a1.delete_effects & a2.add_effects) or (a2.delete_effects & a1.add_effects):
                    action_mutexes.add((a1, a2))
                    continue

                # (2) Interference: del(a1) ∩ pre(a2) != ∅ atau sebaliknya
                if (a1.delete_effects & a2.preconditions) or (a2.delete_effects & a1.preconditions):
                    action_mutexes.add((a1, a2))
                    continue

                # (3) Competing Needs: ada p in pre(a1) dan q in pre(a2) yang mutex di S_i
                competing = False
                for p in a1.preconditions:
                    for q in a2.preconditions:
                        if curr_state.is_mutex(p, q):
                            competing = True
                            break
                    if competing:
                        break
                if competing:
                    action_mutexes.add((a1, a2))

        act_level = ActionLevel(level=curr_state_idx, actions=applicable_actions, mutex_pairs=action_mutexes)
        self.action_levels.append(act_level)

        # 3. Bangun S_{i+1}
        next_facts: Set[Predicate] = set()
        adders_by_fact: Dict[Predicate, List[PGAction]] = {}

        for a in applicable_actions:
            for eff in a.add_effects:
                next_facts.add(eff)
                adders_by_fact.setdefault(eff, []).append(a)

        # 4. Hitung Mutex antar Fakta di S_{i+1} (Inconsistent Support)
        fact_mutexes: Set[Tuple[Predicate, Predicate]] = set()
        fact_list = list(next_facts)
        n_facts = len(fact_list)

        for i in range(n_facts):
            p = fact_list[i]
            adders_p = adders_by_fact.get(p, [])
            for j in range(i + 1, n_facts):
                q = fact_list[j]
                adders_q = adders_by_fact.get(q, [])

                # Dua fakta mutex jika SETIAP aksi yang menambah p mutex dengan SETIAP aksi yang menambah q
                all_mutex = True
                for ap in adders_p:
                    for aq in adders_q:
                        if ap == aq:
                            # Aksi yang sama menambah p dan q sekaligus -> tidak mutex!
                            all_mutex = False
                            break
                        if not act_level.is_mutex(ap, aq):
                            # Ditemukan pasangan aksi non-mutex yang mendukung p dan q -> tidak mutex!
                            all_mutex = False
                            break
                    if not all_mutex:
                        break

                if all_mutex:
                    fact_mutexes.add((p, q))

        next_state = StateLevel(level=curr_state_idx + 1, facts=next_facts, mutex_pairs=fact_mutexes)
        self.state_levels.append(next_state)

        # Cek leveling off: fakta sama persis dan mutex fakta sama persis
        if (next_facts == curr_state.facts and
                len(fact_mutexes) == len(curr_state.mutex_pairs) and
                fact_mutexes == curr_state.mutex_pairs):
            self.leveled_off = True
            return False

        return True

    def build_until_goal_or_level_off(self, max_levels: int = 20) -> int:
        """
        Membangun graph hingga semua sasaran muncul tanpa mutex atau hingga graph mendatar.
        Mengembalikan indeks level pertama yang memenuhi sasaran (atau -1 jika gagal).
        """
        goal_set = self.problem.goal

        for lvl in range(max_levels):
            curr_state = self.state_levels[-1]
            # Cek apakah sasaran ada dan bebas mutex
            if goal_set <= curr_state.facts:
                goal_list = list(goal_set)
                has_mutex = False
                for i in range(len(goal_list)):
                    for j in range(i + 1, len(goal_list)):
                        if curr_state.is_mutex(goal_list[i], goal_list[j]):
                            has_mutex = True
                            break
                    if has_mutex:
                        break
                if not has_mutex:
                    return curr_state.level

            if self.leveled_off:
                break

            changed = self.expand_one_level()
            if not changed:
                break

        # Evaluasi akhir di level puncak
        final_state = self.state_levels[-1]
        if goal_set <= final_state.facts:
            goal_list = list(goal_set)
            has_mutex = False
            for i in range(len(goal_list)):
                for j in range(i + 1, len(goal_list)):
                    if final_state.is_mutex(goal_list[i], goal_list[j]):
                        has_mutex = True
                        break
                if has_mutex:
                    break
            if not has_mutex:
                return final_state.level

        return -1


def compute_h_level(problem: PlanningProblem, max_levels: int = 15) -> float:
    """
    Menghitung Heuristik h_level:
    Level pertama S_i tempat seluruh fakta sasaran muncul tanpa pasangan mutex.
    Bersifat admissible (tidak pernah over-estimasi jarak langkah paralel).
    """
    pg = PlanningGraph(problem)
    lvl = pg.build_until_goal_or_level_off(max_levels=max_levels)
    if lvl >= 0:
        return float(lvl)
    return float("inf")


def extract_graphplan(pg: PlanningGraph, max_levels: int = 15) -> Optional[List[GroundAction]]:
    """
    Ekstraksi rencana GraphPlan klasik (Blum & Furst 1997) menggunakan pencarian mundur
    antar tingkat Planning Graph.
    """
    target_level = pg.build_until_goal_or_level_off(max_levels=max_levels)
    if target_level < 0:
        return None

    goal_set = pg.problem.goal

    def search_level(lvl: int, subgoals: FrozenSet[Predicate]) -> Optional[List[GroundAction]]:
        if lvl == 0:
            if subgoals <= pg.state_levels[0].facts:
                return []
            return None

        act_level = pg.action_levels[lvl - 1]
        sg_list = list(subgoals)

        # Cari kombinasi aksi non-mutex di A_{lvl-1} yang mencakup subgoals
        def find_action_cover(remaining_goals: List[Predicate],
                              chosen_actions: List[PGAction]) -> Optional[List[GroundAction]]:
            if not remaining_goals:
                # Kumpulkan seluruh precondition dari aksi yang dipilih sebagai subgoal baru
                next_subgoals = set()
                for a in chosen_actions:
                    next_subgoals.update(a.preconditions)
                # Rekursif ke level sebelumnya
                plan_prefix = search_level(lvl - 1, frozenset(next_subgoals))
                if plan_prefix is not None:
                    # Ambil aksi konkret (kecuali no-op)
                    step_acts = [a.original_action for a in chosen_actions if not a.is_noop and a.original_action]
                    return plan_prefix + step_acts
                return None

            curr_g = remaining_goals[0]
            # Cari aksi yang menambahkan curr_g
            candidates = [a for a in act_level.actions if curr_g in a.add_effects]

            for cand in candidates:
                # Periksa apakah cand mutex dengan aksi yang sudah dipilih di level ini
                conflict = False
                for ca in chosen_actions:
                    if act_level.is_mutex(cand, ca):
                        conflict = True
                        break
                if conflict:
                    continue

                # Saring sisa goals yang belum tercakup oleh aksi terpilih
                new_chosen = chosen_actions + [cand]
                covered = set()
                for a in new_chosen:
                    covered.update(a.add_effects)
                rest_goals = [g for g in remaining_goals[1:] if g not in covered]

                res = find_action_cover(rest_goals, new_chosen)
                if res is not None:
                    return res

            return None

        return find_action_cover(sg_list, [])

    while target_level < len(pg.state_levels):
        plan = search_level(target_level, goal_set)
        if plan is not None:
            return plan
        # Jika gagal ekstraksi pada target_level, ekspansi level berikutnya
        if pg.leveled_off:
            break
        changed = pg.expand_one_level()
        if not changed:
            break
        target_level += 1

    return None

