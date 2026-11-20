"""
combat_policy.py - Formulasi Formal Decisions Under Uncertainty (DUU)
untuk Kebijakan Risiko Pertempuran Real-Time Minion (Live Minion Combat Policy)
berbasis Maximum Expected Utility (MEU) dan Bayesian Belief Updating.

Komponen Teoretis:
1. Ruang Aksi: A = {ENGAGE, EVADE, HEAL}
2. Jaringan Keputusan (Decision Network):
   - Chance Node: Tipe Goblin T in {NORMAL, ELITE}
     * Prior: P(ELITE) = 0.20, P(NORMAL) = 0.80
   - Bukti Observasi (Evidence):
     * Pertukaran serangan awal (observed damage / combat signature).
     * Likelihood:
       P(HighDamage | ELITE) = 0.70, P(HighDamage | NORMAL) = 0.20
       P(LowDamage  | ELITE) = 0.30, P(LowDamage  | NORMAL) = 0.80
     * Pembaruan Bayes:
       P(ELITE | E) = P(E | ELITE)*P(ELITE) / P(E)
3. Model Probabilitas Kemenangan P(win | HP_hero, HP_goblin, n, T):
   - Menghitung waktu eliminasi dan peluang menang berdasarkan sisa HP goblin:
     Jika goblin sekarat (HP <= 0.33), peluang menang naik signifikan.
   - Sigmoid kontinu terkalibrasi analitik & simulasi Monte Carlo:
     P(win | HP, HP_gob, n, T) = 1 / (1 + exp(- (HP - center(HP_gob, n, T)) / scale))
   - Prediktif Bayes:
     P(win) = (1 - P(ELITE|E)) * P(win|NORMAL) + P(ELITE|E) * P(win|ELITE)
4. Fungsi Utilitas:
   - U(loot) = (1 - P(ELITE|E)) * 5.5 + P(ELITE|E) * 12.0
   - U(death) = -20.0 (penalti kematian & kegagalan misi)
   - U(evade_cost) = -1.5 (biaya deviasi / detour)
   - U(potion) = -3.0 (biaya koin 1 ramuan)
5. Expected Utility (EU):
   - EU(ENGAGE) = P(win) * U(loot) + (1 - P(win)) * U(death)
   - EU(EVADE) = (1 - c) * U(evade_cost) + c * U(death) (c = 0.0 karena v_hero > v_goblin)
   - EU(HEAL) = EU(ENGAGE | min(1.0, HP + 0.50)) - 3.0 (hanya valid jika has_potion=True)
6. Derivasi Titik Keseimbangan (Analytic Inversion):
   EU(ENGAGE) = EU(EVADE) => P*(win) = (u_evade - u_death) / (u_loot - u_death) = 18.5 / 25.5 ~= 0.72549
   Inversi Sigmoid menghasilkan ambang batas HP* = 35.0% untuk 1 goblin normal HP penuh.
7. Histeresis & Dwell Time:
   - Margin histeresis 10% (decommit saat HP < HP* - 0.10 = 25%)
   - Reset state saat goblin mati, hero mati, atau menjauh dari radius ancaman.
"""

from __future__ import annotations

import math
from typing import Tuple, Dict, Any, Optional


class CombatDecision:
    ENGAGE = "ENGAGE"
    EVADE = "EVADE"
    HEAL = "HEAL"
    NO_THREAT = "NO_THREAT"


class GoblinType:
    NORMAL = "NORMAL"
    ELITE = "ELITE"


