"""
local_search.py - LOCAL SEARCH: Boss Adaptive Tuning & Opponent Modeling

Boss mengamati gaya bermain Hero selama pertarungan dan mengadaptasi bobot
evaluasi Minimax w = (w_hp, w_def, w_hvy, w_res).

Modul ini mengimplementasikan:
  1. OpponentModel:
     - Pelacakan frekuensi aksi Hero (ATTACK, POTION, DEFEND)
     - Laplace smoothing (alpha = 1.0)
     - Prior support berdasarkan perlengkapan loadout Hero
  2. Evaluasi Fitness:
     - Simulasi cepat N rollout (rollouts deterministik dengan seed)
     - Evaluasi performa bobot terhadap gaya bermain Hero
  3. Algoritma Local Search:
     - Hill Climbing dengan Random Restarts
     - Simulated Annealing dengan Geometric Cooling & Acceptance Probability
     - Clamping ke BOSS_WEIGHT_BOUNDS
     - Batas waktu komputasi ketat (150-300 ms)
  4. BossRotationPlanner (Bonus CSP):
     - Rencana sekuens aksi Boss 4 ronde ke depan (t+1..t+4)
     - Cooldown Heavy Attack & batas Heal sebagai constraint
     - Dipakai sebagai move ordering prior di Minimax
"""

from dataclasses import dataclass, field
import math
import random
import time
import config
from ai.adversarial import (
    BattleState,
    apply_action,
    evaluate,
    boss_actions,
    hero_actions,
    is_terminal
)


# ==============================================================================
# MODEL LAWAN (OPPONENT MODEL DENGAN LAPLACE SMOOTHING)
# ==============================================================================
class OpponentModel:
    """
    Model estimasi probabilitas aksi Hero.
    Menggunakan penghitungan frekuensi + Laplace smoothing + prior dari loadout.
    """

    def __init__(self, loadout: dict = None):
        self.action_counts = {"ATTACK": 0, "POTION": 0, "DEFEND": 0}
        self.total_observed = 0
        self.prior_counts = {"ATTACK": 1.0, "POTION": 1.0, "DEFEND": 1.0}
        self._init_priors_from_loadout(loadout)

    def _init_priors_from_loadout(self, loadout: dict = None):
        """Menyesuaikan prior keyakinan awal berdasarkan loadout Hero."""
        if not loadout:
            return

        weapon = loadout.get("WEAPON", "")
        armor = loadout.get("ARMOR", "")
        charm = loadout.get("CHARM", "")
        consumable = loadout.get("CONSUMABLE", "")

        # Senjata agresif -> Hero cenderung serang
        if weapon in ("Kapak Berat", "Tongkat Api"):
            self.prior_counts["ATTACK"] += 2.0
        elif weapon == "Belati Cepat":
            self.prior_counts["ATTACK"] += 1.0

        # Potion ekstra -> Hero cenderung minum potion
        if consumable == "Potion Ekstra" or charm == "Jimat Penawar":
            self.prior_counts["POTION"] += 2.0

        # Armor tebal atau perisai kertas -> Hero defensif
        if armor == "Besi" or consumable == "Perisai Kertas":
            self.prior_counts["DEFEND"] += 2.0

    def record_action(self, action: str):
        """Mencatat aksi aktual yang dilakukan Hero di battle."""
        if action in self.action_counts:
            self.action_counts[action] += 1
            self.total_observed += 1

    def get_distribution(self) -> dict[str, float]:
        """
        Menghitung probabilitas setiap aksi Hero dengan Laplace smoothing.
        P(a) = (count(a) + prior(a)) / (total_observed + sum(priors))
        """
        denominator = self.total_observed + sum(self.prior_counts.values())
        return {
            act: (self.action_counts[act] + self.prior_counts[act]) / denominator
            for act in ("ATTACK", "POTION", "DEFEND")
        }

    def sample_action(self, rng: random.Random, available_actions: list[str]) -> str:
        """Mengambil sampel aksi Hero berdasarkan distribusi probabilitas."""
        dist = self.get_distribution()
        # Normalisasi ke aksi legal saja
        legal_dist = {a: dist.get(a, 0.0) for a in available_actions}
        total = sum(legal_dist.values())
        if total <= 0:
            return available_actions[0]

        r = rng.random() * total
        acc = 0.0
        for act, p in legal_dist.items():
            acc += p
            if r <= acc:
                return act
        return available_actions[-1]


