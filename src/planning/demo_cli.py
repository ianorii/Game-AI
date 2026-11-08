"""
demo_cli.py - Handler Demonstrasi CLI Interaktif untuk Ujian & Presentasi Dosen
Mendukung opsi:
  --demo-ojek       : Domain ojek delivery, trace Result(s,a), penolakan plan checker
  --demo-regression : Backward search regression trace sesuai Slide 27 & dual goal Slide 30
  --demo-graph      : Planning graph, deteksi relasi mutex (Slide 31-35), h_level, GraphPlan
  --demo-detour     : Detour jembatan A -> B, A* re-routing, frame time IncrementalPlanner
"""

import sys
import time
import tempfile
import pygame

from planning.pddl_parser import parse_domain, parse_problem
from planning.grounding import ground_problem
from planning.strips import PlanValidator, Predicate, GroundAction
from planning.planner import (
    search_bfs, search_ucs, search_astar_hmax, search_astar_hadd,
    search_weighted_astar_hff, IncrementalPlanner
)
from planning.regression import (
    search_regression_bfs, search_regression_astar,
    build_regression_trace, format_regression_trace
)
from planning.planning_graph import (
    PlanningGraph, compute_h_level, extract_graphplan
)
from world_state import WorldState
from world.game_map import GameMap
from planning.distance_matrix import DistanceMatrix
from planning.problem_generator import build_problem_from_state
from ai.pathfinding import astar


def run_demo_ojek():
    print("\n" + "=" * 80)
    print("DEMO 1: DOMAIN OJEK DELIVERY (Materi Kuliah Slide 1-26 & Slide 30)")
    print("=" * 80)

    with open("data/planning/ojek.domain", "r", encoding="utf-8") as f:
        domain = parse_domain(f.read())
    with open("data/planning/ojek.problem", "r", encoding="utf-8") as f:
        problem_ast = parse_problem(f.read())

    prob = ground_problem(domain, problem_ast, enable_pruning=True)
    print(f"[Problem Setup]")
    print(f"  Objects: {', '.join(problem_ast.objects.keys())}")
    print(f"  Initial State Facts: {len(prob.initial_state.facts)} fakta")
    print(f"    - (motor-at rumah)")
    print(f"    - (at paket warung)")
    print(f"    - road(rumah, warung), road(warung, kampus) [simetris]")
    print(f"  Goal Facts: {', '.join(str(p) for p in prob.goal)}")
    print(f"  Aksi ter-ground: {len(prob.actions)}")

    print("\n[1. Eksekusi Forward Search Algorithms]")
    for name, fn in [
        ("BFS (Breadth-First Search)", search_bfs),
        ("UCS (Uniform-Cost Search)", search_ucs),
        ("A* (Heuristik h_max)", search_astar_hmax),
        ("WA* (Weighted A* h_FF, w=2.0)", lambda p: search_weighted_astar_hff(p, weight=2.0))
    ]:
        t0 = time.perf_counter()
        res = fn(prob)
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        plan_str = " -> ".join(a.signature for a in res.plan)
        print(f"  * {name:<32} : {len(res.plan)} langkah | Biaya: {res.total_cost:.1f} | Nodes: {res.nodes_expanded:2d} | Waktu: {elapsed_ms:.2f} ms")
        print(f"    Rencana: {plan_str}")

    print("\n[2. State Progression Trace: Result(s, a) = (s \\ del(a)) U add(a)]")
    res = search_bfs(prob)
    st = prob.initial_state
    print(f"  State Awal (s0):")
    dynamic_facts = [str(p) for p in st.facts if p.name in ("motor-at", "at", "in")]
    print(f"    Fakta Dinamis: {', '.join(dynamic_facts)}")
    for step_num, act in enumerate(res.plan, start=1):
        st = act.apply(st)
        del_str = ", ".join(str(p) for p in act.delete_effects)
        add_str = ", ".join(str(p) for p in act.add_effects)
        dyn_now = [str(p) for p in st.facts if p.name in ("motor-at", "at", "in")]
        print(f"  Langkah {step_num}: {act.signature}")
        print(f"    Del: {{{del_str}}} | Add: {{{add_str}}}")
        print(f"    State Baru (s{step_num}): {', '.join(dyn_now)}")

    print("\n[3. Plan Checker: Penolakan Rencana Tidak Sah (Slide 30)]")
    prob_unpruned = ground_problem(domain, problem_ast, enable_pruning=False)
    act_map = {a.signature: a for a in prob_unpruned.actions}

    # Plan (a)
    plan_a = [
        act_map["drive(rumah, warung)"],
        act_map["drive(warung, kampus)"],
        act_map["pickup(paket, kampus)"]
    ]
    rep_a = PlanValidator.validate(prob_unpruned, plan_a)
    print(f"  Plan (a) ['drive(rumah, warung)', 'drive(warung, kampus)', 'pickup(paket, kampus)']:")
    print(f"    Valid: {rep_a.valid} | Alasan: {rep_a.message}")

    # Plan (b)
    drive_rk = GroundAction(
        name="drive", params=("rumah", "kampus"),
        preconditions=frozenset([
            Predicate("motor-at", ("rumah",)),
            Predicate("road", ("rumah", "kampus"))
        ]),
        add_effects=frozenset([Predicate("motor-at", ("kampus",))]),
        delete_effects=frozenset([Predicate("motor-at", ("rumah",))]),
        cost=1.0, duration=1.0
    )
    plan_b = [drive_rk, act_map["pickup(paket, kampus)"]]
    rep_b = PlanValidator.validate(prob_unpruned, plan_b)
    print(f"  Plan (b) ['drive(rumah, kampus)', 'pickup(paket, kampus)']:")
    print(f"    Valid: {rep_b.valid} | Alasan: {rep_b.message}")

    print("\n[4. Variasi Gerbang Kampus Tertutup (ojek_gate)]")
    with open("data/planning/ojek_gate.domain", "r", encoding="utf-8") as f:
        g_dom = parse_domain(f.read())
    with open("data/planning/ojek_gate.problem", "r", encoding="utf-8") as f:
        g_prob_ast = parse_problem(f.read())
    prob_gate = ground_problem(g_dom, g_prob_ast, enable_pruning=True)
    res_gate = search_weighted_astar_hff(prob_gate)
    print(f"  Rencana Adaptif: {' -> '.join(a.signature for a in res_gate.plan)}")
    print("=" * 80 + "\n")


