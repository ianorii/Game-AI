"""
src/planning - Classical Planning (STRIPS) & Hierarchical Task Network (HTN) Engine
"""

from planning.strips import Predicate, GroundAction, STRIPSState, PlanningProblem, PlanValidator
from planning.pddl_parser import parse_domain, parse_problem, DomainAST, ProblemAST
from planning.grounding import ground_problem
from planning.heuristics import h_max, h_add, h_ff, check_relaxed_reachability, FastHeuristicEngine
from planning.distance_matrix import DistanceMatrix
from planning.problem_generator import build_problem_from_state, generate_dynamic_coin_facts
from planning.planner import (
    search_bfs, search_ucs, search_astar_hmax, search_astar_hadd,
    search_weighted_astar_hff, search_astar_hlevel, solve, IncrementalPlanner, SearchResult
)
from planning.executor import PlanExecutor, PlanExecutionReport, ExecutionStepResult
from planning.monitor import PlanMonitor, ReplanTrigger, MonitorStatus
from planning.autopilot import AutopilotController, PlannerMode, AutopilotState