# ==============================================================================
# FUNGSI FITNESS (SIMULASI FAST ROLLOUTS HALUS & KONTINU)
# ==============================================================================
def simulate_single_battle(initial_state: BattleState, weights: tuple,
                           opponent_model: OpponentModel, rng: random.Random,
                           max_sim_turns: int = 14) -> dict:
    """
    Simulasi satu pertempuran deterministik dengan ekspektasi aksi lawan:
    Mengembalikan statistik lengkap pertempuran untuk kalkulasi fitness halus.
    """
    state = initial_state.clone()
    boss_start_hp = state.boss_hp
    player_start_hp = state.player_hp
    dist = opponent_model.get_distribution()

    for _ in range(max_sim_turns):
        if is_terminal(state):
            break

        if state.turn == "player":
            acts = hero_actions(state)
            chosen_act = opponent_model.sample_action(rng, acts)
            state, _ = apply_action(state, "player", chosen_act, rng=rng)
        else:
            # Boss memilih aksi terbaik dengan 2-ply lookahead terbobot ekspektasi Hero
            acts = boss_actions(state)
            best_act = acts[0]
            best_score = -1e9
            for b_act in acts:
                child, _ = apply_action(state, "boss", b_act, rng=None)
                if is_terminal(child):
                    val = evaluate(child, weights=weights)
                else:
                    h_acts = hero_actions(child)
                    val = sum(dist.get(ha, 0.33) * evaluate(apply_action(child, "player", ha, rng=None)[0], weights=weights) for ha in h_acts)

                if val > best_score:
                    best_score = val
                    best_act = b_act

            state, _ = apply_action(state, "boss", best_act, rng=rng)

    boss_won = state.player_hp <= 0 or (state.boss_hp > state.player_hp and state.turn_number > config.BATTLE_MAX_TURNS)
    damage_dealt = max(0, player_start_hp - state.player_hp)
    damage_taken = max(0, boss_start_hp - state.boss_hp)
    return {
        "boss_won": boss_won,
        "damage_dealt": damage_dealt,
        "damage_taken": damage_taken,
        "rem_boss_hp": state.boss_hp,
        "rem_player_hp": state.player_hp,
        "turns": state.turn_number,
        "potions_used": config.HERO_INITIAL_POTIONS - state.potion_count
    }


def evaluate_fitness(weights: tuple, initial_state: BattleState,
                     opponent_model: OpponentModel,
                     sim_count: int = config.LOCAL_SEARCH_SIM_COUNT,
                     seed: int = config.LOCAL_SEARCH_SEED) -> float:
    """
    Menghitung skor kecocokan (fitness) kontinu dan halus:
      - Common Random Numbers (CRN): Setiap rollout k menggunakan seed deterministik
        sehingga perbandingan antar bobot kandidat adil dan bebas variansi acak.
      - Komponen Kontinu:
        1. Sisa HP Boss akhir (continuous percentage)
        2. Selisih HP akhir (continuous difference)
        3. Efisiensi ronde (kecepatan menang atau daya tahan saat kalah)
        4. Net damage (damage dealt - damage taken)
    """
    total_score = 0.0

    for k in range(sim_count):
        # CRN: Seed identik untuk rollout ke-k di setiap kandidat bobot
        rng = random.Random(seed * 7919 + k * 1013)
        res = simulate_single_battle(initial_state, weights, opponent_model, rng)

        boss_max_hp = max(1, initial_state.boss_max_hp)
        player_max_hp = max(1, initial_state.player_max_hp)

        boss_hp_ratio = res["rem_boss_hp"] / boss_max_hp
        player_hp_ratio = res["rem_player_hp"] / player_max_hp
        hp_diff_pct = (boss_hp_ratio - player_hp_ratio)

        if res["boss_won"]:
            game_score = 100.0 + boss_hp_ratio * 40.0 + max(0, 14 - res["turns"]) * 2.5
        elif res["rem_boss_hp"] <= 0:
            game_score = -60.0 + (res["damage_dealt"] / player_max_hp) * 25.0 + min(res["turns"], 14) * 1.5
        else:
            game_score = hp_diff_pct * 60.0

        net_dmg = (res["damage_dealt"] - res["damage_taken"]) * 0.25
        hp_diff_continuous = hp_diff_pct * 30.0

        total_score += (game_score + net_dmg + hp_diff_continuous)

    return round(total_score / max(1, sim_count), 2)