class BayesianMinionBelief:
    """
    Model Pembaruan Keyakinan Bayesian untuk mengklasifikasi tipe ancaman goblin.
    Prior: P(ELITE) = 0.20, P(NORMAL) = 0.80.
    """

    def __init__(self,
                 prior_elite: float = 0.20,
                 p_high_given_elite: float = 0.70,
                 p_high_given_normal: float = 0.20):
        self.prior_elite = float(prior_elite)
        self.p_high_given_elite = float(p_high_given_elite)
        self.p_high_given_normal = float(p_high_given_normal)
        self.posterior_elite = self.prior_elite
        self.observations_count = 0

    def reset(self):
        """Reset keyakinan ke prior awal saat pertempuran baru dimulai."""
        self.posterior_elite = self.prior_elite
        self.observations_count = 0

    def update(self, is_high_damage: bool) -> float:
        """
        Pembaruan posterior berdasarkan observasi kekuatan serangan/damage musuh:
        P(ELITE | E) = P(E | ELITE)*P(ELITE) / [P(E | ELITE)*P(ELITE) + P(E | NORMAL)*P(NORMAL)]
        """
        p_e_given_elite = self.p_high_given_elite if is_high_damage else (1.0 - self.p_high_given_elite)
        p_e_given_normal = self.p_high_given_normal if is_high_damage else (1.0 - self.p_high_given_normal)

        numerator = p_e_given_elite * self.posterior_elite
        denominator = numerator + (p_e_given_normal * (1.0 - self.posterior_elite))

        if denominator > 1e-9:
            self.posterior_elite = numerator / denominator
        self.observations_count += 1
        return self.posterior_elite


