"""
csp_loadout.py - Constraint Satisfaction Problem untuk Persiapan Loadout Hero.

Hero mengonfigurasi 4 slot perlengkapan sebelum menghadapi Boss:
  1. WEAPON
  2. ARMOR
  3. CHARM
  4. CONSUMABLE

Sistem ini mengimplementasikan:
  - Constraint eksplisit (Unary, Global Budget, Global Weight, Binary Conflict, Binary Requirement, Combinatorial Defensive)
  - CSP Solver berbasis Backtracking Search
  - Heuristik MRV (Minimum Remaining Values) dengan Degree heuristic tie-breaker
  - Heuristik LCV (Least Constraining Value)
  - Inferensi Forward Checking (FC)
  - Pelacakan performa & riwayat langkah (CSPStats)
  - Fungsi murni apply_loadout() yang memodifikasi BattleState tanpa efek samping
"""

from dataclasses import dataclass, field
import copy
import time
import random
import config
from ai.adversarial import BattleState


# ==============================================================================
# STRUKTUR DATA & HELPER ITEM
# ==============================================================================
def get_item_dict(slot: str, name: str) -> dict:
    """Mengambil dictionary item berdasarkan slot dan nama."""
    items = config.CSP_ITEMS.get(slot, []) or config.CSP_ITEMS.get(slot.upper(), [])
    for it in items:
        if it["name"] == name:
            return it
    return {"name": name, "cost": 0, "weight": 0, "desc": "-", "effects": {}, "locked": False, "is_defensive": False}


def calculate_cost(assignment: dict) -> int:
    """Menghitung total cost dari assignment saat ini."""
    total = 0
    for slot, val in assignment.items():
        if val:
            it = get_item_dict(slot, val)
            total += it.get("cost", 0)
    return total


def calculate_weight(assignment: dict) -> int:
    """Menghitung total weight dari assignment saat ini."""
    total = 0
    for slot, val in assignment.items():
        if val:
            it = get_item_dict(slot, val)
            total += it.get("weight", 0)
    return total


# ==============================================================================
# KELAS-KELAS CONSTRAINT EKSPLISIT
# ==============================================================================
class Constraint:
    """Base class untuk constraint CSP."""
    name: str = "Constraint"

    def is_satisfied(self, assignment: dict, partial: bool = False) -> tuple[bool, str]:
        """
        Memeriksa apakah assignment memenuhi batasan.
        Mengembalikan (True, "") atau (False, "Penjelasan pelanggaran").
        """
        raise NotImplementedError


class UnlockedConstraint(Constraint):
    """Batasan Unary: Item yang terkunci (locked=True) tidak boleh digunakan."""
    name = "Unary: Unlocked Items Only"

    def is_satisfied(self, assignment: dict, partial: bool = False) -> tuple[bool, str]:
        for slot, val in assignment.items():
            if val:
                it = get_item_dict(slot, val)
                if it.get("locked", False):
                    return False, f"Item '{val}' masih terkunci (butuh level/syarat khusus)!"
        return True, ""


class BudgetConstraint(Constraint):
    """Batasan Global: Total cost perlengkapan <= max_budget."""
    def __init__(self, max_budget: int = None):
        self.max_budget = max_budget if max_budget is not None else config.CSP_BUDGET
        self.name = f"Global: Budget Limit (<= {self.max_budget})"

    def is_satisfied(self, assignment: dict, partial: bool = False) -> tuple[bool, str]:
        cost = calculate_cost(assignment)
        if cost > self.max_budget:
            return False, f"Total Cost ({cost}/{self.max_budget}) melebihi batas anggaran!"
        return True, ""


class WeightConstraint(Constraint):
    """Batasan Global: Total bobot perlengkapan <= max_weight."""
    def __init__(self, max_weight: int = None):
        self.max_weight = max_weight if max_weight is not None else config.CSP_WEIGHT_LIMIT
        self.name = f"Global: Weight Limit (<= {self.max_weight})"

    def is_satisfied(self, assignment: dict, partial: bool = False) -> tuple[bool, str]:
        weight = calculate_weight(assignment)
        if weight > self.max_weight:
            return False, f"Total Beban ({weight}/{self.max_weight}) melebihi batas kapasitas hero!"
        return True, ""