def analyze_weight_landscape(initial_state: BattleState, opponent_model: OpponentModel,
                            n_points: int = 50, seed: int = 999) -> list[tuple[tuple, float]]:
    """
    Evaluasi 50 titik acak di ruang bobot untuk membuktikan kontur & gradien lanskap fitness.
    Menggunakan Common Random Numbers (CRN) dengan fixed seed.
    """
    rng = random.Random(seed)
    results = []
    for _ in range(n_points):
        w = tuple(round(rng.uniform(low, high), 2) for low, high in config.BOSS_WEIGHT_BOUNDS)
        fit = evaluate_fitness(w, initial_state, opponent_model, sim_count=20, seed=seed)
        results.append((w, fit))
    return results


def measure_weight_sensitivity(n_states: int = 100, seed: int = 42) -> dict:
    """
    Mengukur persentase state pertempuran di mana keputusan aksi terbaik Boss Minimax
    berubah akibat perubahan bobot evaluasi (Sensitivitas Minimax terhadap Bobot).
    """
    rng = random.Random(seed)
    from ai.adversarial import MinimaxBattleAI

    w_default = (1.0, 14.0, 18.0, 7.0)
    w_aggress = (1.0, 4.0, 32.0, 2.0)
    w_defend  = (1.0, 26.0, 6.0, 14.0)

    ai_def = MinimaxBattleAI(depth=config.MINIMAX_DEPTH_NORMAL, weights=w_default)
    ai_agg = MinimaxBattleAI(depth=config.MINIMAX_DEPTH_NORMAL, weights=w_aggress)
    ai_dfs = MinimaxBattleAI(depth=config.MINIMAX_DEPTH_NORMAL, weights=w_defend)

    changed_moves = 0
    decision_records = []

    for _ in range(n_states):
        st = BattleState(
            player_hp=rng.randint(20, 100),
            boss_hp=rng.randint(20, 120),
            potion_count=rng.randint(0, 3),
            boss_heal_count=rng.randint(0, 2),
            boss_heavy_cd=rng.randint(0, 2),
            player_defending=rng.choice([True, False]),
            boss_defending=rng.choice([True, False]),
            turn="boss"
        )

        act_def, _, _ = ai_def.choose_move(st)
        act_agg, _, _ = ai_agg.choose_move(st)
        act_dfs, _, _ = ai_dfs.choose_move(st)

        has_change = (act_agg != act_def) or (act_dfs != act_def)
        if has_change:
            changed_moves += 1

        decision_records.append({
            "state": (st.player_hp, st.boss_hp, st.boss_heavy_cd, st.boss_heal_count),
            "act_default": act_def,
            "act_agg": act_agg,
            "act_dfs": act_dfs,
            "changed": has_change
        })

    change_pct = round((changed_moves / max(1, n_states)) * 100.0, 1)
    return {
        "n_states": n_states,
        "changed_moves": changed_moves,
        "change_pct": change_pct,
        "records": decision_records
    }


def calculate_wilson_ci(wins: int, total: int, z: float = 1.96) -> tuple[float, float, float]:
    """
    Menghitung 95% Wilson Score Confidence Interval untuk proporsi win rate:
    p_hat, ci_low, ci_high.
    """
    if total <= 0:
        return 0.0, 0.0, 0.0
    p = wins / total
    denom = 1.0 + (z**2) / total
    center = (p + (z**2) / (2.0 * total)) / denom
    margin = (z * math.sqrt((p * (1.0 - p) / total) + (z**2) / (4.0 * total**2))) / denom
    ci_low = max(0.0, round((center - margin) * 100.0, 1))
    ci_high = min(100.0, round((center + margin) * 100.0, 1))
    return round(p * 100.0, 1), ci_low, ci_high


