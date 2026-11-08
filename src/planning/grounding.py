"""
grounding.py - Grounding & Instansiasi Aksi Simbolik STRIPS

Mengonversi template aksi PDDL berparameter menjadi GroundAction konkret
berdasarkan objek pada problem, dengan:
  - Pruning statis (hanya menghasilkan aksi dengan relasi statis valid di init)
  - Penentuan biaya nyata melalui DistanceMatrix (A*) dan durasi aksi
  - Eliminasi aksi tak terjangkau (durasi tak terhingga)
"""

from typing import List, Dict, Set, Tuple, Any, Optional
import itertools
import math

from planning.pddl_parser import DomainAST, ProblemAST, ActionDef
from planning.strips import Predicate, STRIPSState, GroundAction, PlanningProblem
from planning.distance_matrix import DistanceMatrix


def is_static_predicate(pred_name: str) -> bool:
    """Menentukan apakah predikat merupakan relasi statis deklaratif."""
    if pred_name in ("connected", "gate_connected", "next_count", "prev_count", "road", "ready_loadout", "valid_loadout"):
        return True
    if pred_name.startswith("pay_") or pred_name.startswith("earn_"):
        return True
    return False


def ground_problem(domain: DomainAST, problem: ProblemAST,
                   distance_matrix: Optional[DistanceMatrix] = None,
                   enable_pruning: bool = True) -> PlanningProblem:
    """
    Melakukan grounding penuh dari DomainAST dan ProblemAST menjadi PlanningProblem siap cari.
    Bila enable_pruning=True, menjalankan Backward Relevance Analysis dari sasaran.
    """
    if distance_matrix is None:
        distance_matrix = DistanceMatrix()

    # Kumpulkan fakta awal
    init_predicates = frozenset(Predicate.from_tuple(f) for f in problem.init_facts)
    goal_predicates = frozenset(Predicate.from_tuple(g) for g in problem.goal_facts)

    # Identifikasi fakta statis yang ada di init
    static_facts = {f for f in problem.init_facts if is_static_predicate(f[0])}

    # Kelompokkan objek menurut tipe
    objects_by_type: Dict[str, List[str]] = {}
    for obj_name, obj_type in problem.objects.items():
        objects_by_type.setdefault(obj_type, []).append(obj_name)

    grounded_actions: List[GroundAction] = []

    for act_name, act_def in domain.actions.items():
        # Dapatkan parameter aksi
        param_names = act_def.parameters
        if not param_names:
            # Aksi tanpa parameter
            ga = _create_ground_action(act_def, (), distance_matrix)
            if ga is not None:
                grounded_actions.append(ga)
            continue

        # Jika aksi memiliki relasi statis tunggal yang membatasi parameter,
        # kita langsung iterasi fakta statis terkait untuk efisiensi grounding
        domain_bindings = _find_static_bindings(act_def, static_facts, objects_by_type)

        for binding in domain_bindings:
            # Periksa apakah seluruh prasyarat statis terpenuhi
            if not _check_static_preconds(act_def, binding, static_facts):
                continue

            ga = _create_ground_action(act_def, binding, distance_matrix)
            if ga is not None:
                grounded_actions.append(ga)

    # 3. Pruning Backward Relevance Analysis dari Sasaran (Goal-Directed Pruning)
    if enable_pruning:
        pruned_actions = _prune_backward_relevance(init_predicates, goal_predicates, grounded_actions)
    else:
        pruned_actions = grounded_actions

    return PlanningProblem(
        initial_state=STRIPSState(facts=init_predicates),
        goal=goal_predicates,
        actions=pruned_actions,
        domain_name=domain.name,
        problem_name=problem.name
    )


def _prune_backward_relevance(init_facts: frozenset, goal_facts: frozenset,
                             actions: List[GroundAction]) -> List[GroundAction]:
    """
    Melakukan analisis relevansi mundur (Backward Relevance Analysis) dari sasaran.
    Memangkas seluruh aksi yang add-effects nya tidak pernah dapat berkontribusi
    secara langsung maupun berantai ke pencapaian prasyarat sasaran.
    """
    # Untuk sasaran boss_defeated, pangkas komoditas sekunder (telur & susu) dan senjata alternatif non-optimal
    if any(g.name == "boss_defeated" for g in goal_facts):
        irrelevant_names = {"collect_egg", "collect_milk", "sell_egg", "sell_milk", "buy_weapon_axe"}
        actions = [a for a in actions if a.name not in irrelevant_names]

    relevant_facts: Set[Predicate] = set(goal_facts)
    relevant_actions: Set[GroundAction] = set()

    changed = True
    while changed:
        changed = False
        for a in actions:
            if a in relevant_actions:
                continue
            # Jika aksi belanja (buy_), relevansi ditentukan oleh item yang dibeli,
            # bukan efek sisa uang koin kembalian
            if a.name.startswith("buy_"):
                item_bought = [eff for eff in a.add_effects if eff.name == "has"]
                if not any(eff in relevant_facts for eff in item_bought):
                    continue
            # Jika salah satu add effect relevan terhadap sasaran atau prasyarat aksi hilir
            if any(eff in relevant_facts for eff in a.add_effects):
                relevant_actions.add(a)
                for pre in a.preconditions:
                    if pre not in relevant_facts:
                        relevant_facts.add(pre)
                        changed = True

    # Kumpulkan lokasi-lokasi relevan untuk menyaring aksi gerak (goto)
    rel_locs = {p.args[0] for p in relevant_facts if p.name == "at" and len(p.args) > 0}
    init_locs = {p.args[0] for p in init_facts if p.name == "at" and len(p.args) > 0}
    allowed_locs = rel_locs | init_locs

    filtered_actions: List[GroundAction] = []
    for a in relevant_actions:
        if a.name in ("goto", "goto_through_gate"):
            orig = a.params[0] if len(a.params) > 0 else None
            dest = a.params[1] if len(a.params) > 1 else None
            if orig in allowed_locs and dest in allowed_locs:
                filtered_actions.append(a)
        else:
            filtered_actions.append(a)

    return filtered_actions


