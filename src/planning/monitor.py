"""
monitor.py - PlanMonitor & Deteksi Pemicu Replanning Sub-fase 2B

Memantau eksekusi rencana secara aktif terhadap lingkungan game dinamis:
  1. TRIGGER_BLOCKED_PATH: Jembatan/jalur terhalang rintangan dinamis (collision override).
  2. TRIGGER_CROP_UNAVAILABLE: Tanaman ladang belum matang, rusak, atau diinjak.
  3. TRIGGER_HP_LOW: Hero mengalami kekalahan atau HP < batas aman (< 40%).
  4. TRIGGER_MANUAL_INTERFERENCE: Pemain menggerakkan hero atau menggunakan item secara manual.

Batas Kegagalan:
  - Maksimal 3x replan berturut-turut. Jika gagal 3x berturut-turut, sistem menyerah
    (surrender) dan mengembalikan kontrol 100% ke mode manual pemain.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Tuple, Any, Dict, Set
import math

import config
from world_state import WorldState
from planning.strips import GroundAction, Predicate, PlanningProblem
from planning.problem_generator import build_problem_from_state, find_nearest_location
from planning.planner import search_weighted_astar_hff, SearchResult
from planning.distance_matrix import DistanceMatrix


class ReplanTrigger:
    NONE = "NONE"
    BLOCKED_PATH = "BLOCKED_PATH"
    CROP_UNAVAILABLE = "CROP_UNAVAILABLE"
    HP_LOW = "HP_LOW"
    MANUAL_INTERFERENCE = "MANUAL_INTERFERENCE"
    PRECONDITION_FAILED = "PRECONDITION_FAILED"


@dataclass
class MonitorStatus:
    is_valid: bool
    trigger: str = ReplanTrigger.NONE
    message: str = "Semua kondisi valid."
    target_action: Optional[GroundAction] = None


class PlanMonitor:
    """
    Monitor eksekusi rencana yang memvalidasi kondisi dunia sebelum tiap aksi
    dan mengatur replanning otonom saat terjadi anomali atau rintangan.
    """

    def __init__(self, world_state: WorldState, goal_type: str = "boss_defeated",
                 max_consecutive_replans: int = 3, distance_matrix: Optional[DistanceMatrix] = None):
        self.world_state = world_state
        self.goal_type = goal_type
        self.max_consecutive_replans = max_consecutive_replans
        self.consecutive_replans = 0
        self.surrendered = False
        self.distance_matrix = distance_matrix or DistanceMatrix()

        self.current_plan: List[GroundAction] = []
        self.current_step_idx: int = 0
        self.last_hero_pos: Optional[Tuple[float, float]] = None

    def set_plan(self, plan: List[GroundAction]):
        """Mengatur rencana aktif dan mereset indeks langkah."""
        self.current_plan = list(plan)
        self.current_step_idx = 0
        self.consecutive_replans = 0
        self.surrendered = False

    @property
    def current_action(self) -> Optional[GroundAction]:
        if 0 <= self.current_step_idx < len(self.current_plan):
            return self.current_plan[self.current_step_idx]
        return None

    def check_preconditions(self, hero: Any = None, game_map: Any = None) -> MonitorStatus:
        """
        Memeriksa apakah aksi saat ini masih legal dan aman untuk dieksekusi.
        """
        if self.surrendered:
            return MonitorStatus(False, ReplanTrigger.PRECONDITION_FAILED,
                                 "Sistem telah menyerah ke mode manual setelah 3x replan gagal.")

        act = self.current_action
        if act is None:
            return MonitorStatus(True, ReplanTrigger.NONE, "Rencana telah selesai.")

        # 1. Pemicu HP Rendah / Kalah Pertarungan
        if hero is not None:
            hp = getattr(hero, "hp", 100)
            max_hp = getattr(hero, "max_hp", 100)
            if hp <= 0:
                return MonitorStatus(False, ReplanTrigger.HP_LOW,
                                     f"Hero kalah dalam pertempuran (HP {hp}/{max_hp})! Perlu rest dan pemulihan.",
                                     act)
            if hp < (max_hp * 0.40) and act.name in ("fight_boss", "fight_boss_hardened"):
                return MonitorStatus(False, ReplanTrigger.HP_LOW,
                                     f"HP hero terlalu rendah ({hp}/{max_hp}) untuk menghadapi boss! Perlu rest.",
                                     act)

        # 2. Pemicu Rintangan Jalur / Jembatan Terblokir (Blocked Bridge/Gate)
        if act.name in ("goto", "goto_through_gate"):
            from_loc = act.params[0]
            to_loc = act.params[1]
            if game_map is not None:
                self.distance_matrix.game_map = game_map
            dur, steps, path = self.distance_matrix.get_distance(
                from_loc, to_loc, gate_open=self.world_state.gate.is_open
            )
            if math.isinf(dur) or steps >= 999999:
                return MonitorStatus(False, ReplanTrigger.BLOCKED_PATH,
                                     f"Jalur dari '{from_loc}' ke '{to_loc}' terblokir oleh rintangan!",
                                     act)

        # 3. Pemicu Anomali Tanaman Ladang
        if act.name == "harvest_radish":
            plot_idx = 0
            if act.params and "1" in act.params[0]:
                plot_idx = 1
            if hasattr(self.world_state, "farm"):
                plots = self.world_state.farm.plots
                if plot_idx >= len(plots) or not plots[plot_idx].is_mature:
                    return MonitorStatus(False, ReplanTrigger.CROP_UNAVAILABLE,
                                         f"Petak ladang {plot_idx} belum matang atau rusak untuk dipanen!",
                                         act)

        # 4. Pemicu Koin / Barang Tidak Cukup
        if act.name == "buy_seed_radish" and self.world_state.coins < self.world_state.shop.get_buy_price("seeds_radish"):
            return MonitorStatus(False, ReplanTrigger.PRECONDITION_FAILED,
                                 "Koin tidak mencukupi untuk membeli benih lobak!", act)

        if act.name == "buy_bottle" and self.world_state.coins < self.world_state.shop.get_buy_price("bottle_empty"):
            return MonitorStatus(False, ReplanTrigger.PRECONDITION_FAILED,
                                 "Koin tidak mencukupi untuk membeli botol kosong!", act)

        if act.name == "craft_key" and (not self.world_state.inventory.has_item("wood", 1) or
                                        not self.world_state.inventory.has_item("rock", 1)):
            return MonitorStatus(False, ReplanTrigger.PRECONDITION_FAILED,
                                 "Material kayu/batu untuk kunci tidak tersedia di tas!", act)

        if act.name == "open_gate" and not self.world_state.inventory.has_item("gate_key", 1):
            return MonitorStatus(False, ReplanTrigger.PRECONDITION_FAILED,
                                 "Hero tidak membawa Kunci Gerbang!", act)

        return MonitorStatus(True, ReplanTrigger.NONE, "Kondisi langkah valid.", act)

    def trigger_replan(self, hero: Any = None, game_map: Any = None) -> Tuple[bool, Optional[List[GroundAction]], str]:
        """
        Membangun problem baru dari state dunia aktual dan mencari rencana pengganti.
        """
        is_initial_plan = (self.current_plan is None)
        if not is_initial_plan:
            if self.consecutive_replans >= self.max_consecutive_replans:
                self.surrendered = True
                msg = (f"[PlanMonitor] Batas {self.max_consecutive_replans}x replan berturut-turut tercapai. "
                       f"Menyerah (surrender) ke kontrol manual pemain.")
                return False, None, msg
            self.consecutive_replans += 1

        self.distance_matrix.invalidate()

        try:
            problem = build_problem_from_state(
                self.world_state, hero=hero, game_map=game_map,
                goal_type=self.goal_type, distance_matrix=self.distance_matrix,
                max_coins=60
            )
            res = search_weighted_astar_hff(problem, weight=2.0, use_helpful_actions=True, timeout_sec=4.0)

            if res.success and len(res.plan) > 0:
                self.current_plan = list(res.plan)
                self.current_step_idx = 0
                if is_initial_plan:
                    self.consecutive_replans = 0
                    msg = f"[PlanMonitor] Perencanaan awal BERHASIL: {len(res.plan)} langkah dihasilkan."
                else:
                    msg = (f"[PlanMonitor] Replanning BERHASIL (percobaan {self.consecutive_replans}/"
                           f"{self.max_consecutive_replans}): {len(res.plan)} langkah baru dihasilkan.")
                return True, self.current_plan, msg
            else:
                if self.consecutive_replans >= self.max_consecutive_replans:
                    self.surrendered = True
                    msg = (f"[PlanMonitor] Replanning GAGAL (percobaan {self.consecutive_replans}/"
                           f"{self.max_consecutive_replans}): {res.failure_reason}. "
                           f"Menyerah (surrender) ke kontrol manual pemain.")
                else:
                    msg = (f"[PlanMonitor] Replanning GAGAL (percobaan {self.consecutive_replans}/"
                           f"{self.max_consecutive_replans}): {res.failure_reason}")
                return False, None, msg

        except Exception as e:
            msg = f"[PlanMonitor] Error saat replanning: {e}"
            if self.consecutive_replans >= self.max_consecutive_replans:
                self.surrendered = True
            return False, None, msg

    def advance_step(self):
        """Maju ke langkah berikutnya setelah aksi selesai sukses."""
        self.current_step_idx += 1
        # Jika berhasil menyelesaikan satu langkah, reset counter kegagalan replan
        self.consecutive_replans = 0