def run_held_out_validation(hero_state: BattleState, default_weights: tuple,
                            tuned_weights: tuple, archetypes: list,
                            matches_per_archetype: int = 500,
                            base_seed: int = 12345) -> list[dict]:
    """
    Validasi Held-Out 500 pertandingan per arketipe hero dengan seed independen
    dan kalkulasi 95% Confidence Interval (Wilson Score).
    """
    results = []
    for arch_name, dist_probs in archetypes:
        model = OpponentModel()
        model.prior_counts = {
            "ATTACK": dist_probs[0] * 10.0,
            "POTION": dist_probs[1] * 10.0,
            "DEFEND": dist_probs[2] * 10.0,
        }

        # 1. Evaluasi Bobot Default
        def_wins = 0
        for i in range(matches_per_archetype):
            rng = random.Random(base_seed + i * 31 + 7)
            res = simulate_single_battle(hero_state, default_weights, model, rng)
            if res["boss_won"]:
                def_wins += 1

        # 2. Evaluasi Bobot Hasil Tuned Local Search (Independent seed)
        tuned_wins = 0
        for i in range(matches_per_archetype):
            rng = random.Random(base_seed + 50000 + i * 31 + 7)
            res = simulate_single_battle(hero_state, tuned_weights, model, rng)
            if res["boss_won"]:
                tuned_wins += 1

        p_def, def_low, def_high = calculate_wilson_ci(def_wins, matches_per_archetype)
        p_tuned, tuned_low, tuned_high = calculate_wilson_ci(tuned_wins, matches_per_archetype)
        delta_p = round(p_tuned - p_def, 1)

        results.append({
            "archetype": arch_name,
            "matches": matches_per_archetype,
            "def_wins": def_wins,
            "def_rate": p_def,
            "def_ci": (def_low, def_high),
            "tuned_wins": tuned_wins,
            "tuned_rate": p_tuned,
            "tuned_ci": (tuned_low, tuned_high),
            "delta_rate": delta_p,
        })
    return results


def clamp_weights(w: list[float]) -> tuple[float, float, float, float]:
    """Memastikan bobot selalu berada dalam batasan konfigurasi BOSS_WEIGHT_BOUNDS."""
    clamped = []
    for val, (low, high) in zip(w, config.BOSS_WEIGHT_BOUNDS):
        clamped.append(round(min(max(val, low), high), 2))
    return tuple(clamped)


# ==============================================================================
# ALGORITMA 1: HILL CLIMBING DENGAN RANDOM RESTARTS
# ==============================================================================
class HillClimbingTuner:
    """
    Penala bobot Minimax menggunakan Hill Climbing dengan Steepest Ascent
    dan Random Restarts.
    """

    def __init__(self, restarts: int = config.LOCAL_SEARCH_HC_RESTARTS,
                 step_size: float = config.LOCAL_SEARCH_STEP,
                 max_time_ms: float = config.LOCAL_SEARCH_MAX_TIME_MS,
                 seed: int = config.LOCAL_SEARCH_SEED):
        self.restarts = restarts
        self.step_size = step_size
        self.max_time_ms = max_time_ms
        self.seed = seed
        self.rng = random.Random(seed)

    def tune(self, current_weights: tuple, initial_state: BattleState,
             opponent_model: OpponentModel) -> tuple[tuple, float, dict]:
        """
        Melakukan penalaan bobot. Mengembalikan (best_weights, best_fitness, stats).
        """
        t0 = time.perf_counter()
        best_overall_weights = clamp_weights(list(current_weights))
        best_overall_fitness = evaluate_fitness(best_overall_weights, initial_state, opponent_model, seed=self.seed)

        stats = {
            "algorithm": "Hill Climbing",
            "iterations": 0,
            "restarts": 0,
            "initial_fitness": best_overall_fitness,
            "final_fitness": best_overall_fitness,
            "time_ms": 0.0,
            "history": [(0, best_overall_fitness)],
        }

        step_count = 0

        for r in range(self.restarts):
            # Cek batas waktu komputasi
            elapsed = (time.perf_counter() - t0) * 1000.0
            if elapsed >= self.max_time_ms:
                break

            stats["restarts"] += 1

            if r == 0:
                cur_w = best_overall_weights
                cur_fit = best_overall_fitness
            else:
                # Random restart dalam batas
                rand_w = [
                    self.rng.uniform(low, high)
                    for low, high in config.BOSS_WEIGHT_BOUNDS
                ]
                cur_w = clamp_weights(rand_w)
                cur_fit = evaluate_fitness(cur_w, initial_state, opponent_model, seed=self.seed + step_count)

            # Hill climbing lokal
            improved = True
            while improved:
                step_count += 1
                stats["iterations"] += 1
                improved = False

                elapsed = (time.perf_counter() - t0) * 1000.0
                if elapsed >= self.max_time_ms:
                    break

                # Generate tetangga: variasikan setiap dimensi (+-step)
                best_neighbor = None
                best_neighbor_fit = cur_fit

                for idx in range(len(cur_w)):
                    if (time.perf_counter() - t0) * 1000.0 >= self.max_time_ms:
                        break
                    for delta in (-self.step_size, self.step_size):
                        if (time.perf_counter() - t0) * 1000.0 >= self.max_time_ms:
                            break
                        neighbor = list(cur_w)
                        neighbor[idx] += delta
                        clamped_neighbor = clamp_weights(neighbor)

                        fit = evaluate_fitness(clamped_neighbor, initial_state, opponent_model,
                                               seed=self.seed + step_count)
                        if fit > best_neighbor_fit:
                            best_neighbor_fit = fit
                            best_neighbor = clamped_neighbor

                if best_neighbor is not None and best_neighbor_fit > cur_fit:
                    cur_w = best_neighbor
                    cur_fit = best_neighbor_fit
                    improved = True
                    stats["history"].append((step_count, cur_fit))

            if cur_fit > best_overall_fitness:
                best_overall_fitness = cur_fit
                best_overall_weights = cur_w

        stats["time_ms"] = (time.perf_counter() - t0) * 1000.0
        stats["final_fitness"] = best_overall_fitness
        return best_overall_weights, best_overall_fitness, stats