class HeavyAxeNoCritCharmConstraint(Constraint):
    """Batasan Binary Konflik: Kapak Berat tidak dapat dipadukan dengan Jimat Kritikal."""
    name = "Binary Conflict: Kapak Berat vs Jimat Kritikal"

    def is_satisfied(self, assignment: dict, partial: bool = False) -> tuple[bool, str]:
        weapon = assignment.get("WEAPON")
        charm = assignment.get("CHARM")
        if weapon == "Kapak Berat" and charm == "Jimat Kritikal":
            return False, "Kapak Berat (serangan lambat) bentrok dengan Jimat Kritikal (butuh presisi cepat)!"
        return True, ""


class FireStaffLightArmorConstraint(Constraint):
    """Batasan Binary Syarat: Tongkat Api membutuhkan jubah ringan (Kain/Kulit), tidak boleh Besi."""
    name = "Binary Requirement: Tongkat Api butuh Jubah Ringan"

    def is_satisfied(self, assignment: dict, partial: bool = False) -> tuple[bool, str]:
        weapon = assignment.get("WEAPON")
        armor = assignment.get("ARMOR")
        if weapon == "Tongkat Api" and armor:
            if armor not in ("Kain", "Kulit"):
                return False, f"Tongkat Api membutuhkan jubah sihir ringan (Kain/Kulit), bukan '{armor}'!"
        return True, ""


class DefensiveItemConstraint(Constraint):
    """
    Batasan Kombinatorial: Minimal membawa 1 item defensif
    (Bisa Armor, Jimat Vitalitas, atau Perisai Kertas).
    """
    name = "Combinatorial: Minimal 1 Item Defensif"

    def __init__(self, allow_starter: bool = False):
        self.allow_starter = allow_starter

    def is_satisfied(self, assignment: dict, partial: bool = False) -> tuple[bool, str]:
        # Jika partial, hanya periksa jika semua 4 slot sudah terisi
        if partial and len([v for v in assignment.values() if v]) < len(config.CSP_SLOTS):
            return True, ""

        has_defensive = False
        for slot, val in assignment.items():
            if val:
                it = get_item_dict(slot, val)
                if it.get("is_defensive", False):
                    has_defensive = True
                    break

        if not has_defensive and self.allow_starter:
            # Starter gear (Kain + Pedang Biasa) sah sebagai minimal defense saat hanya membawa starter
            if assignment.get("ARMOR") == "Kain" and assignment.get("WEAPON") == "Pedang Biasa":
                has_defensive = True

        if not has_defensive:
            return False, "Hero harus membawa minimal 1 item defensif (Armor / Jimat Vitalitas / Perisai Kertas)!"
        return True, ""


class OwnedConstraint(Constraint):
    """Batasan Unary: Hanya item yang dimiliki hero di inventori atau starter yang dapat digunakan."""
    name = "Unary: Owned Items Only"

    def __init__(self, owned_items: Optional[set] = None):
        self.starter_items = {"Pedang Biasa", "Kain", "Kosong"}
        self.owned_items = set(owned_items) if owned_items is not None else None

    def is_satisfied(self, assignment: dict, partial: bool = False) -> tuple[bool, str]:
        if self.owned_items is None:
            return True, ""
        allowed = self.starter_items | self.owned_items
        for slot, val in assignment.items():
            if val and val not in allowed:
                return False, f"Item '{val}' belum dimiliki hero (beli di toko desa atau bawa starter)!"
        return True, ""


def get_default_constraints(budget: int = None, weight_limit: int = None) -> list[Constraint]:
    """Menghasilkan list constraint resmi dengan batas budget dan weight yang dapat disesuaikan."""
    return [
        UnlockedConstraint(),
        BudgetConstraint(budget),
        WeightConstraint(weight_limit),
        HeavyAxeNoCritCharmConstraint(),
        FireStaffLightArmorConstraint(),
        DefensiveItemConstraint(),
    ]


