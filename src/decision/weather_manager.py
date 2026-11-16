"""
src/decision/weather_manager.py
Modul integrasi sistem Cuaca Probabilistik, Papan Pengumuman Bayes,
Zona Rawan Banjir, dan Evaluasi Kebijakan Dinamis (Putaran 3).
"""

import os
import math
import random
from typing import Dict, List, Tuple, Optional, Any
import pygame

import config
from decision.probability import bayes_update, expected_value, expected_utility
from decision.mdp import value_iteration, extract_policy, compute_q
from decision.flood_model import create_flood_mdp


class WeatherManager:
    """
    Pengelola siklus cuaca dunia, status banjir tersembunyi,
    dan keyakinan Bayesian Hero/AI.
    """

    def __init__(self, cycle_duration: float = getattr(config, "WEATHER_CYCLE_SECONDS", 240.0),
                 seed: Optional[int] = 20261021):
        self.cycle_duration = cycle_duration
        self.timer: float = 0.0
        self.day: int = 1
        self.rng = random.Random(seed) if seed is not None else random.Random()

        # Status banjir nyata (tersembunyi dari pemain & agen AI)
        self.is_flooded: bool = (self.rng.random() < config.FLOOD_PRIOR_DEFAULT)

        # Belief / keyakinan AI terhadap probabilitas banjir
        self.belief_p_flood: float = config.FLOOD_PRIOR_DEFAULT
        self.prior_p_flood: float = config.FLOOD_PRIOR_DEFAULT

        # Interaksi papan pengumuman
        self.has_read_board: bool = False
        self.last_evidence: Optional[str] = None
        self.forced_evidence: Optional[str] = None
        self.evidence_history: List[Dict[str, Any]] = []

        # Kebijakan optimal saat ini dari Value Iteration
        self.current_mdp = None
        self.current_V: Dict[str, float] = {}
        self.current_Q: Dict[Tuple[str, str], float] = {}
        self.current_policy: Dict[str, str] = {}
        self.policy_choice: str = "Pintas"  # "Pintas" atau "Raya"

        # Definisi zona rawan banjir di pantai/sungai (koridor menuju gerbang)
        # Koordinat tile: x=2016..2368, y=864..960
        self.flood_rect = (2016, 864, 352, 96)
        self.safe_retreat_pos = (1984.0, 832.0)

        # Hitung kebijakan awal
        self.recalculate_policy()

    @property
    def day_counter(self) -> int:
        return self.day

    @property
    def cycle_timer(self) -> float:
        return self.timer

    @property
    def prior_flood(self) -> float:
        return self.prior_p_flood

    @property
    def belief_flood(self) -> float:
        return self.belief_p_flood

    @belief_flood.setter
    def belief_flood(self, val: float):
        self.belief_p_flood = val

    @property
    def actual_flood(self) -> bool:
        return self.is_flooded

    @actual_flood.setter
    def actual_flood(self, val: bool):
        self.is_flooded = val

    @property
    def notice_read_today(self) -> bool:
        return self.has_read_board

    @property
    def optimal_policy(self) -> str:
        return self.policy_choice

    @property
    def flood_zone_rect(self) -> pygame.Rect:
        return pygame.Rect(self.flood_rect)

    def _update_policy(self):
        """Alias untuk recalculate_policy."""
        self.recalculate_policy()

    def get_expected_utilities(self) -> Tuple[float, float]:
        qp = self.current_Q.get(("Warung", "Pintas"), 0.0)
        qr = self.current_Q.get(("Warung", "Raya"), 0.0)
        return qp, qr

    def update(self, dt: float) -> Optional[str]:
        """Update timer cuaca tiap frame game loop."""
        self.timer += dt
        if self.timer >= self.cycle_duration:
            return self.new_day()
        return None

    def new_day(self, force_flood: Optional[bool] = None) -> str:
        """Memulai hari cuaca baru dan membangkitkan kondisi tersembunyi baru."""
        self.day += 1
        self.timer = 0.0
        if force_flood is not None:
            self.is_flooded = force_flood
        else:
            self.is_flooded = (self.rng.random() < config.FLOOD_PRIOR_DEFAULT)

        self.prior_p_flood = config.FLOOD_PRIOR_DEFAULT
        self.belief_p_flood = config.FLOOD_PRIOR_DEFAULT
        self.has_read_board = False
        self.last_evidence = None

        old_policy = self.policy_choice
        self.recalculate_policy()

        msg = f"[CUACA HARI #{self.day}] Siklus cuaca baru dimulai. P(Banjir) reset ke prior {self.belief_p_flood:.2f}."
        if old_policy != self.policy_choice:
            msg += f" Pemicu kebijakan: {self.policy_choice}!"
        return msg

    def read_notice_board(self) -> Tuple[bool, str, float]:
        """
        Membaca papan pengumuman cuaca desa ([E]).
        Menghasilkan bukti observasi berdasar kondisi aktual dengan likelihood resmi,
        lalu memperbarui keyakinan AI dengan aturan Bayes.
        """
        if self.has_read_board:
            return False, f"Papan cuaca hari #{self.day} sudah Anda baca sebelumnya.", self.belief_p_flood

        # Bangkitkan bukti sesuai kondisi nyata (atau paksa deterministik untuk demo)
        # P(Berita|Banjir) = 0.90, P(Berita|NoBanjir) = 0.10
        if self.forced_evidence is not None:
            evidence = self.forced_evidence
        elif self.is_flooded:
            roll = self.rng.random()
            if roll < config.P_NEWS_GIVEN_FLOOD:
                evidence = "air mulai naik"
            else:
                evidence = "langit cerah"
        else:
            roll = self.rng.random()
            if roll < config.P_NEWS_GIVEN_NO_FLOOD:
                evidence = "air mulai naik"
            else:
                evidence = "langit cerah"

        old_prior = self.belief_p_flood
        if evidence == "air mulai naik":
            post, p_e = bayes_update(old_prior, config.P_NEWS_GIVEN_FLOOD, config.P_NEWS_GIVEN_NO_FLOOD)
        else:
            post, p_e = bayes_update(old_prior, config.P_SUNNY_GIVEN_FLOOD, config.P_SUNNY_GIVEN_NO_FLOOD)

        self.belief_p_flood = post
        self.has_read_board = True
        self.last_evidence = evidence

        old_policy = self.policy_choice
        self.recalculate_policy()

        log_item = {
            "day": self.day,
            "evidence": evidence,
            "prior": old_prior,
            "posterior": post,
            "is_flooded_real": self.is_flooded,
            "policy_before": old_policy,
            "policy_after": self.policy_choice
        }
        self.evidence_history.append(log_item)

        msg = (f"[PAPAN CUACA] Bukti: \"{evidence.upper()}\" | "
               f"P(Banjir) {old_prior:.2f} -> {post:.2f} | "
               f"Kebijakan: {self.policy_choice}")
        if old_policy != self.policy_choice:
            msg += f" (POLICY BERUBAH: {old_policy} -> {self.policy_choice})!"

        return True, msg, self.belief_p_flood

    def recalculate_policy(self):
        """Menyelesaikan Value Iteration pada model MDP dengan parameter f = belief_p_flood."""
        self.current_mdp = create_flood_mdp(f=self.belief_p_flood)
        v, policy, history = value_iteration(self.current_mdp, tolerance=config.DECISION_VI_TOLERANCE,
                                             max_iterations=config.DECISION_VI_MAX_ITER)
        self.current_V = v
        self.current_policy = policy
        self.current_Q = {}

        # Hitung nilai Q untuk setiap aksi di Warung
        for act in self.current_mdp.actions("Warung"):
            self.current_Q[("Warung", act)] = compute_q(self.current_mdp, "Warung", act, v)

        # Di titik persimpangan 'Warung': Pintas vs Raya
        self.policy_choice = policy.get("Warung", "Pintas")

    def is_in_flood_zone(self, px: float, py: float) -> bool:
        """Memeriksa apakah koordinat entitas berada dalam zona rawan banjir."""
        rx, ry, rw, rh = self.flood_rect
        return (rx <= px <= rx + rw) and (ry <= py <= ry + rh)

    def find_nearest_dry_tile(self, hero_px: float, hero_py: float,
                              game_map: Optional[Any] = None, max_r: int = 15) -> Tuple[float, float]:
        """
        Mencari posisi tile kering terdekat di luar zona banjir rawan yang valid untuk berdiri (can_stand).
        Jika game_map tidak tersedia, fallback ke titik safe_retreat_pos standar.
        """
        if game_map is None:
            return self.safe_retreat_pos

        rx, ry, rw, rh = self.flood_rect
        start_tx = int(hero_px // 32)
        start_ty = int(hero_py // 32)
        w_tiles = getattr(game_map, "width", 2752) // 32
        h_tiles = getattr(game_map, "height", 1536) // 32

        best_pos: Optional[Tuple[float, float]] = None
        min_dist_sq = float("inf")

        for r in range(1, max_r + 1):
            for dx in range(-r, r + 1):
                for dy in range(-r, r + 1):
                    if max(abs(dx), abs(dy)) != r:
                        continue
                    tx = start_tx + dx
                    ty = start_ty + dy
                    if 0 <= tx < w_tiles and 0 <= ty < h_tiles:
                        px = tx * 32.0 + 16.0
                        py = ty * 32.0 + 16.0
                        # Harus di luar zona rawan banjir
                        if not (rx <= px <= rx + rw and ry <= py <= ry + rh):
                            hb = pygame.Rect(int(px - 7), int(py - 4), 14, 8)
                            if game_map.can_stand(hb):
                                d_sq = (px - hero_px) ** 2 + (py - hero_py) ** 2
                                if d_sq < min_dist_sq:
                                    min_dist_sq = d_sq
                                    best_pos = (px, py)
            if best_pos is not None:
                return best_pos

        return self.safe_retreat_pos

    def trigger_flood_flush(self, hero: Any, game_map: Optional[Any] = None) -> Tuple[bool, str]:
        """
        Jika banjir nyata aktif dan hero berada di zona rawan banjir,
        seret hero ke daratan kering TERDEKAT dan terapkan penalti waktu (-20s).
        NPC dan hewan tidak terpengaruh (hanya hero yang dapat terseret).
        """
        if not self.is_flooded:
            return False, ""

        if not self.is_in_flood_zone(hero.px, hero.py):
            return False, ""

        # Hero terperangkap banjir -> cari tile kering terdekat
        dry_pos = self.find_nearest_dry_tile(hero.px, hero.py, game_map)
        hero.px, hero.py = dry_pos
        if hasattr(hero, "play_action_animation"):
            hero.play_action_animation("swimming", 1.5)
        penalty = getattr(config, "FLOOD_PENALTY_TIME", 2.70)
        msg = f"[BANJIR BANDANG] Arus pantai menghanyutkan Anda ke tanah kering ({dry_pos[0]:.0f}, {dry_pos[1]:.0f})! Penalti waktu: -{penalty:.1f}s"
        return True, msg


# ==============================================================================
# EVALUASI MONTE CARLO (BAGIAN 6)
# ==============================================================================

def run_monte_carlo_evaluation(n_days: int = 10000, seed: int = 20261021) -> Dict[str, Any]:
    """
    Menjalankan simulasi Monte Carlo N >= 10.000 hari untuk membandingkan 4 strategi:
      (a) Selalu Rute Cepat (Pintas)
      (b) Selalu Rute Aman (Raya)
      (c) Kebijakan MDP tanpa membaca papan (prior tetap 0.10)
      (d) Kebijakan MDP adaptif dengan membaca papan (posterior Bayes)

    Menghitung rata-rata utilitas per perjalanan, interval kepercayaan 95%,
    dan perbandingan terhadap EU Teori.
    """
    rng = random.Random(seed)

    payoff_fast: List[float] = []
    payoff_safe: List[float] = []
    payoff_mdp_blind: List[float] = []
    payoff_mdp_adaptive: List[float] = []

    # Parameter slide
    u_success = config.DECISION_REWARD_CAMPUS        # +10
    u_flood = config.DECISION_REWARD_FLOOD           # -20
    u_safe = config.DECISION_UTILITY_MAIN_ROAD       # +6

    # Simulasi N hari
    for _ in range(n_days):
        # 1. State alamiah banjir aktual tersembunyi
        is_flooded = (rng.random() < config.FLOOD_PRIOR_DEFAULT)

        # (a) Selalu Cepat: jika banjir -> -20, jika aman -> +10
        val_a = u_flood if is_flooded else u_success
        payoff_fast.append(val_a)

        # (b) Selalu Aman: selalu +6
        val_b = u_safe
        payoff_safe.append(val_b)

        # (c) MDP Tanpa Membaca Papan:
        # Prior = 0.10 < f* (0.1333) -> aksi selalu "Pintas"
        val_c = u_flood if is_flooded else u_success
        payoff_mdp_blind.append(val_c)

        # (d) MDP Adaptif (Membaca Papan Cuaca):
        # Bangkitkan bukti observasi dari papan cuaca
        if is_flooded:
            evidence = "air mulai naik" if rng.random() < config.P_NEWS_GIVEN_FLOOD else "langit cerah"
        else:
            evidence = "air mulai naik" if rng.random() < config.P_NEWS_GIVEN_NO_FLOOD else "langit cerah"

        # Update posterior Bayes
        if evidence == "air mulai naik":
            post, _ = bayes_update(config.FLOOD_PRIOR_DEFAULT, config.P_NEWS_GIVEN_FLOOD, config.P_NEWS_GIVEN_NO_FLOOD)
        else:
            post, _ = bayes_update(config.FLOOD_PRIOR_DEFAULT, config.P_SUNNY_GIVEN_FLOOD, config.P_SUNNY_GIVEN_NO_FLOOD)

        # Keputusan MDP:
        # Jika post > f* (~0.1333) -> ambil "Raya" (+6)
        # Jika post <= f* -> ambil "Pintas" (+10 atau -20)
        if post > config.DECISION_ANALYTIC_F_STAR:
            action_d = "Raya"
            val_d = u_safe
        else:
            action_d = "Pintas"
            val_d = u_flood if is_flooded else u_success

        payoff_mdp_adaptive.append(val_d)

    def calc_stats(arr: List[float]) -> Dict[str, float]:
        n = len(arr)
        mean = sum(arr) / n
        var = sum((x - mean) ** 2 for x in arr) / (n - 1)
        std_err = math.sqrt(var / n)
        # z = 1.96 untuk 95% CI
        ci95 = 1.96 * std_err
        return {
            "mean": round(mean, 4),
            "ci95_low": round(mean - ci95, 4),
            "ci95_high": round(mean + ci95, 4),
            "std_err": round(std_err, 4)
        }

    # Teori EU:
    # EU(Cepat) = 0.9(10) + 0.1(-20) = 7.0
    # EU(Aman) = 6.0
    # EU(Adaptif):
    # P(Berita) = 0.18 -> P(Banjir|Berita)=0.50 -> Raya -> +6
    # P(Cerah) = 0.82 -> P(Banjir|Cerah)=0.0122 -> Pintas -> 0.0122(-20) + 0.9878(10) = 9.6341
    # EU_Adaptif_Teori = 0.18 * 6.0 + 0.82 * 9.6341 = 1.08 + 7.90 = 8.98
    eu_theory = {
        "fast": 7.0,
        "safe": 6.0,
        "mdp_blind": 7.0,
        "mdp_adaptive": round(0.18 * 6.0 + 0.82 * (0.012195 * (-20) + 0.987805 * 10), 4)
    }

    return {
        "n_days": n_days,
        "seed": seed,
        "results": {
            "fast": calc_stats(payoff_fast),
            "safe": calc_stats(payoff_safe),
            "mdp_blind": calc_stats(payoff_mdp_blind),
            "mdp_adaptive": calc_stats(payoff_mdp_adaptive),
        },
        "eu_theory": eu_theory
    }


def run_real_game_monte_carlo(n_days: int = 10000, seed: int = 20261021) -> Dict[str, Any]:
    """
    Simulasi Monte Carlo Waktu Nyata di Game (Satuan: Detik):
    Menjalankan simulasi headless dengan parameter rute game nyata:
    - Rute Pintas: 1.14s (168px)
    - Rute Aman: 1.50s (220px)
    - Penalti fisik terkalibrasi: 2.70s (animasi renang 1.5s + recovery mundur)
    Membandingkan 4 strategi:
      (a) Selalu Cepat (Pintas)
      (b) Selalu Aman (Raya)
      (c) Kebijakan tanpa membaca papan (prior 0.10)
      (d) Kebijakan adaptif Bayes dengan membaca papan
    """
    rng = random.Random(seed)

    t_pintas = 1.14
    t_aman = 1.50
    t_pen = 2.70
    f_star = getattr(config, "DECISION_ANALYTIC_F_STAR", 2.0 / 15.0)

    game_fast: List[float] = []
    game_safe: List[float] = []
    game_blind: List[float] = []
    game_adaptive: List[float] = []

    for _ in range(n_days):
        is_flooded = (rng.random() < config.FLOOD_PRIOR_DEFAULT)

        # 1. Selalu Cepat
        t_a = (t_pintas + t_pen) if is_flooded else t_pintas
        game_fast.append(t_a)

        # 2. Selalu Aman
        t_b = t_aman
        game_safe.append(t_b)

        # 3. Blind MDP (prior 0.10 < f*) -> selalu Pintas
        t_c = t_a
        game_blind.append(t_c)

        # 4. Adaptif Bayes
        if is_flooded:
            ev = "news" if rng.random() < config.P_NEWS_GIVEN_FLOOD else "sunny"
        else:
            ev = "news" if rng.random() < config.P_NEWS_GIVEN_NO_FLOOD else "sunny"

        if ev == "news":
            post, _ = bayes_update(config.FLOOD_PRIOR_DEFAULT, config.P_NEWS_GIVEN_FLOOD, config.P_NEWS_GIVEN_NO_FLOOD)
        else:
            post, _ = bayes_update(config.FLOOD_PRIOR_DEFAULT, config.P_SUNNY_GIVEN_FLOOD, config.P_SUNNY_GIVEN_NO_FLOOD)

        if post > f_star:
            t_d = t_aman
        else:
            t_d = (t_pintas + t_pen) if is_flooded else t_pintas
        game_adaptive.append(t_d)

    def stats(arr: List[float]) -> Dict[str, float]:
        n = len(arr)
        mean = sum(arr) / n
        var = sum((x - mean) ** 2 for x in arr) / (n - 1)
        sd = math.sqrt(var)
        se = sd / math.sqrt(n)
        ci95 = 1.96 * se
        return {
            "mean": round(mean, 4),
            "std_dev": round(sd, 4),
            "std_err": round(se, 4),
            "ci95_low": round(mean - ci95, 4),
            "ci95_high": round(mean + ci95, 4)
        }

    return {
        "metadata": {
            "n_days": n_days,
            "seed": seed,
            "description": "Simulasi Monte Carlo Game Nyata (Detik)",
            "vpi_note": "VPI adalah metrik ekstensi analisis keputusan formal di luar silabus slide kuliah."
        },
        "real_game_seconds": {
            "fast_always": stats(game_fast),
            "safe_always": stats(game_safe),
            "blind_mdp": stats(game_blind),
            "adaptive_bayes": stats(game_adaptive),
            "theory_expected_seconds": {
                "fast": round(t_pintas + config.FLOOD_PRIOR_DEFAULT * t_pen, 4),
                "safe": round(t_aman, 4),
                "blind": round(t_pintas + config.FLOOD_PRIOR_DEFAULT * t_pen, 4),
                "adaptive": round(0.18 * t_aman + 0.82 * (t_pintas + 0.012195 * t_pen), 4)
            },
            "time_saved_by_notice_sec": round(stats(game_fast)["mean"] - stats(game_adaptive)["mean"], 4)
        }
    }
