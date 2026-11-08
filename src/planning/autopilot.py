"""
autopilot.py - Autopilot Controller & Integrasi Mode OFF / ADVISOR / AUTO

Fitur Sub-fase 2B:
  1. Tiga Mode Operasi (F9):
     - OFF: Kontrol manual murni, sistem perencanaan non-aktif.
     - ADVISOR: Menampilkan rekomendasi langkah berikutnya di HUD tanpa menggerakkan Hero.
     - AUTO: Hero bergerak otomatis mengeksekusi rencana dari game baru sampai boss.
  2. Jeda Otomatis saat Kontrol Player Terdeteksi:
     - Jika pemain menekan tombol gerak (WASD / Panah) saat mode AUTO aktif,
       autopilot langsung menjeda (PAUSED) agar pemain memegang kendali penuh.
  3. Integrasi PlanMonitor:
     - Memeriksa kondisi dunia sebelum tiap aksi.
     - Memicu replanning otomatis jika jembatan terhalang, HP kritis, atau panen gagal.
     - Menyerah ke mode manual jika replan gagal 3x berturut-turut.
"""

from typing import Optional, List, Tuple, Any, Dict
import math
import pygame

import config
from world_state import WorldState
from planning.strips import GroundAction
from planning.monitor import PlanMonitor, ReplanTrigger, MonitorStatus
from planning.executor import PlanExecutor
from planning.distance_matrix import DistanceMatrix


class PlannerMode:
    OFF = "OFF"
    ADVISOR = "ADVISOR"
    AUTO = "AUTO"
    ALL = [OFF, ADVISOR, AUTO]


class AutopilotState:
    IDLE = "IDLE"
    PLANNING = "PLANNING"
    NAVIGATING = "NAVIGATING"
    INTERACTING = "INTERACTING"
    PAUSED = "PAUSED"
    SURRENDERED = "SURRENDERED"