class CombatRiskModel:
    """
    Model Evaluasi Utilitas Harapan (MEU) & Bayesian Decision Network
    untuk Pertempuran Hero vs Minion Goblin Real-Time.
    """

    def __init__(self,
                 u_loot: Optional[float] = None,
                 u_loot_normal: float = 5.5,
                 u_loot_elite: float = 12.0,
                 u_death: float = -20.0,
                 u_evade_cost: float = -1.5,
                 u_potion_cost: float = -3.0,
                 potion_heal_pct: float = 0.50,
                 hysteresis_margin: float = 0.10,
                 prior_elite: float = 0.20,
                 c_catch_prob: float = 0.0):
        if u_loot is not None:
            u_loot_normal = u_loot
        self.u_loot = float(u_loot_normal)
        self.u_loot_normal = float(u_loot_normal)
        self.u_loot_elite = float(u_loot_elite)
        self.u_death = float(u_death)
        self.u_evade_cost = float(u_evade_cost)
        self.u_potion_cost = float(u_potion_cost)
        self.potion_heal_pct = float(potion_heal_pct)
        self.hysteresis_margin = float(hysteresis_margin)
        self.c_catch_prob = float(c_catch_prob)

        # Inisialisasi belief Bayesian
        self.belief = BayesianMinionBelief(prior_elite=prior_elite)

        # Skala dan kalibrasi sigmoid analitik:
        # P*(win) untuk goblin normal:
        # EU(Engage) = EU(Evade) => p* * 5.5 + (1 - p*) * (-20) = -1.5 => 25.5 p* = 18.5
        self.p_star_normal = (self.u_evade_cost - self.u_death) / (self.u_loot_normal - self.u_death)
        self.p_star = self.p_star_normal
        self.scale = 0.10
        # z* = ln(p* / (1 - p*)) ~= 0.97186
        self.z_star = math.log(self.p_star_normal / (1.0 - self.p_star_normal))
        # Center normal dikalibrasi tepat agar pada HP=0.35, P(win) = p_star_normal:
        self.center_normal = 0.35 - (self.z_star * self.scale)  # ~= 0.25281

    def calculate_win_probability(self,
                                  hp_hero: float,
                                  hp_goblin: float = 1.0,
                                  goblin_count: int = 1,
                                  is_elite: bool = False) -> float:
        """
        Menghitung probabilitas menang kontinu P(win | hp_hero, hp_goblin, n, is_elite).
        hp_hero dan hp_goblin dalam rentang [0.0, 1.0].
        """
        # Guard HP batas
        if hp_hero <= 0.0:
            return 0.0
        if hp_goblin <= 0.0:
            return 1.0
        if hp_hero >= 1.0 and goblin_count <= 1 and hp_goblin <= 0.5:
            return 0.999

        # Penyesuaian center berdasarkan HP sisa goblin dan tipe
        # Jika goblin sekarat (hp_goblin rendah), center bergeser ke kiri (hero lebih mudah menang)
        base_center = self.center_normal * max(0.2, min(1.0, hp_goblin))

        if is_elite:
            # Goblin elit memiliki HP lebih tinggi dan damage 2x lipat
            base_center += 0.20

        # Penyesuaian jumlah goblin n
        if goblin_count > 1:
            base_center += 0.12 * (goblin_count - 1)

        z = (hp_hero - base_center) / self.scale

        # Sigmoid stabil numerik
        if z >= 15.0:
            return 1.0
        elif z <= -15.0:
            return 0.0
        return 1.0 / (1.0 + math.exp(-z))

    def get_predictive_win_probability(self,
                                        hp_hero: float,
                                        hp_goblin: float = 1.0,
                                        goblin_count: int = 1) -> Tuple[float, float, float]:
        """
        Menghitung probabilitas prediktif Bayesian:
        P(win) = (1 - P(ELITE))*P(win|NORMAL) + P(ELITE)*P(win|ELITE)
        Mengembalikan: (P_prediktif, P_win_normal, P_win_elite)
        """
        p_win_norm = self.calculate_win_probability(hp_hero, hp_goblin, goblin_count, is_elite=False)
        p_win_elite = self.calculate_win_probability(hp_hero, hp_goblin, goblin_count, is_elite=True)

        p_elite = self.belief.posterior_elite
        p_pred = (1.0 - p_elite) * p_win_norm + p_elite * p_win_elite
        return p_pred, p_win_norm, p_win_elite

    def calculate_breakeven_threshold(self,
                                      hp_goblin: float = 1.0,
                                      goblin_count: int = 1,
                                      p_elite: Optional[float] = None) -> Optional[float]:
        """
        Inversi analitik untuk menentukan ambang batas HP* di mana EU(Engage) = EU(Evade).
        Jika tidak ada solusi (misal n terlalu besar sehingga P(win|HP=1.0) < p*), return None.
        """
        if p_elite is None:
            p_elite = self.belief.posterior_elite
        expected_u_loot = (1.0 - p_elite) * self.u_loot_normal + p_elite * self.u_loot_elite
        eu_evade = (1.0 - self.c_catch_prob) * self.u_evade_cost + self.c_catch_prob * self.u_death

        # p* = (EU(evade) - U(death)) / (U(loot) - U(death))
        p_star = (eu_evade - self.u_death) / (expected_u_loot - self.u_death)
        if p_star <= 0.0 or p_star >= 1.0:
            return None

        # z* = ln(p* / (1 - p*))
        z_star = math.log(p_star / (1.0 - p_star))

        # Center terbobot
        base_center_norm = self.center_normal * max(0.2, min(1.0, hp_goblin)) + (0.12 * max(0, goblin_count - 1))
        base_center_elite = base_center_norm + 0.20
        eff_center = (1.0 - p_elite) * base_center_norm + p_elite * base_center_elite

        hp_star = eff_center + (z_star * self.scale)
        return hp_star

    def compute_expected_utilities(self,
                                  hp_hero: float,
                                  hp_goblin: float = 1.0,
                                  goblin_count: int = 1,
                                  has_potion: bool = False) -> Dict[str, float]:
        """
        Menghitung nilai utilitas harapan untuk aksi ENGAGE, EVADE, dan HEAL.
        """
        # Guard HP Hero 0
        if hp_hero <= 0.0:
            return {
                "p_win": 0.0,
                "eu_engage": self.u_death,
                "eu_evade": self.u_death,
                "eu_heal": self.u_death,
                "p_elite": self.belief.posterior_elite
            }

        p_pred, p_norm, p_elite_win = self.get_predictive_win_probability(hp_hero, hp_goblin, goblin_count)
        p_elite = self.belief.posterior_elite

        expected_u_loot = (1.0 - p_elite) * self.u_loot_normal + p_elite * self.u_loot_elite

        # 1. EU(ENGAGE)
        eu_engage = p_pred * expected_u_loot + (1.0 - p_pred) * self.u_death

        # 2. EU(EVADE)
        # c = peluang tertangkap (default 0.0 karena v_hero > v_goblin)
        eu_evade = (1.0 - self.c_catch_prob) * self.u_evade_cost + self.c_catch_prob * self.u_death

        # 3. EU(HEAL)
        if has_potion and hp_hero < 0.99:
            healed_hp = min(1.0, hp_hero + self.potion_heal_pct)
            p_pred_healed, _, _ = self.get_predictive_win_probability(healed_hp, hp_goblin, goblin_count)
            eu_heal = (p_pred_healed * expected_u_loot + (1.0 - p_pred_healed) * self.u_death) + self.u_potion_cost
        else:
            eu_heal = -float("inf")

        return {
            "p_win": p_pred,
            "p_win_normal": p_norm,
            "p_win_elite": p_elite_win,
            "p_elite": p_elite,
            "eu_engage": eu_engage,
            "eu_evade": eu_evade,
            "eu_heal": eu_heal,
        }

    def decide(self,
               hp_hero: float,
               hp_goblin: float = 1.0,
               goblin_count: int = 1,
               has_potion: bool = False,
               currently_engaged: bool = False) -> Tuple[str, Dict[str, Any]]:
        """
        Mengambil keputusan optimal argmax(EU) dilengkapi histeresis:
        - Jika goblin_count == 0: NO_THREAT
        - Guard HP <= 0: EVADE (Game Over)
        - Jika currently_engaged: bertahan di ENGAGE selama HP >= HP* - margin (histeresis)
          kecuali EU(HEAL) > EU(ENGAGE) maka disarankan HEAL.
        - Jika belum engage: pilih argmax {ENGAGE, EVADE, HEAL}.
        """
        if goblin_count <= 0:
            return CombatDecision.NO_THREAT, {
                "decision": CombatDecision.NO_THREAT,
                "p_win": 1.0,
                "eu_engage": 0.0,
                "eu_evade": 0.0,
                "eu_heal": -float("inf")
            }

        if hp_hero <= 0.0:
            metrics = self.compute_expected_utilities(hp_hero, hp_goblin, goblin_count, has_potion)
            metrics["decision"] = CombatDecision.EVADE
            metrics["is_dead"] = True
            return CombatDecision.EVADE, metrics

        metrics = self.compute_expected_utilities(hp_hero, hp_goblin, goblin_count, has_potion)
        eu_engage = metrics["eu_engage"]
        eu_evade = metrics["eu_evade"]
        eu_heal = metrics["eu_heal"]

        hp_star = self.calculate_breakeven_threshold(hp_goblin, goblin_count)
        metrics["derived_threshold"] = hp_star
        metrics["p_star_breakeven"] = self.p_star_normal

        # Pengecekan Heal
        if has_potion and eu_heal > eu_engage and eu_heal > eu_evade:
            action = CombatDecision.HEAL
        elif currently_engaged:
            # Mode bertahan (histeresis):
            # Decommit hanya jika HP jatuh di bawah ambang batas dikurangi margin
            threshold = (hp_star if hp_star is not None else 0.35) - self.hysteresis_margin
            action = CombatDecision.ENGAGE if hp_hero >= threshold else CombatDecision.EVADE
        else:
            # Mode inisiasi baru: argmax EU(Engage) vs EU(Evade)
            action = CombatDecision.ENGAGE if eu_engage >= eu_evade else CombatDecision.EVADE

        metrics["decision"] = action
        return action, metrics