def run_demo_regression():
    print("\n" + "=" * 80)
    print("DEMO 2: BACKWARD SEARCH / REGRESSION (Materi Kuliah Slide 27 & Slide 30)")
    print("=" * 80)

    with open("data/planning/ojek.domain", "r", encoding="utf-8") as f:
        domain = parse_domain(f.read())
    with open("data/planning/ojek.problem", "r", encoding="utf-8") as f:
        problem_ast = parse_problem(f.read())

    prob = ground_problem(domain, problem_ast, enable_pruning=True)

    print("[1. Backward Search Regression Trace Persis Slide 27]")
    res_reg = search_regression_bfs(prob)
    trace = build_regression_trace(prob, res_reg.plan)
    print(format_regression_trace(trace))

    print("\n[2. Backward Search dengan Dual Goal (Slide 30)]")
    print("  Goal Ganda: (at paket kampus) DAN (motor-at rumah)")
    with open("data/planning/ojek.problem", "r", encoding="utf-8") as f:
        dual_ast = parse_problem(f.read())
    dual_ast.goal_facts = {("at", "paket", "kampus"), ("motor-at", "rumah")}
    prob_dual = ground_problem(domain, dual_ast, enable_pruning=True)

    t0 = time.perf_counter()
    res_dual = search_regression_astar(prob_dual)
    elapsed_ms = (time.perf_counter() - t0) * 1000.0
    print(f"  Hasil Pencarian: SUKSES ({len(res_dual.plan)} langkah, {elapsed_ms:.2f} ms)")
    for i, a in enumerate(res_dual.plan, 1):
        print(f"    {i}. {a.signature}")
    val_dual = PlanValidator.validate(prob_dual, res_dual.plan)
    print(f"  Validasi Forward Execution: {val_dual.valid}")
    print("=" * 80 + "\n")


def run_demo_graph():
    print("\n" + "=" * 80)
    print("DEMO 3: PLANNING GRAPH & MUTEX (Materi Kuliah Slide 31-35)")
    print("=" * 80)

    with open("data/planning/ojek.domain", "r", encoding="utf-8") as f:
        domain = parse_domain(f.read())
    with open("data/planning/ojek.problem", "r", encoding="utf-8") as f:
        problem_ast = parse_problem(f.read())

    prob = ground_problem(domain, problem_ast, enable_pruning=True)
    pg = PlanningGraph(prob)
    print(f"[1. Membangun Planning Graph Level-by-Level (Slide 31-32)]")
    for level_idx in range(4):
        pg.expand_one_level()
        sl = pg.state_levels[level_idx + 1]
        al = pg.action_levels[level_idx]
        print(f"  Level {level_idx}: {len(al.actions):2d} Aksi ({len(al.mutex_pairs)} mutex aksi) -> Level S{level_idx+1}: {len(sl.facts):2d} Proposisi ({len(sl.mutex_pairs)} mutex proposisi)")

    print("\n[2. Deteksi Relasi Mutex Aksi (Slide 33-34)]")
    a0 = pg.action_levels[0]
    drive_act = next(a for a in a0.actions if "drive(rumah, warung)" in a.signature)
    noop_motor = next(a for a in a0.actions if "motor-at rumah" in a.signature)
    noop_paket = next(a for a in a0.actions if "at paket warung" in a.signature)

    print(f"  Aksi: {drive_act.signature}")
    print(f"  Mutex dengan no-op 'motor-at rumah': {a0.is_mutex(drive_act, noop_motor)} (Inconsistent effects / interference)")
    print(f"  Mutex dengan no-op 'at paket warung': {a0.is_mutex(drive_act, noop_paket)} (Tidak ada konflik)")

    print("\n[3. Evaluasi Heuristik h_level & Ekstraksi GraphPlan (Slide 35)]")
    h_lvl = compute_h_level(prob)
    print(f"  Heuristik h_level(s0, goal) = {h_lvl:.1f}")
    plan_gp = extract_graphplan(PlanningGraph(prob))
    if plan_gp:
        print(f"  GraphPlan mengekstrak rencana {len(plan_gp)} langkah:")
        for idx, step in enumerate(plan_gp, 1):
            print(f"    {idx}. {step.signature}")
    print("=" * 80 + "\n")