def get_loadout_constraints(budget: int = None, weight_limit: int = None,
                           owned_items: Optional[set] = None) -> list[Constraint]:
    """Constraint loadout lengkap termasuk batasan item yang dimiliki hero (OwnedConstraint)."""
    return [
        UnlockedConstraint(),
        OwnedConstraint(owned_items),
        BudgetConstraint(budget),
        WeightConstraint(weight_limit),
        HeavyAxeNoCritCharmConstraint(),
        FireStaffLightArmorConstraint(),
        DefensiveItemConstraint(allow_starter=(owned_items is not None)),
    ]


# Daftar semua constraint resmi default
DEFAULT_CONSTRAINTS: list[Constraint] = get_default_constraints()


def check_constraints(assignment: dict, partial: bool = False,
                      constraints: list[Constraint] = None) -> tuple[bool, str]:
    """
    Memeriksa semua constraint pada assignment.
    Mengembalikan (is_valid, reason).
    """
    if constraints is None:
        constraints = DEFAULT_CONSTRAINTS

    for c in constraints:
        sat, reason = c.is_satisfied(assignment, partial=partial)
        if not sat:
            return False, reason
    return True, "Semua batasan terpenuhi."


# ==============================================================================
# STATISTIK PENCARIAN CSP
# ==============================================================================
@dataclass
class CSPStats:
    """Merekam statistik pencarian CSP solver untuk analisis dan F4 panel."""
    nodes_visited: int = 0
    backtracks_count: int = 0
    pruned_values_count: int = 0
    constraint_checks: int = 0
    time_ms: float = 0.0
    solutions_found: int = 0
    step_history: list = field(default_factory=list)


