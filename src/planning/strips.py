"""
strips.py - Data Struktur STRIPS & Validator Rencana

Menyediakan:
  - Predicate: fakta atomik (nama, argumen)
  - GroundAction: aksi konkret terikat objek dengan precond, add, del, dan real cost
  - STRIPSState: representasi state murni (frozenset dari fakta)
  - PlanningProblem: deskripsi problem STRIPS
  - PlanValidator: simulator verifikasi keabsahan rencana
"""

from dataclasses import dataclass, field
from typing import Tuple, FrozenSet, List, Set, Optional, Dict, Any


@dataclass(frozen=True)
class Predicate:
    name: str
    args: Tuple[str, ...] = field(default_factory=tuple)

    def __repr__(self) -> str:
        if not self.args:
            return f"({self.name})"
        return f"({self.name} {' '.join(self.args)})"

    @classmethod
    def from_tuple(cls, t: Tuple[Any, ...]) -> "Predicate":
        if not t:
            raise ValueError("Tuple fakta tidak boleh kosong!")
        return cls(name=str(t[0]), args=tuple(str(x) for x in t[1:]))

    def to_tuple(self) -> Tuple[str, ...]:
        return (self.name,) + self.args


@dataclass(frozen=True)
class STRIPSState:
    facts: FrozenSet[Predicate]

    def has(self, pred: Predicate) -> bool:
        return pred in self.facts

    def satisfies(self, conditions: FrozenSet[Predicate]) -> bool:
        return conditions <= self.facts

    def apply(self, add_effects: FrozenSet[Predicate], del_effects: FrozenSet[Predicate]) -> "STRIPSState":
        new_facts = (self.facts - del_effects) | add_effects
        return STRIPSState(facts=frozenset(new_facts))

    def __len__(self) -> int:
        return len(self.facts)

    def __iter__(self):
        return iter(self.facts)


@dataclass(frozen=True)
class GroundAction:
    name: str
    params: Tuple[str, ...]
    preconditions: FrozenSet[Predicate]
    add_effects: FrozenSet[Predicate]
    delete_effects: FrozenSet[Predicate]
    cost: float = 1.0
    duration: float = 1.0
    action_type: str = "generic"

    def is_applicable(self, state: STRIPSState) -> bool:
        return self.preconditions <= state.facts

    def apply(self, state: STRIPSState) -> STRIPSState:
        return state.apply(self.add_effects, self.delete_effects)

    @property
    def signature(self) -> str:
        if not self.params:
            return self.name
        return f"{self.name}({', '.join(self.params)})"

    def __repr__(self) -> str:
        return f"Action<{self.signature}, cost={self.cost:.2f}s>"


@dataclass
class PlanningProblem:
    initial_state: STRIPSState
    goal: FrozenSet[Predicate]
    actions: List[GroundAction]
    domain_name: str = "dungeon-expedition"
    problem_name: str = "expedition-problem"

    def is_goal(self, state: STRIPSState) -> bool:
        return self.goal <= state.facts


@dataclass
class PlanStepResult:
    step_index: int
    action_signature: str
    cost: float
    duration: float
    preconditions_met: bool
    missing_preconditions: List[str]
    resulting_facts_count: int


@dataclass
class ValidationReport:
    valid: bool
    total_cost: float
    total_duration: float
    steps: List[PlanStepResult]
    goal_reached: bool
    missing_goals: List[str]
    message: str


class PlanValidator:
    """
    Memvalidasi rencana aksi pada state STRIPS murni.
    Memverifikasi setiap langkah memenuhi precondition dan state akhir memenuhi goal.
    """

    @staticmethod
    def validate(problem: PlanningProblem, plan: List[GroundAction]) -> ValidationReport:
        current_state = problem.initial_state
        step_results = []
        total_cost = 0.0
        total_duration = 0.0

        for idx, act in enumerate(plan, start=1):
            total_cost += act.cost
            total_duration += act.duration

            unmet = [str(p) for p in act.preconditions if not current_state.has(p)]
            preconds_ok = (len(unmet) == 0)

            if not preconds_ok:
                step_results.append(PlanStepResult(
                    step_index=idx,
                    action_signature=act.signature,
                    cost=act.cost,
                    duration=act.duration,
                    preconditions_met=False,
                    missing_preconditions=unmet,
                    resulting_facts_count=len(current_state)
                ))
                return ValidationReport(
                    valid=False,
                    total_cost=total_cost,
                    total_duration=total_duration,
                    steps=step_results,
                    goal_reached=False,
                    missing_goals=[str(g) for g in problem.goal if not current_state.has(g)],
                    message=f"Langkah {idx} '{act.signature}' gagal: prasyarat tidak terpenuhi: {unmet}"
                )

            # Eksekusi aksi pada state simbolik
            current_state = act.apply(current_state)
            step_results.append(PlanStepResult(
                step_index=idx,
                action_signature=act.signature,
                cost=act.cost,
                duration=act.duration,
                preconditions_met=True,
                missing_preconditions=[],
                resulting_facts_count=len(current_state)
            ))

        missing_goals = [str(g) for g in problem.goal if not current_state.has(g)]
        goal_reached = (len(missing_goals) == 0)

        if not goal_reached:
            return ValidationReport(
                valid=False,
                total_cost=total_cost,
                total_duration=total_duration,
                steps=step_results,
                goal_reached=False,
                missing_goals=missing_goals,
                message=f"Rencana selesai tetapi sasaran tidak tercapai! Kurang: {missing_goals}"
            )

        return ValidationReport(
            valid=True,
            total_cost=total_cost,
            total_duration=total_duration,
            steps=step_results,
            goal_reached=True,
            missing_goals=[],
            message=f"Rencana VALID! ({len(plan)} langkah, total biaya: {total_cost:.2f}s, goal tercapai)."
        )