def run_demo_detour():
    print("\n" + "=" * 80)
    print("DEMO 4: DETOUR REPLAN & REAL-TIME RE-ROUTING (Sub-fase 2B & Bagian 2)")
    print("=" * 80)

    gmap = GameMap()
    bridge_b_override = {(24, 15), (43, 20)}

    def is_blocked_raw(cx, cy):
        px = cx * 32 + 16
        py = cy * 32 + 16
        return not gmap.is_walkable_at(px, py)

    def is_blocked_raw_bridge_a_cut(cx, cy):
        if 35 <= cx <= 41 and 28 <= cy <= 33:
            return True
        return is_blocked_raw(cx, cy)

    def is_blocked_both_open(cx, cy):
        if (cx, cy) in bridge_b_override:
            return False
        return is_blocked_raw(cx, cy)

    def is_blocked_detour(cx, cy):
        if 35 <= cx <= 41 and 28 <= cy <= 33:
            return True
        if (cx, cy) in bridge_b_override:
            return False
        return is_blocked_raw(cx, cy)

    print("[1. Topologi Jembatan Peta Mentah Sunnyside]")
    west_bank = (34, 30)
    east_bank = (50, 29)
    res_raw_open = astar(86, 48, west_bank, east_bank, is_blocked_raw)
    res_raw_cut = astar(86, 48, west_bank, east_bank, is_blocked_raw_bridge_a_cut)
    print(f"  Jembatan A Terbuka (Raw): {len(res_raw_open.path)} tile")
    print(f"  Jembatan A Ditutup (Raw): {len(res_raw_cut.path) if res_raw_cut.found else 'Terputus Total (dur=inf)'}")
    print("  -> Analisis: Jembatan Tengah A adalah satu-satunya penyeberangan alami pada raw mask.")

    print("\n[2. Detour Reroute A* Melintasi Koridor Jembatan B Utara]")
    res_before = astar(86, 48, west_bank, east_bank, is_blocked_both_open)
    res_after = astar(86, 48, west_bank, east_bank, is_blocked_detour)
    cost_before = len(res_before.path) / 4.6
    cost_after = len(res_after.path) / 4.6
    delta_cost = cost_after - cost_before

    print(f"  Rute Jembatan A (Sebelum): {len(res_before.path)} tile ({cost_before:.2f} s)")
    print(f"  Rute Jembatan B (Sesudah): {len(res_after.path)} tile ({cost_after:.2f} s)")
    print(f"  Delta Cost Detour: {delta_cost:+.2f} s")
    wp_north = [p for p in res_after.path if (p in bridge_b_override or (37 <= p[0] <= 46 and 16 <= p[1] <= 21))]
    print(f"  Waypoints Koridor Utara: {wp_north[:6]}")

    print("\n[3. Evaluasi Frame Time IncrementalPlanner.step() <= 20 ms]")
    with open("data/planning/expedition.domain", "r", encoding="utf-8") as f:
        exp_domain = parse_domain(f.read())
    ws = WorldState(starting_coins=20)
    dm = DistanceMatrix(game_map=gmap)
    prob_exp = build_problem_from_state(ws, domain=exp_domain, goal_type="boss_defeated", distance_matrix=dm, max_coins=60)
    inc_planner = IncrementalPlanner(prob_exp, weight=2.0)

    frame_times = []
    for step_i in range(5):
        t0 = time.perf_counter()
        done, _ = inc_planner.step(max_frame_ms=15.0)
        dur_ms = (time.perf_counter() - t0) * 1000.0
        frame_times.append(dur_ms)
        print(f"  Step frame {step_i+1}: {dur_ms:.2f} ms")

    max_ft = max(frame_times)
    print(f"  Frame time maksimum: {max_ft:.2f} ms (Target: <= 20 ms -> {'LOLOS' if max_ft <= 20.0 else 'GAGAL'})")
    print("=" * 80 + "\n")