class AutopilotController:
    """
    Pengendali utama Autopilot Hero di dunia game.
    """

    def __init__(self, world_state: WorldState, hero: Any = None, game_map: Any = None,
                 distance_matrix: Optional[DistanceMatrix] = None):
        self.world_state = world_state
        self.hero = hero
        self.game_map = game_map
        self.mode = PlannerMode.OFF
        self.state = AutopilotState.IDLE

        self.distance_matrix = distance_matrix or DistanceMatrix(game_map=game_map)
        self.monitor = PlanMonitor(world_state, distance_matrix=self.distance_matrix)
        self.executor = PlanExecutor(world_state, hero=hero, game_map=game_map)

        self.current_path: List[Tuple[int, int]] = []
        self.target_location_name: Optional[str] = None
        self.status_message: str = "Mode Planner: OFF"
        self.is_paused_by_player: bool = False

    def toggle_mode(self) -> str:
        """Berpindah antara mode OFF -> ADVISOR -> AUTO -> OFF."""
        idx = PlannerMode.ALL.index(self.mode) if self.mode in PlannerMode.ALL else 0
        self.mode = PlannerMode.ALL[(idx + 1) % len(PlannerMode.ALL)]
        self.is_paused_by_player = False

        if self.mode == PlannerMode.OFF:
            self.state = AutopilotState.IDLE
            self.status_message = "Mode Planner dimatikan (OFF)."
        elif self.mode == PlannerMode.ADVISOR:
            self.status_message = "Mode ADVISOR aktif: Menampilkan saran langkah."
            if not self.monitor.current_plan:
                self._request_new_plan()
        elif self.mode == PlannerMode.AUTO:
            self.status_message = "Mode AUTO aktif: Hero bergerak mandiri."
            if not self.monitor.current_plan:
                self._request_new_plan()
            else:
                self.state = AutopilotState.NAVIGATING

        return self.mode

    def _request_new_plan(self) -> bool:
        """Membuat rencana baru dari kondisi dunia saat ini."""
        self.state = AutopilotState.PLANNING
        ok, plan, msg = self.monitor.trigger_replan(hero=self.hero, game_map=self.game_map)
        if ok and plan:
            self.status_message = msg
            self.state = AutopilotState.NAVIGATING if self.mode == PlannerMode.AUTO else AutopilotState.IDLE
            return True
        else:
            self.status_message = msg
            if self.monitor.surrendered:
                self.state = AutopilotState.SURRENDERED
            else:
                self.state = AutopilotState.IDLE
            return False

    def handle_player_input(self, keys_pressed: Dict[int, bool]) -> bool:
        """
        Mendeteksi apakah pemain menekan kontrol gerak manual.
        Jika terdeteksi saat mode AUTO, langsung jeda eksekusi autopilot.
        """
        movement_keys = [pygame.K_w, pygame.K_a, pygame.K_s, pygame.K_d,
                         pygame.K_UP, pygame.K_DOWN, pygame.K_LEFT, pygame.K_RIGHT]

        is_moving = any(keys_pressed.get(k, False) for k in movement_keys)
        if is_moving and self.mode == PlannerMode.AUTO:
            if not self.is_paused_by_player:
                self.is_paused_by_player = True
                self.state = AutopilotState.PAUSED
                self.status_message = "[AUTOPILOT: DIJEDA] Kontrol manual terdeteksi. Tekan [F10] untuk lanjut."
            return True
        elif not is_moving and self.is_paused_by_player and self.mode == PlannerMode.AUTO:
            # Tetap dijeda sampai pemain menekan tombol resume secara eksplisit (F10)
            return False

        return False

    def toggle_pause(self) -> bool:
        """
        Beralih jeda/lanjut secara eksplisit (tombol F10).
        Mengembalikan True jika sekarang dijeda, False jika sekarang aktif berjalan.
        """
        if self.mode != PlannerMode.AUTO:
            return False
        if self.state == AutopilotState.PAUSED or self.is_paused_by_player:
            self.is_paused_by_player = False
            self.status_message = "[AUTOPILOT] Melanjutkan kembali..."
            status = self.monitor.check_preconditions(hero=self.hero, game_map=self.game_map)
            if not status.is_valid:
                self._request_new_plan()
            else:
                self.state = AutopilotState.NAVIGATING
            return False
        else:
            self.is_paused_by_player = True
            self.state = AutopilotState.PAUSED
            self.status_message = "[AUTOPILOT: DIJEDA] Dijeda manual oleh pemain. Tekan [F10] untuk lanjut."
            return True

    def get_advisor_text(self) -> str:
        """Mengembalikan teks saran rekomendasi untuk ditampilkan di HUD."""
        if self.mode == PlannerMode.OFF:
            return ""
        if self.state == AutopilotState.SURRENDERED:
            return "[ADVISOR] Rencana gagal 3x berturut-turut. Kontrol manual diperlukan!"
        if self.state == AutopilotState.PAUSED:
            return "[ADVISOR] Autopilot dijeda oleh input pemain."

        act = self.monitor.current_action
        if act is None:
            return "[ADVISOR] Seluruh ekspedisi selesai! Kemenangan tercapai."

        step_num = self.monitor.current_step_idx + 1
        total_steps = len(self.monitor.current_plan)

        descriptions = {
            "goto": f"Pergi ke {act.params[1] if len(act.params)>1 else act.params[0]}",
            "goto_through_gate": f"Lewati gerbang menuju {act.params[1] if len(act.params)>1 else act.params[0]}",
            "buy_seed_radish": "Beli Benih Lobak di Toko (5 koin)",
            "buy_bottle": "Beli Botol Kosong di Toko (8 koin)",
            "buy_armor_leather": "Beli Zirah Kulit di Toko (15 koin)",
            "buy_weapon_dagger": "Beli Belati Cepat di Toko (12 koin)",
            "sell_radish": "Jual Lobak ke Toko (+10 koin)",
            "sell_egg": "Jual Telur ke Toko (+6 koin)",
            "sell_fish": "Jual Ikan ke Toko (+15 koin)",
            "sell_milk": "Jual Susu ke Toko (+12 koin)",
            "sell_wood": "Jual Kayu ke Toko (+5 koin)",
            "sell_rock": "Jual Batu ke Toko (+5 koin)",
            "plant_radish": f"Tanam Benih Lobak di Ladang ({act.params[0] if act.params else 'plot0'})",
            "water_radish": f"Siram Air pada Petak Ladang ({act.params[0] if act.params else 'plot0'})",
            "wait_grow_radish": "Tunggu tanaman lobak matang (12.5s)",
            "harvest_radish": f"Panen Lobak Matang ({act.params[0] if act.params else 'plot0'})",
            "collect_egg": "Ambil Telur di Kandang Ayam",
            "collect_milk": "Perah Susu di Padang Sapi",
            "fish": "Memancing Ikan di Dermaga Sungai",
            "chop_wood": "Tebang Kayu di Hutan",
            "mine_rock": "Tambang Batu di Tebing",
            "craft_potion": "Racik Health Potion di Bengkel",
            "craft_key": "Tempa Kunci Gerbang di Bengkel (1 Kayu + 1 Batu)",
            "open_gate": "Buka Gerbang Reruntuhan dengan Kunci",
            "equip_starter": "Pasang Peralatan Pemula (Pedang & Kain)",
            "equip_leather": "Pasang Zirah Kulit",
            "rest": "Istirahat di Ranjang (Pulihkan HP 100%)",
            "fight_boss": "Kalahkan Skeleton Overlord di Arena Boss!"
        }

        desc = descriptions.get(act.name, f"Lakukan {act.name} {act.params}")
        return f"[ADVISOR Langkah {step_num}/{total_steps}] {desc}"

    def update(self, dt: float):
        """
        Loop update autopilot yang dipanggil setiap frame permainan.
        """
        if self.mode != PlannerMode.AUTO or self.is_paused_by_player:
            return

        if self.state in (AutopilotState.IDLE, AutopilotState.SURRENDERED, AutopilotState.PAUSED):
            return

        act = self.monitor.current_action
        if act is None:
            self.state = AutopilotState.IDLE
            self.status_message = "Misi ekspedisi selesai!"
            return

        # 1. Periksa pre-kondisi dengan PlanMonitor
        status = self.monitor.check_preconditions(hero=self.hero, game_map=self.game_map)
        if not status.is_valid:
            self.status_message = f"[Pemicu {status.trigger}] {status.message}"
            replan_ok = self._request_new_plan()
            if not replan_ok:
                return

        # 2. Eksekusi aksi
        step_res = self.executor.execute_action(act, advance_crops=True)
        if step_res.success:
            self.status_message = f"Selesai: {act.name} -> {step_res.message}"
            self.monitor.advance_step()
        else:
            self.status_message = f"Gagal: {act.name} -> {step_res.message}"
            self._request_new_plan()

