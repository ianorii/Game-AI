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
                 distance_matrix: Optional[DistanceMatrix] = None, game: Any = None):
        self.world_state = world_state
        self.hero = hero
        self.game_map = game_map
        self.game = game
        self.mode = PlannerMode.OFF
        self.state = AutopilotState.IDLE

        self.distance_matrix = distance_matrix or DistanceMatrix(game_map=game_map)
        self.monitor = PlanMonitor(world_state, distance_matrix=self.distance_matrix)
        self.executor = PlanExecutor(world_state, hero=hero, game_map=game_map, game=game)

        self.current_path: List[Tuple[int, int]] = []
        self.target_location_name: Optional[str] = None
        self.status_message: str = "Mode Planner: OFF"
        self.is_paused_by_player: bool = False
        self.navigating_act: Optional[GroundAction] = None
        self.interacting_act: Optional[GroundAction] = None
        self.interaction_timer: float = 0.0
        self.advisor_replan_cooldown: float = 0.0

    def toggle_mode(self) -> str:
        """Berpindah antara mode OFF -> ADVISOR -> AUTO -> OFF."""
        idx = PlannerMode.ALL.index(self.mode) if self.mode in PlannerMode.ALL else 0
        self.mode = PlannerMode.ALL[(idx + 1) % len(PlannerMode.ALL)]
        self.is_paused_by_player = False
        self.navigating_act = None
        self.interacting_act = None
        self.interaction_timer = 0.0

        if self.mode == PlannerMode.OFF:
            self.state = AutopilotState.IDLE
            self.status_message = "Mode Planner dimatikan (OFF)."
            if self.hero:
                self.hero.set_path([])
        elif self.mode == PlannerMode.ADVISOR:
            self.status_message = "Mode ADVISOR aktif: Menampilkan saran langkah."
            if not self.monitor.current_plan or self.monitor.current_action is None:
                self._request_new_plan()
            self.update_advisor(0.0)
        elif self.mode == PlannerMode.AUTO:
            self.status_message = "Mode AUTO aktif: Hero bergerak mandiri."
            self.monitor.surrendered = False
            self.monitor.consecutive_replans = 0
            if not self.monitor.current_plan or self.monitor.current_action is None:
                self._request_new_plan()
            else:
                self.state = AutopilotState.IDLE

        return self.mode

    def _request_new_plan(self) -> bool:
        """Membuat rencana baru dari kondisi dunia saat ini."""
        self.state = AutopilotState.PLANNING
        self.monitor.surrendered = False
        self.monitor.consecutive_replans = 0
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
            "goto_through_gate": f"Menuju {act.params[1] if len(act.params)>1 else act.params[0]} (Lawan Boss)",
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
            "craft_key": "Tempa Kunci Segel Bos di Bengkel (1 Kayu + 1 Batu)",
            "open_gate": "Lawan Boss (Buka Segel dengan Kunci)",
            "equip_starter": "Pasang Peralatan Pemula (Pedang & Kain)",
            "equip_leather": "Pasang Zirah Kulit",
            "rest": "Istirahat di Ranjang (Pulihkan HP 100%)",
            "fight_boss": "Kalahkan Skeleton Overlord di Arena Boss!"
        }

        desc = descriptions.get(act.name, f"Lakukan {act.name} {act.params}")
        return f"[ADVISOR Langkah {step_num}/{total_steps}] {desc}"

    def on_belief_updated(self, weather_manager: Any):
        """
        Merespons pembaruan keyakinan cuaca dari Papan Pengumuman Cuaca.
        Jika kebijakan optimal berubah menjadi 'Raya' (detour aman memutar),
        memicu evaluasi ulang rencana (TRIGGER_BELIEF_UPDATE).
        """
        if not weather_manager:
            return
        policy = getattr(weather_manager, "optimal_policy", "Pintas")
        belief = getattr(weather_manager, "belief_flood", 0.10)
        self.status_message = f"[TRIGGER_BELIEF_UPDATE] P(Banjir)={belief*100:.1f}% -> Kebijakan={policy.upper()}"
        if policy == "Raya":
            if self.mode == PlannerMode.AUTO:
                self._request_new_plan()
                self.status_message = f"[TRIGGER_BELIEF_UPDATE] {self.status_message}"

    def _is_action_completed(self, act: GroundAction) -> bool:
        """
        Mengecek apakah efek dari aksi STRIPS saat ini telah dipenuhi oleh aksi manual pemain di dunia nyata.
        Digunakan oleh mode ADVISOR untuk memajukan langkah saran secara otomatis saat pemain
        berhasil melakukan instruksi (misal membeli benih, tiba di lokasi, menebang pohon, dll).
        """
        if not act:
            return False

        name = act.name
        params = act.params

        # 1. Aksi Pergerakan (goto / goto_through_gate)
        if name in ("goto", "goto_through_gate"):
            to_loc = params[1] if len(params) > 1 else params[0]
            locs = getattr(config, "LOCATIONS", {})
            target_pt = locs.get(to_loc)
            if to_loc == "boss":
                if hasattr(self, "game") and self.game and hasattr(self.game, "boss") and self.game.boss:
                    target_pt = (self.game.boss.px, self.game.boss.py)
                elif hasattr(config, "BOSS_FIELD_POS"):
                    target_pt = config.BOSS_FIELD_POS

            if self.hero and target_pt:
                dist = math.hypot(self.hero.px - target_pt[0], self.hero.py - target_pt[1])
                # Ambang batas toleransi kedatangan (~2.25 tile = 72 px)
                if dist <= 72.0:
                    return True
            return False

        # 2. Aksi Belanja di Toko (buy_*)
        if name == "buy_seed_radish":
            inv = self.world_state.inventory
            if inv.has_item("seeds_radish", 1) or inv.has_item("radish", 1) or inv.has_item("potion_red", 1):
                return True
            plots = getattr(getattr(self.world_state, "farm", None), "plots", [])
            if any(getattr(p, "crop_type", None) == "radish" for p in plots):
                return True
            return False

        if name == "buy_bottle":
            inv = self.world_state.inventory
            if inv.has_item("bottle_empty", 1) or inv.has_item("potion_red", 1):
                return True
            return False

        if name == "buy_armor_leather":
            inv = self.world_state.inventory
            eq = getattr(self.world_state, "equipped_armor", None)
            if inv.has_item("Kulit", 1) or eq == "Kulit" or eq == "Besi" or inv.has_item("Besi", 1):
                return True
            return False

        if name == "buy_fire_staff":
            inv = self.world_state.inventory
            eq = getattr(self.world_state, "equipped_weapon", None)
            if inv.has_item("Tongkat Api", 1) or eq == "Tongkat Api":
                return True
            return False

        if name == "buy_weapon_dagger":
            inv = self.world_state.inventory
            eq = getattr(self.world_state, "equipped_weapon", None)
            if inv.has_item("Belati Cepat", 1) or eq == "Belati Cepat":
                return True
            return False

        if name == "buy_weapon_axe":
            inv = self.world_state.inventory
            eq = getattr(self.world_state, "equipped_weapon", None)
            if inv.has_item("Kapak Berat", 1) or eq == "Kapak Berat":
                return True
            return False

        if name == "buy_armor_iron":
            inv = self.world_state.inventory
            eq = getattr(self.world_state, "equipped_armor", None)
            if inv.has_item("Besi", 1) or eq == "Besi":
                return True
            return False

        if name == "buy_gate_key":
            inv = self.world_state.inventory
            if inv.has_item("gate_key", 1) or getattr(self.world_state.gate, "is_open", False):
                return True
            return False

        if name == "buy_item":
            item = params[0] if params else ""
            if item and self.world_state.inventory.has_item(item, 1):
                return True
            return False

        # 3. Aksi Penjualan di Toko (sell_*)
        if name == "sell_fish":
            inv = self.world_state.inventory
            target_coin = 0
            if len(params) > 1 and params[1].startswith("c"):
                try:
                    target_coin = int(params[1][1:])
                except ValueError:
                    target_coin = 0
            if not inv.has_item("fish", 1) and (self.world_state.coins >= target_coin or target_coin == 0):
                return True
            return False

        if name == "sell_radish":
            inv = self.world_state.inventory
            if not inv.has_item("radish", 1):
                return True
            return False

        if name in ("sell_egg", "sell_milk", "sell_wood", "sell_rock"):
            item_raw = name.replace("sell_", "")
            if not self.world_state.inventory.has_item(item_raw, 1):
                return True
            return False

        # 4. Pengumpulan Bahan Alam
        if name == "fish":
            if self.world_state.inventory.has_item("fish", 1):
                return True
            return False

        if name in ("mine_rock", "mine_rock_river"):
            inv = self.world_state.inventory
            if inv.has_item("rock", 1) or inv.has_item("gate_key", 1) or getattr(self.world_state.gate, "is_open", False):
                return True
            return False

        if name == "chop_wood":
            inv = self.world_state.inventory
            if inv.has_item("wood", 1) or inv.has_item("gate_key", 1) or getattr(self.world_state.gate, "is_open", False):
                return True
            return False

        if name == "collect_egg":
            return self.world_state.inventory.has_item("egg", 1)

        if name == "collect_milk":
            return self.world_state.inventory.has_item("milk", 1)

        # 5. Agronomi & Farm
        if name == "plant_radish":
            plots = getattr(getattr(self.world_state, "farm", None), "plots", [])
            inv = self.world_state.inventory
            if any(getattr(p, "crop_type", None) == "radish" for p in plots) or inv.has_item("radish", 1) or inv.has_item("potion_red", 1):
                return True
            return False

        if name == "water_radish":
            plots = getattr(getattr(self.world_state, "farm", None), "plots", [])
            inv = self.world_state.inventory
            if any(getattr(p, "is_watered", False) for p in plots) or any(getattr(p, "is_mature", False) for p in plots) or inv.has_item("radish", 1) or inv.has_item("potion_red", 1):
                return True
            return False

        if name == "wait_grow_radish":
            plots = getattr(getattr(self.world_state, "farm", None), "plots", [])
            inv = self.world_state.inventory
            if any(getattr(p, "is_mature", False) for p in plots) or inv.has_item("radish", 1) or inv.has_item("potion_red", 1):
                return True
            return False

        if name == "harvest_radish":
            inv = self.world_state.inventory
            if inv.has_item("radish", 1) or inv.has_item("potion_red", 1):
                return True
            return False

        # 6. Crafting di Bengkel
        if name == "craft_key":
            inv = self.world_state.inventory
            if inv.has_item("gate_key", 1) or getattr(self.world_state.gate, "is_open", False):
                return True
            return False

        if name == "craft_potion":
            if self.world_state.inventory.has_item("potion_red", 1):
                return True
            return False

        # 7. Membuka Gerbang
        if name == "open_gate":
            if getattr(self.world_state.gate, "is_open", False):
                return True
            return False

        # 8. Perlengkapan Tempur
        if name.startswith("equip"):
            if getattr(self.world_state, "equipped_ok", False):
                return True
            w = params[0] if len(params) > 0 else None
            a = params[1] if len(params) > 1 else None
            w_ok = (not w or getattr(self.world_state, "equipped_weapon", None) == w)
            a_ok = (not a or getattr(self.world_state, "equipped_armor", None) == a)
            if w_ok and a_ok:
                return True
            return False

        # 9. Pemulihan HP
        if name == "rest":
            if self.hero and self.hero.hp >= self.hero.max_hp:
                return True
            return False

        # 10. Pertarungan Boss
        if name == "fight_boss":
            boss = getattr(self.world_state, "boss", None)
            if getattr(boss, "is_defeated", False) or getattr(self.world_state, "boss_defeated", False):
                return True
            return False

        return False

    def update_advisor(self, dt: float):
        """
        Memantau aksi pemain secara pasif dalam mode ADVISOR.
        Mendeteksi jika pemain telah menyelesaikan langkah yang disarankan
        (misal: membeli benih di toko, tiba di lokasi target, menebang pohon, dll)
        dan memajukan indeks langkah secara otomatis.
        Jika kondisi dunia berubah sehingga langkah tidak lagi valid,
        memicu replanning otonom agar saran langkah selalu mutakhir.
        """
        if self.mode != PlannerMode.ADVISOR:
            return

        if self.advisor_replan_cooldown > 0:
            self.advisor_replan_cooldown = max(0.0, self.advisor_replan_cooldown - dt)

        if not self.monitor.current_plan or self.monitor.current_action is None:
            if not self.monitor.current_plan and not self.monitor.surrendered:
                self._request_new_plan()
            return

        # 1. Periksa apakah aksi saat ini (atau aksi berikutnya) telah diselesaikan secara manual oleh pemain
        advanced = False
        loop_guard = 0
        while loop_guard < 5:
            act = self.monitor.current_action
            if not act:
                break
            if self._is_action_completed(act):
                self.monitor.advance_step()
                advanced = True
                loop_guard += 1
            else:
                break

        if advanced:
            next_act = self.monitor.current_action
            if next_act:
                from planning.planner_ui import format_action_human
                act_title, _ = format_action_human(next_act)
                self.status_message = f"[ADVISOR] Langkah selesai! Lanjut: {act_title}"
            else:
                self.status_message = "[ADVISOR] Seluruh langkah ekspedisi telah selesai!"
            return

        # 2. Jika aksi belum selesai, periksa validitas prekondisi langkah saat ini.
        # Bila pemain menyimpang dan prekondisi gagal, picu replanning (dengan cooldown).
        if self.advisor_replan_cooldown <= 0:
            act = self.monitor.current_action
            if act:
                status = self.monitor.check_preconditions(hero=self.hero, game_map=self.game_map)
                if not status.is_valid:
                    self.advisor_replan_cooldown = 1.5
                    self._request_new_plan()

    def update(self, dt: float):
        """
        Loop update autopilot yang dipanggil setiap frame permainan.
        Menggerakkan Hero secara fisik di dunia game tile-by-tile via A*,
        memberikan pacing aksi yang halus, dan memvalidasi prekondisi kontinu.
        """
        if self.mode == PlannerMode.ADVISOR:
            self.update_advisor(dt)
            return

        if self.mode != PlannerMode.AUTO or self.is_paused_by_player:
            return

        if self.state in (AutopilotState.SURRENDERED, AutopilotState.PAUSED):
            return

        # 1. State NAVIGATING: Hero sedang berjalan di peta menuju lokasi tujuan
        if self.state == AutopilotState.NAVIGATING:
            if self.hero and (self.hero.moving or (hasattr(self.hero, "path") and len(self.hero.path) > 0)):
                # Hero masih melangkah di peta, biarkan berjalan
                return
            else:
                # Hero telah tiba di tujuan!
                if self.navigating_act:
                    step_res = self.executor.execute_action(self.navigating_act, advance_crops=True)
                    self.status_message = f"Tiba di {self.target_location_name or 'tujuan'}!"
                    self.monitor.advance_step()
                    self.navigating_act = None
                    self.target_location_name = None
                    self.state = AutopilotState.IDLE
                return

        # 2. State INTERACTING: Hero sedang menjalankan aksi di tempat (potong kayu, crafting, dll)
        if self.state == AutopilotState.INTERACTING:
            self.interaction_timer -= dt
            if self.interaction_timer > 0:
                return
            else:
                # Timer aksi selesai, terapkan efeknya di world_state
                if self.interacting_act:
                    step_res = self.executor.execute_action(self.interacting_act, advance_crops=True)
                    if step_res.success:
                        self.status_message = f"Selesai: {self.interacting_act.name}"
                        self.monitor.advance_step()
                    else:
                        self.status_message = f"Gagal: {self.interacting_act.name} -> {step_res.message}"
                        self._request_new_plan()
                    self.interacting_act = None
                    self.state = AutopilotState.IDLE
                return

        # 3. State IDLE: Ambil aksi berikutnya dari monitor
        act = self.monitor.current_action
        if act is None:
            self.state = AutopilotState.IDLE
            self.status_message = "Selesai! Boss telah dikalahkan."
            return

        # Periksa prekondisi dengan PlanMonitor
        status = self.monitor.check_preconditions(hero=self.hero, game_map=self.game_map)
        if not status.is_valid:
            self.status_message = f"[Pemicu {status.trigger}] {status.message}"
            replan_ok = self._request_new_plan()
            if not replan_ok:
                return
            act = self.monitor.current_action
            if not act:
                return

        # Eksekusi aksi:
        # A. Aksi Pergerakan (goto / goto_through_gate)
        if act.name in ("goto", "goto_through_gate"):
            to_loc = act.params[1] if len(act.params) > 1 else act.params[0]
            from_loc = act.params[0] if len(act.params) > 1 else "spawn"
            self.target_location_name = to_loc
            self.navigating_act = act

            locs = getattr(config, "LOCATIONS", {})
            target_pt = locs.get(to_loc)
            if to_loc == "boss":
                if hasattr(self, "game") and self.game and hasattr(self.game, "boss") and self.game.boss:
                    target_pt = (self.game.boss.px - 32, self.game.boss.py)
                elif hasattr(config, "BOSS_FIELD_POS"):
                    target_pt = (config.BOSS_FIELD_POS[0] - 32, config.BOSS_FIELD_POS[1])

            # Cari path A* dari posisi hero sekarang
            path_tiles = None
            if self.hero and target_pt:
                hero_cell = getattr(self.hero, "cell", (int(self.hero.px // 32), int(self.hero.py // 32)))
                target_cell = (int(target_pt[0] // 32), int(target_pt[1] // 32))
                
                # Gunakan cache distance matrix jika hero berada di from_loc
                _, _, dm_path = self.distance_matrix.get_distance(
                    from_loc, to_loc, gate_open=self.world_state.gate.is_open
                )
                if dm_path and len(dm_path) > 0 and hero_cell == dm_path[0]:
                    path_tiles = list(dm_path)
                elif self.game_map:
                    from ai.pathfinding import astar
                    def is_blocked(cx, cy):
                        if not self.game_map.can_stand(pygame.Rect(cx * 32 + 9, cy * 32 + 12, 14, 8)):
                            return True
                        return False
                    res = astar(self.game_map.width // 32, self.game_map.height // 32,
                                hero_cell, target_cell, is_blocked)
                    if res.found:
                        path_tiles = res.path

            if self.hero and path_tiles and len(path_tiles) > 0:
                self.hero.manual_mode = False
                self.hero.set_control_dir(None)
                self.hero.set_path(path_tiles)
                self.state = AutopilotState.NAVIGATING
                self.status_message = f"Menuju {to_loc} ({len(path_tiles)} langkah)..."
            else:
                # Fallback teleport instan jika sudah berada di lokasi atau path kosong
                step_res = self.executor.execute_action(act, advance_crops=True)
                self.monitor.advance_step()
                self.navigating_act = None
                self.target_location_name = None
                self.state = AutopilotState.IDLE
            return

        # B. Aksi Interaksi Dunia (potong kayu, tambang batu, tempa kunci, tanam, beli barang, dll)
        else:
            self.interacting_act = act
            self.state = AutopilotState.INTERACTING
            # Berikan waktu animasi singkat (0.4s) agar player melihat aksi hero
            self.interaction_timer = 0.4
            if self.hero:
                if "chop" in act.name or "mine" in act.name:
                    self.hero.action_anim = "attack"
                    self.hero.action_anim_duration = 0.4
                elif "craft" in act.name or "water" in act.name or "plant" in act.name:
                    self.hero.action_anim = "casting"
                    self.hero.action_anim_duration = 0.4
                elif "fight" in act.name:
                    self.hero.action_anim = "attack"
                    self.hero.action_anim_duration = 0.8
            self.status_message = f"Melakukan {act.name}..."
            return