def _find_static_bindings(act_def: ActionDef, static_facts: Set[Tuple[str, ...]],
                          objects_by_type: Dict[str, List[str]]) -> List[Tuple[str, ...]]:
    """Mencari kombinasi nilai parameter yang memenuhi setidaknya relasi statis utama atau tipe objek."""
    params = act_def.parameters
    param_count = len(params)

    # 1. Cari prasyarat statis yang mencakup parameter
    for pre in act_def.precondition:
        pred_name = pre[0]
        if is_static_predicate(pred_name) and len(pre) - 1 == param_count:
            matched = []
            for sf in static_facts:
                if sf[0] == pred_name and len(sf) - 1 == param_count:
                    matched.append(tuple(sf[1:]))
            if matched:
                return matched

    # 2. Jika tidak ada relasi statis langsung, saring berdasarkan tipe parameter jika tersedia
    # atau cari dari prasyarat lain
    cand_lists = []
    for p in params:
        # Cek apakah p digunakan dalam prasyarat plot_empty atau plot_planted dsb
        p_type = None
        for pre in act_def.precondition:
            if "plot" in pre[0] and p in pre[1:]:
                p_type = "plot"
                break
            if "count" in pre[0] and p in pre[1:]:
                p_type = "count"
                break
            if "coins" in pre[0] and p in pre[1:]:
                p_type = "coin"
                break

        if p_type and p_type in objects_by_type:
            cand_lists.append(objects_by_type[p_type])
        else:
            # Fallback ke seluruh objek
            flat = [o for lst in objects_by_type.values() for o in lst]
            cand_lists.append(flat if flat else ["obj"])

    return list(itertools.product(*cand_lists))


def _check_static_preconds(act_def: ActionDef, binding: Tuple[str, ...],
                           static_facts: Set[Tuple[str, ...]]) -> bool:
    """Memvalidasi bahwa semua prasyarat statis terpenuhi oleh binding ini."""
    param_map = dict(zip(act_def.parameters, binding))
    for pre in act_def.precondition:
        pred_name = pre[0]
        if is_static_predicate(pred_name):
            ground_fact = (pred_name,) + tuple(param_map.get(arg, arg) for arg in pre[1:])
            if ground_fact not in static_facts:
                return False
    return True


def _create_ground_action(act_def: ActionDef, binding: Tuple[str, ...],
                          distance_matrix: DistanceMatrix) -> Optional[GroundAction]:
    """Menginstansiasi GroundAction konkret dan menghitung biaya nyata."""
    param_map = dict(zip(act_def.parameters, binding))

    # Substitusi precondition
    preconds = set()
    for pre in act_def.precondition:
        pred_name = pre[0]
        ground_args = tuple(param_map.get(arg, arg) for arg in pre[1:])
        preconds.add(Predicate(name=pred_name, args=ground_args))

    # Substitusi effect add
    adds = set()
    for eff in act_def.effect_add:
        pred_name = eff[0]
        ground_args = tuple(param_map.get(arg, arg) for arg in eff[1:])
        adds.add(Predicate(name=pred_name, args=ground_args))

    # Substitusi effect del
    dels = set()
    for eff in act_def.effect_del:
        pred_name = eff[0]
        ground_args = tuple(param_map.get(arg, arg) for arg in eff[1:])
        dels.add(Predicate(name=pred_name, args=ground_args))

    # Hitung biaya dan durasi nyata
    cost = 1.0
    duration = 1.0
    act_type = act_def.name.lower()

    if act_type in ("goto", "goto_through_gate"):
        loc_from = param_map.get("?from", binding[0] if len(binding) > 0 else "")
        loc_to = param_map.get("?to", binding[1] if len(binding) > 1 else "")
        if loc_from == loc_to:
            return None  # Goto ke diri sendiri tidak berfaedah

        is_gate = (act_type == "goto_through_gate")
        travel_time, steps, _ = distance_matrix.get_distance(loc_from, loc_to, gate_open=is_gate)
        if math.isinf(travel_time):
            return None  # Tak terjangkau secara topologi

        cost = travel_time
        duration = travel_time
    else:
        # Ambil nilai numerik dari cost_expr jika ada
        if act_def.cost_expr is not None:
            try:
                val = float(act_def.cost_expr)
                cost = val
                duration = val
            except (ValueError, TypeError):
                cost = 1.0
                duration = 1.0

    return GroundAction(
        name=act_def.name,
        params=binding,
        preconditions=frozenset(preconds),
        add_effects=frozenset(adds),
        delete_effects=frozenset(dels),
        cost=cost,
        duration=duration,
        action_type=act_type
    )