# ==============================================================================
# CSP SOLVER
# ==============================================================================
class LoadoutCSPSolver:
    """
    Solver CSP untuk Loadout Hero:
    - 4 Varian Pencarian:
      1. Naive (Generate & Test: urutan variabel tetap, domain tetap, periksa penuh saat 4 slot terisi)
      2. BT-Incremental (Backtracking dengan pengecekan konsistensi parsial bertahap)
      3. BT+Heuristics (MRV + Degree Heuristic + LCV, cek parsial, tanpa forward checking)
      4. BT+MRV+FC+LCV (Forward Checking memangkas domain unassigned dan deteksi wipeout dini)
    """

    def __init__(self, items=None, constraints=None, seed=config.CSP_SOLVER_SEED, owned_items=None):
        self.items = items if items is not None else config.CSP_ITEMS
        if constraints is not None:
            self.constraints = constraints
        elif owned_items is not None:
            self.constraints = get_loadout_constraints(owned_items=owned_items)
        else:
            self.constraints = DEFAULT_CONSTRAINTS
        self.seed = seed
        self.rng = random.Random(seed)
        self.variables = list(config.CSP_SLOTS)
        self.top_candidates = []

        # Derajat keterlibatan variabel dalam batasan (Degree Heuristic)
        self.degrees = {
            "WEAPON": 5,      # HeavyAxe, FireStaff, Budget, Weight, Defensive
            "ARMOR": 4,       # FireStaff, Budget, Weight, Defensive
            "CHARM": 4,       # HeavyAxe, Budget, Weight, Defensive
            "CONSUMABLE": 3,  # Budget, Weight, Defensive
        }

    def get_initial_domains(self) -> dict[str, list[str]]:
        """Mendapatkan domain nama item untuk setiap slot."""
        domains = {}
        for var in self.variables:
            item_list = self.items.get(var, [])
            # Filter locked items terlebih dahulu (Node Consistency / Unary constraint)
            domains[var] = [it["name"] for it in item_list if not it.get("locked", False)]
        return domains

    def select_unassigned_variable(self, assignment: dict, domains: dict[str, list[str]],
                                   use_mrv: bool = True) -> str:
        """
        Memilih variabel berikutnya dengan MRV dan Degree heuristic sebagai tie-breaker.
        """
        unassigned = [v for v in self.variables if v not in assignment]
        if not unassigned:
            return ""

        if not use_mrv:
            return unassigned[0]

        # MRV: domain terkecil
        min_rem = min(len(domains[v]) for v in unassigned)
        candidates = [v for v in unassigned if len(domains[v]) == min_rem]

        if len(candidates) == 1:
            return candidates[0]

        # Degree Heuristic tie-breaker: pilih variabel dengan degree tertinggi
        return max(candidates, key=lambda v: self.degrees.get(v, 0))

    def order_domain_values(self, var: str, assignment: dict, domains: dict[str, list[str]],
                            use_lcv: bool = True) -> list[str]:
        """
        Mengurutkan nilai domain dengan heuristik LCV (Least Constraining Value).
        Nilai yang paling sedikit memotong domain variabel tetangga ditempatkan di depan.
        """
        values = list(domains[var])
        if not use_lcv or len(values) <= 1:
            return values

        unassigned = [v for v in self.variables if v not in assignment and v != var]
        if not unassigned:
            return values

        def count_conflicts(val: str) -> int:
            conflicts = 0
            temp_assign = dict(assignment)
            temp_assign[var] = val
            for other_var in unassigned:
                for other_val in domains[other_var]:
                    trial_assign = dict(temp_assign)
                    trial_assign[other_var] = other_val
                    sat, _ = check_constraints(trial_assign, partial=True, constraints=self.constraints)
                    if not sat:
                        conflicts += 1
            return conflicts

        values.sort(key=count_conflicts)
        return values

    def forward_check(self, var: str, val: str, assignment: dict,
                      domains: dict[str, list[str]]) -> tuple[bool, dict[str, list[str]], int]:
        """
        Memangkas domain variabel unassigned yang bertentangan dengan assignment baru.
        Mengembalikan (is_valid, new_domains, pruned_count).
        """
        new_domains = {v: list(d) for v, d in domains.items()}
        temp_assign = dict(assignment)
        temp_assign[var] = val
        pruned_count = 0

        unassigned = [v for v in self.variables if v not in temp_assign]
        for other_var in unassigned:
            valid_vals = []
            for other_val in new_domains[other_var]:
                trial_assign = dict(temp_assign)
                trial_assign[other_var] = other_val
                sat, _ = check_constraints(trial_assign, partial=True, constraints=self.constraints)
                if sat:
                    valid_vals.append(other_val)
                else:
                    pruned_count += 1

            if not valid_vals:
                # Forward checking mendeteksi wipeout: domain habis
                return False, new_domains, pruned_count
            new_domains[other_var] = valid_vals

        return True, new_domains, pruned_count

    def solve(self, use_mrv: bool = True, use_fc: bool = True, use_lcv: bool = True) -> tuple[dict, CSPStats]:
        """
        Mencari satu solusi pertama yang valid.
        """
        t0 = time.perf_counter()
        stats = CSPStats()
        initial_domains = self.get_initial_domains()

        def backtrack(assignment: dict, domains: dict[str, list[str]]) -> dict | None:
            stats.nodes_visited += 1

            if len(assignment) == len(self.variables):
                sat, _ = check_constraints(assignment, partial=False, constraints=self.constraints)
                if sat:
                    stats.solutions_found += 1
                    return assignment
                return None

            var = self.select_unassigned_variable(assignment, domains, use_mrv=use_mrv)
            ordered_vals = self.order_domain_values(var, assignment, domains, use_lcv=use_lcv)

            for val in ordered_vals:
                trial_assign = dict(assignment)
                trial_assign[var] = val

                sat, reason = check_constraints(trial_assign, partial=True, constraints=self.constraints)
                if not sat:
                    stats.step_history.append({
                        "slot": var, "item": val, "action": "prune", "reason": reason
                    })
                    continue

                stats.step_history.append({
                    "slot": var, "item": val, "action": "assign", "reason": "Consistent"
                })

                if use_fc:
                    fc_ok, pruned_domains, pruned_count = self.forward_check(var, val, assignment, domains)
                    stats.pruned_values_count += pruned_count
                    if not fc_ok:
                        stats.backtracks_count += 1
                        stats.step_history.append({
                            "slot": var, "item": val, "action": "backtrack", "reason": "Forward checking wipeout"
                        })
                        continue
                    next_domains = pruned_domains
                else:
                    next_domains = domains

                result = backtrack(trial_assign, next_domains)
                if result is not None:
                    return result

                stats.backtracks_count += 1
                stats.step_history.append({
                    "slot": var, "item": val, "action": "backtrack", "reason": "No valid solution in subtree"
                })

            return None

        solution = backtrack({}, initial_domains)
        stats.time_ms = (time.perf_counter() - t0) * 1000.0
        return solution or dict(config.CSP_DEFAULT_LOADOUT), stats

    # --------------------------------------------------------------------------
    # 4 VARIAN PENCARIAN SOLVER CSP (LENGKAP UNTUK BENCHMARK & EVALUASI AKADEMIK)
    # --------------------------------------------------------------------------
    def solve_all_naive(self) -> tuple[list[dict], CSPStats]:
        """
        Varian 1: Naive (Generate & Test / Pure Chronological Search)
        - Urutan variabel tetap (WEAPON -> ARMOR -> CHARM -> CONSUMABLE).
        - Domain tetap tanpa pengurutan nilai.
        - Constraint baru dievaluasi saat assignment lengkap (4 slot terisi).
        """
        t0 = time.perf_counter()
        stats = CSPStats()
        initial_domains = self.get_initial_domains()
        all_solutions = []
        var_order = list(self.variables)

        def backtrack_naive(assignment: dict, depth: int):
            stats.nodes_visited += 1

            if depth == len(var_order):
                stats.constraint_checks += 1
                sat, _ = check_constraints(assignment, partial=False, constraints=self.constraints)
                if sat:
                    stats.solutions_found += 1
                    all_solutions.append(dict(assignment))
                else:
                    stats.backtracks_count += 1
                return

            var = var_order[depth]
            for val in initial_domains[var]:
                trial = dict(assignment)
                trial[var] = val
                backtrack_naive(trial, depth + 1)

        backtrack_naive({}, 0)
        stats.time_ms = (time.perf_counter() - t0) * 1000.0
        return all_solutions, stats

    def solve_all_bt_incremental(self) -> tuple[list[dict], CSPStats]:
        """
        Varian 2: Backtracking + Pengecekan Konsistensi Parsial Bertahap
        - Urutan variabel tetap.
        - Constraint dicek di setiap assignment parsial.
        - Jika inkonsisten, langsung potong cabang (backtrack) tanpa forward checking.
        """
        t0 = time.perf_counter()
        stats = CSPStats()
        initial_domains = self.get_initial_domains()
        all_solutions = []
        var_order = list(self.variables)

        def backtrack_inc(assignment: dict, depth: int):
            stats.nodes_visited += 1

            if depth == len(var_order):
                stats.constraint_checks += 1
                sat, _ = check_constraints(assignment, partial=False, constraints=self.constraints)
                if sat:
                    stats.solutions_found += 1
                    all_solutions.append(dict(assignment))
                else:
                    stats.backtracks_count += 1
                return

            var = var_order[depth]
            for val in initial_domains[var]:
                trial = dict(assignment)
                trial[var] = val
                stats.constraint_checks += 1
                sat, _ = check_constraints(trial, partial=True, constraints=self.constraints)
                if sat:
                    backtrack_inc(trial, depth + 1)
                else:
                    stats.backtracks_count += 1

        backtrack_inc({}, 0)
        stats.time_ms = (time.perf_counter() - t0) * 1000.0
        return all_solutions, stats

    def solve_all_heuristics(self) -> tuple[list[dict], CSPStats]:
        """
        Varian 3: Backtracking + Heuristik Cerdas (MRV + Degree + LCV)
        - Variabel dipilih dinamis menggunakan MRV (Minimum Remaining Values)
          dengan Degree Heuristic sebagai tie-breaker.
        - Nilai diurutkan dengan LCV (Least Constraining Value).
        - Pengecekan konsistensi parsial bertahap, tanpa pruning domain unassigned.
        """
        t0 = time.perf_counter()
        stats = CSPStats()
        initial_domains = self.get_initial_domains()
        all_solutions = []

        def backtrack_heur(assignment: dict, domains: dict[str, list[str]]):
            stats.nodes_visited += 1

            if len(assignment) == len(self.variables):
                stats.constraint_checks += 1
                sat, _ = check_constraints(assignment, partial=False, constraints=self.constraints)
                if sat:
                    stats.solutions_found += 1
                    all_solutions.append(dict(assignment))
                else:
                    stats.backtracks_count += 1
                return

            var = self.select_unassigned_variable(assignment, domains, use_mrv=True)
            ordered_vals = self.order_domain_values(var, assignment, domains, use_lcv=True)

            for val in ordered_vals:
                trial = dict(assignment)
                trial[var] = val
                stats.constraint_checks += 1
                sat, _ = check_constraints(trial, partial=True, constraints=self.constraints)
                if sat:
                    backtrack_heur(trial, domains)
                else:
                    stats.backtracks_count += 1

        backtrack_heur({}, initial_domains)
        stats.time_ms = (time.perf_counter() - t0) * 1000.0
        return all_solutions, stats

    def solve_all_fc(self) -> tuple[list[dict], CSPStats]:
        """
        Varian 4: Backtracking + MRV + Degree + LCV + Forward Checking (FC)
        - Heuristik MRV + Degree + LCV aktif.
        - Forward Checking aktif: memangkas domain unassigned setiap kali nilai
          ditetapkan. Deteksi kegagalan cabang (wipeout) secara dini.
        """
        t0 = time.perf_counter()
        stats = CSPStats()
        initial_domains = self.get_initial_domains()
        all_solutions = []

        def backtrack_fc(assignment: dict, domains: dict[str, list[str]]):
            stats.nodes_visited += 1

            if len(assignment) == len(self.variables):
                stats.constraint_checks += 1
                sat, _ = check_constraints(assignment, partial=False, constraints=self.constraints)
                if sat:
                    stats.solutions_found += 1
                    all_solutions.append(dict(assignment))
                else:
                    stats.backtracks_count += 1
                return

            var = self.select_unassigned_variable(assignment, domains, use_mrv=True)
            ordered_vals = self.order_domain_values(var, assignment, domains, use_lcv=True)

            for val in ordered_vals:
                trial = dict(assignment)
                trial[var] = val

                stats.constraint_checks += 1
                sat, _ = check_constraints(trial, partial=True, constraints=self.constraints)
                if not sat:
                    stats.backtracks_count += 1
                    continue

                fc_ok, next_domains, pr_cnt = self.forward_check(var, val, assignment, domains)
                stats.pruned_values_count += pr_cnt
                stats.constraint_checks += pr_cnt
                if not fc_ok:
                    stats.backtracks_count += 1
                    continue

                backtrack_fc(trial, next_domains)

        backtrack_fc({}, initial_domains)
        stats.time_ms = (time.perf_counter() - t0) * 1000.0
        return all_solutions, stats

    def solve_all(self, use_mrv: bool = True, use_fc: bool = True) -> tuple[list[dict], CSPStats]:
        """
        Mencari SELURUH kombinasi solusi yang valid.
        Kompatibilitas mundur dengan pemanggilan solve_all sebelumnya.
        """
        if use_fc and use_mrv:
            return self.solve_all_fc()
        elif use_mrv:
            return self.solve_all_heuristics()
        else:
            return self.solve_all_bt_incremental()

    def evaluate_loadout_utility(self, loadout: dict) -> float:
        """
        Menghitung skor utilitas bawaan sebuah loadout.
        Skor = bonus ATK*4 + bonus HP*1.2 + bonus DEF*60 + bonus Potion*8 + bonus Dmg*1.5.
        """
        atk_bonus = 0
        hp_bonus = 0
        def_bonus = 0.0
        potion_bonus = 0
        boss_penalty = 0

        for slot, val in loadout.items():
            if val:
                it = get_item_dict(slot, val)
                eff = it.get("effects", {})
                atk_bonus += eff.get("attack_bonus", 0)
                hp_bonus += eff.get("max_hp_bonus", 0)
                def_bonus += eff.get("defend_bonus", 0.0)
                potion_bonus += eff.get("potion_count_bonus", 0) + eff.get("potion_heal_bonus", 0) // 5
                boss_penalty += eff.get("boss_hp_penalty", 0)
                if eff.get("start_defending", False):
                    def_bonus += 0.10

        return (atk_bonus * 4.0) + (hp_bonus * 1.2) + (def_bonus * 60.0) + (potion_bonus * 8.0) + (boss_penalty * 1.5)

    def best_loadout(self, sim_fn=None, top_k: int = 5) -> tuple[dict, CSPStats]:
        """
        Mencari loadout terbaik dari semua solusi legal.
        - Tahap 1: Evaluasi cepat seluruh solusi legal dengan evaluate_loadout_utility.
        - Tahap 2: Ambil top-K kandidat dan tampilkan skornya pada modal inspeksi F4 tab CSP.
        - Tahap 3: Pilih kandidat peringkat teratas (atau evaluasi mendalam dengan sim_fn jika diberikan).
        """
        solutions, stats = self.solve_all_fc()
        if not solutions:
            return dict(config.CSP_DEFAULT_LOADOUT), stats

        scored_candidates = []
        for sol in solutions:
            u_score = self.evaluate_loadout_utility(sol)
            if sim_fn is not None:
                final_score = sim_fn(sol)
            else:
                final_score = u_score

            scored_candidates.append({
                "loadout": sol,
                "utility": round(u_score, 1),
                "score": round(final_score, 1),
                "cost": calculate_cost(sol),
                "weight": calculate_weight(sol),
                "name": f"{sol.get('WEAPON','-')} | {sol.get('ARMOR','-')} | {sol.get('CHARM','-')}"
            })

        scored_candidates.sort(key=lambda x: x["score"], reverse=True)
        self.top_candidates = scored_candidates[:top_k]

        best = self.top_candidates[0]["loadout"] if self.top_candidates else solutions[0]
        return best, stats

        return best or dict(config.CSP_DEFAULT_LOADOUT), stats