# ==============================================================================
# ALGORITMA 2: SIMULATED ANNEALING
# ==============================================================================
class SimulatedAnnealingTuner:
    """
    Penala bobot Minimax menggunakan Simulated Annealing:
    - Geometric cooling: T <- alpha * T
    - Probabilitas penerimaan: exp(delta_E / T)
    - Merekam fitness trajectory untuk digambar pada panel F4
    """

    def __init__(self, t0: float = config.SA_TUNING_T0,
                 alpha: float = config.SA_TUNING_ALPHA,
                 min_t: float = config.SA_TUNING_MIN_T,
                 step_size: float = config.LOCAL_SEARCH_STEP,
                 max_time_ms: float = config.LOCAL_SEARCH_MAX_TIME_MS,
                 seed: int = config.LOCAL_SEARCH_SEED):
        self.t0 = t0
        self.alpha = alpha
        self.min_t = min_t
        self.step_size = step_size
        self.max_time_ms = max_time_ms
        self.seed = seed
        self.rng = random.Random(seed)

    def tune(self, current_weights: tuple, initial_state: BattleState,
             opponent_model: OpponentModel) -> tuple[tuple, float, dict]:
        """
        Melakukan penalaan bobot dengan Simulated Annealing.
        Mengembalikan (best_weights, best_fitness, stats).
        """
        t_start = time.perf_counter()
        cur_w = clamp_weights(list(current_weights))
        cur_fit = evaluate_fitness(cur_w, initial_state, opponent_model, seed=self.seed)

        best_w = cur_w
        best_fit = cur_fit

        stats = {
            "algorithm": "Simulated Annealing",
            "iterations": 0,
            "accepted_worse": 0,
            "initial_fitness": cur_fit,
            "final_fitness": cur_fit,
            "time_ms": 0.0,
            "history": [(0, cur_fit)],
        }

        T = self.t0
        step = 0

        while T > self.min_t:
            step += 1
            stats["iterations"] += 1

            # Cek batas waktu komputasi (150-300 ms)
            elapsed = (time.perf_counter() - t_start) * 1000.0
            if elapsed >= self.max_time_ms:
                break

            # Pilih tetangga acak: ubah 1-2 dimensi acak
            neighbor = list(cur_w)
            dim_to_change = self.rng.sample(range(len(neighbor)), k=self.rng.choice([1, 2]))
            for d in dim_to_change:
                perturbation = self.rng.uniform(-self.step_size, self.step_size)
                neighbor[d] += perturbation

            clamped_neighbor = clamp_weights(neighbor)
            new_fit = evaluate_fitness(clamped_neighbor, initial_state, opponent_model,
                                       seed=self.seed + step)

            delta_e = new_fit - cur_fit

            if delta_e > 0:
                # Perbaikan: selalu terima
                cur_w = clamped_neighbor
                cur_fit = new_fit
                if cur_fit > best_fit:
                    best_fit = cur_fit
                    best_w = cur_w
            else:
                # Worsening step: terima dengan probabilitas exp(delta_e / T)
                prob = math.exp(delta_e / max(0.0001, T))
                if self.rng.random() < prob:
                    cur_w = clamped_neighbor
                    cur_fit = new_fit
                    stats["accepted_worse"] += 1

            stats["history"].append((step, cur_fit))

            # Geometric cooling
            T *= self.alpha

        stats["time_ms"] = (time.perf_counter() - t_start) * 1000.0
        stats["final_fitness"] = best_fit
        return best_w, best_fit, stats


# ==============================================================================
# BOSS ROTATION PLANNER (BONUS CSP: 4-TURN ACTION SEQUENCE)
# ==============================================================================
class BossRotationPlanner:
    """
    CSP Perencana Rotasi Aksi Boss untuk 4 ronde ke depan (t+1..t+4).
    Variabel : T1, T2, T3, T4
    Domain   : ['ATTACK', 'HEAVY_ATTACK', 'DEFEND', 'HEAL']
    Batasan  :
      1. Cooldown Heavy Attack: Heavy Attack hanya boleh muncul 1x per 4 ronde
         dan menghormati boss_heavy_cd saat ini.
      2. Limit Heal: Heal maksimal 1x dalam 4 ronde dan tidak melebihi sisa heal boss.
      3. No Triple Spam: Tidak boleh memilih aksi yang sama 3x berturut-turut.
    """

    def __init__(self):
        self.cached_plan = []
        self.plan_start_turn = 0

    def generate_plan(self, state: BattleState) -> list[str]:
        """
        Menyelesaikan CSP untuk menghasilkan 4 aksi berurutan.
        """
        slots = ["T1", "T2", "T3", "T4"]
        base_domain = ["ATTACK", "HEAVY_ATTACK", "DEFEND"]
        if state.boss_heal_count > 0 and state.boss_hp < state.boss_max_hp * 0.7:
            base_domain.append("HEAL")

        solution = []

        def is_valid(sequence: list[str]) -> bool:
            # Cooldown Heavy Attack
            heavy_indices = [i for i, a in enumerate(sequence) if a == "HEAVY_ATTACK"]
            if len(heavy_indices) > 1:
                return False
            if heavy_indices and state.boss_heavy_cd > 0:
                # Jika CD saat ini masih ada, T1..Tcd tidak boleh heavy attack
                if heavy_indices[0] < state.boss_heavy_cd:
                    return False

            # Limit Heal
            heal_count = sequence.count("HEAL")
            if heal_count > 1 or heal_count > state.boss_heal_count:
                return False

            # No Triple Spam (3x aksi sama berturut-turut)
            for i in range(len(sequence) - 2):
                if sequence[i] == sequence[i + 1] == sequence[i + 2]:
                    return False

            return True

        def backtrack(current: list[str]) -> list[str] | None:
            if len(current) == 4:
                return current if is_valid(current) else None

            # Prioritaskan aksi agresif bila HP hero rendah
            domain_order = list(base_domain)
            if state.player_hp < 40 and "HEAVY_ATTACK" in domain_order:
                domain_order.remove("HEAVY_ATTACK")
                domain_order.insert(0, "HEAVY_ATTACK")

            for act in domain_order:
                trial = current + [act]
                if is_valid(trial):
                    res = backtrack(trial)
                    if res is not None:
                        return res
            return None

        plan = backtrack([])
        if plan is None:
            plan = ["ATTACK", "DEFEND", "ATTACK", "HEAVY_ATTACK"]

        self.cached_plan = plan
        self.plan_start_turn = state.turn_number
        return plan

    def get_next_action(self, current_turn: int) -> str | None:
        """Mengambil aksi terencana untuk ronde saat ini jika masih dalam rentang."""
        offset = current_turn - self.plan_start_turn
        if 0 <= offset < len(self.cached_plan):
            return self.cached_plan[offset]
        return None


# ==============================================================================
# HELPER DESKRIPSI ADAPTASI BOSS
# ==============================================================================
def describe_adaptation(old_w: tuple, new_w: tuple) -> str:
    """Membentuk pesan log battle ketika Boss mengubah bobot evaluasinya."""
    dw_hp = new_w[0] - old_w[0]
    dw_def = new_w[1] - old_w[1]
    dw_hvy = new_w[2] - old_w[2]
    dw_res = new_w[3] - old_w[3]

    reasons = []
    if dw_hvy > 0.5:
        reasons.append("lebih agresif & mematikan (HEAVY_ATTACK)")
    elif dw_hvy < -0.5:
        reasons.append("mengurangi serangan ceroboh")

    if dw_def > 0.8:
        reasons.append("memperketat pertahanan (DEFEND)")
    elif dw_def < -0.8:
        reasons.append("mengurangi sikap pasif")

    if dw_res > 0.8:
        reasons.append("menekan regenerasi potion Hero")

    if dw_hp > 0.5:
        reasons.append("fokus eliminasi selisih HP")

    if not reasons:
        return "Boss membaca pergerakan Hero dan menyempurnakan kalkulasinya!"
    return f"Boss beradaptasi: {', '.join(reasons)}!"