# ==============================================================================
# FUNGSI MURNI PENERAPAN LOADOUT PADA BATTLE STATE
# ==============================================================================
def apply_loadout(initial_state: BattleState, loadout: dict, base_potion_count: Optional[int] = None) -> BattleState:
    """
    Fungsi murni: Mengembalikan copy BattleState baru yang sudah diperbarui
    oleh efek perlengkapan loadout CSP, tanpa efek samping atau merusak input.

    Aksi player TETAP HANYA 3: ATTACK, POTION, DEFEND.
    Efek loadout hanya mengubah variabel numerik state (HP, ATK bonus, dsb).
    Jumlah potion awal battle dapat disinkronkan dari inventori hero (base_potion_count).
    """
    new_state = initial_state.clone()
    new_state.loadout = dict(loadout)

    if base_potion_count is not None:
        new_state.potion_count = max(0, int(base_potion_count))

    total_atk_bonus = 0
    total_hp_bonus = 0
    total_potion_count_bonus = 0
    total_potion_heal_bonus = 0
    total_defend_bonus = 0.0
    start_defending = False
    boss_hp_penalty = 0

    for slot, val in loadout.items():
        if val:
            it = get_item_dict(slot, val)
            eff = it.get("effects", {})
            total_atk_bonus += eff.get("attack_bonus", 0)
            total_hp_bonus += eff.get("max_hp_bonus", 0)
            total_potion_count_bonus += eff.get("potion_count_bonus", 0)
            total_potion_heal_bonus += eff.get("potion_heal_bonus", 0)
            total_defend_bonus += eff.get("defend_bonus", 0.0)
            if eff.get("start_defending", False):
                start_defending = True
            boss_hp_penalty += eff.get("boss_hp_penalty", 0)

    new_state.hero_attack_bonus = total_atk_bonus
    new_state.hero_defend_bonus = total_defend_bonus
    new_state.potion_heal_bonus = total_potion_heal_bonus

    if total_hp_bonus > 0:
        new_state.player_max_hp += total_hp_bonus
        new_state.player_hp = new_state.player_max_hp

    if total_potion_count_bonus > 0:
        new_state.potion_count += total_potion_count_bonus

    if start_defending:
        new_state.player_defending = True

    if boss_hp_penalty > 0:
        new_state.boss_hp = max(1, new_state.boss_hp - boss_hp_penalty)

    return new_state

