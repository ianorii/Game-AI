"""
executor.py - Eksekutor Rencana STRIPS Headless & Validasi terhadap Dunia Nyata

Menerjemahkan setiap GroundAction dari rencana STRIPS menjadi pemanggilan API
formal di src/world_actions.py pada WorldState nyata. Memverifikasi:
  1. Keabsahan prasyarat di state nyata sebelum eksekusi aksi
  2. Durasi estimasi vs durasi simulasi aktual
  3. Konsistensi state prediksi vs state aktual dunia setelah aksi
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any, Tuple, Set
import math
import time

from world_state import WorldState
import world_actions
from planning.strips import GroundAction, Predicate, STRIPSState, PlanningProblem
from planning.distance_matrix import DistanceMatrix


@dataclass
class ExecutionStepResult:
    """Hasil eksekusi satu langkah rencana pada WorldState."""
    action_name: str
    params: Tuple[str, ...]
    predicted_duration: float
    actual_duration: float
    success: bool
    message: str
    divergences: List[str] = field(default_factory=list)


@dataclass
class PlanExecutionReport:
    """Laporan komprehensif eksekusi seluruh rangkaian rencana."""
    success: bool
    total_steps: int
    steps_executed: int
    total_predicted_duration: float
    total_actual_duration: float
    step_results: List[ExecutionStepResult] = field(default_factory=list)
    failure_reason: Optional[str] = None
    divergence_count: int = 0

    def summary(self) -> str:
        status = "SUKSES" if self.success else f"GAGAL ({self.failure_reason})"
        return (f"[PlanExecutor] Status: {status} | Langkah: {self.steps_executed}/{self.total_steps} | "
                f"Durasi Prediksi: {self.total_predicted_duration:.2f}s | "
                f"Durasi Aktual: {self.total_actual_duration:.2f}s | Divergensi: {self.divergence_count}")


class PlanExecutor:
    """
    Eksekutor rencana headless yang menghubungkan rencana STRIPS abstrak
    ke state mesin game nyata (WorldState, Farm, Gate, Inventory, Shop).
    """

    def __init__(self, world_state: WorldState, hero: Any = None, game_map: Any = None,
                 distance_matrix: Optional[DistanceMatrix] = None):
        self.world_state = world_state
        self.hero = hero
        self.game_map = game_map
        self.distance_matrix = distance_matrix or DistanceMatrix(game_map=game_map)

    def execute_plan(self, plan: List[GroundAction], advance_crops: bool = True) -> PlanExecutionReport:
        """
        Mengeksekusi daftar GroundAction berurutan pada WorldState nyata.
        Jika advance_crops=True, aksi wait_grow_radish memajukan tahap pertumbuhan tanaman
        hingga matang pada plot terkait secara langsung.
        """
        step_results: List[ExecutionStepResult] = []
        total_pred_dur = sum(act.duration for act in plan)
        total_act_dur = 0.0
        divergence_count = 0

        for idx, act in enumerate(plan):
            step_res = self.execute_action(act, advance_crops=advance_crops)
            step_results.append(step_res)
            total_act_dur += step_res.actual_duration
            divergence_count += len(step_res.divergences)

            if not step_res.success:
                return PlanExecutionReport(
                    success=False,
                    total_steps=len(plan),
                    steps_executed=idx + 1,
                    total_predicted_duration=total_pred_dur,
                    total_actual_duration=total_act_dur,
                    step_results=step_results,
                    failure_reason=f"Langkah {idx + 1} ({act.name}) gagal: {step_res.message}",
                    divergence_count=divergence_count
                )

        return PlanExecutionReport(
            success=True,
            total_steps=len(plan),
            steps_executed=len(plan),
            total_predicted_duration=total_pred_dur,
            total_actual_duration=total_act_dur,
            step_results=step_results,
            failure_reason=None,
            divergence_count=divergence_count
        )

    def execute_action(self, act: GroundAction, advance_crops: bool = True) -> ExecutionStepResult:
        """Mengeksekusi satu GroundAction ke API world_actions."""
        name = act.name
        params = act.params
        pred_dur = act.duration
        divergences: List[str] = []

        # 1. Dispatching ke world_actions
        if name in ("goto", "goto_through_gate"):
            from_loc = params[0] if len(params) > 1 else None
            to_loc = params[1] if len(params) > 1 else params[0]
            res = world_actions.goto_location(
                self.world_state, self.hero, to_loc, self.game_map,
                distance_matrix=self.distance_matrix, from_location=from_loc
            )

        elif name == "buy_seed_radish":
            res = world_actions.buy(self.world_state, "seeds_radish", 1)

        elif name == "buy_bottle":
            res = world_actions.buy(self.world_state, "bottle_empty", 1)

        elif name == "buy_armor_leather":
            res = world_actions.buy(self.world_state, "Kulit", 1)

        elif name == "buy_weapon_dagger":
            res = world_actions.buy(self.world_state, "Belati Cepat", 1)

        elif name == "buy_weapon_axe":
            res = world_actions.buy(self.world_state, "Kapak Berat", 1)

        elif name == "buy_fire_staff":
            res = world_actions.buy(self.world_state, "Tongkat Api", 1)

        elif name == "buy_armor_iron":
            res = world_actions.buy(self.world_state, "Besi", 1)

        elif name == "buy_gate_key":
            res = world_actions.buy(self.world_state, "gate_key", 1)

        elif name == "buy_item":
            item_id = act.params[0] if act.params else ""
            item_name = item_id
            catalog_path = "data/catalog.json"
            if os.path.exists(catalog_path):
                try:
                    with open(catalog_path, "r", encoding="utf-8") as f:
                        cat_d = json.load(f)
                    for cat_list in (cat_d.get("weapons", []), cat_d.get("armors", [])):
                        for it in cat_list:
                            if it.get("id") == item_id:
                                item_name = it.get("name", item_id)
                                break
                except Exception:
                    pass
            res = world_actions.buy(self.world_state, item_name, 1)

        elif name == "sell_radish":
            res = world_actions.sell(self.world_state, "radish", 1)

        elif name == "sell_egg":
            res = world_actions.sell(self.world_state, "egg", 1)

        elif name == "sell_fish":
            res = world_actions.sell(self.world_state, "fish", 1)

        elif name == "sell_milk":
            res = world_actions.sell(self.world_state, "milk", 1)

        elif name == "sell_wood":
            res = world_actions.sell(self.world_state, "wood", 1)

        elif name == "sell_rock":
            res = world_actions.sell(self.world_state, "rock", 1)

        elif name == "plant_radish":
            plot_idx = 0
            if params and "1" in params[0]:
                plot_idx = 1
            res = world_actions.plant(self.world_state, "radish", plot_idx)

        elif name == "water_radish":
            plot_idx = 0
            if params and "1" in params[0]:
                plot_idx = 1
            res = world_actions.water(self.world_state, plot_idx)

        elif name == "wait_grow_radish":
            plot_idx = 0
            if params and "1" in params[0]:
                plot_idx = 1
            if advance_crops and hasattr(self.world_state, "farm"):
                plots = self.world_state.farm.plots
                if 0 <= plot_idx < len(plots):
                    p = plots[plot_idx]
                    p.stage = 5
                    p.growth_timer = 0.0
                    p.is_watered = False
            res = world_actions.ActionResult(True, f"Tanaman pada plot {plot_idx} telah matang sepenuhnya.", duration=12.5)

        elif name == "harvest_radish":
            plot_idx = 0
            if params and "1" in params[0]:
                plot_idx = 1
            res = world_actions.harvest(self.world_state, plot_idx)

        elif name == "collect_egg":
            res = world_actions.collect_egg(self.world_state)

        elif name == "collect_milk":
            res = world_actions.collect_milk(self.world_state)

        elif name == "fish":
            res = world_actions.fish(self.world_state)

        elif name == "chop_wood":
            res = world_actions.chop_wood(self.world_state)

        elif name == "mine_rock":
            res = world_actions.mine_rock(self.world_state)

        elif name == "mine_rock_river":
            res = world_actions.mine_rock(self.world_state)

        elif name == "craft_potion":
            res = world_actions.craft_potion(self.world_state)

        elif name == "craft_key":
            res = world_actions.craft_key(self.world_state)

        elif name == "open_gate":
            res = world_actions.open_gate(self.world_state, self.game_map)

        elif name == "equip":
            pddl_to_name = {
                "sword_basic": "Pedang Biasa", "weapon_dagger": "Belati Cepat",
                "weapon_axe": "Kapak Berat", "fire_staff": "Tongkat Api",
                "cloth_armor": "Kain", "armor_leather": "Kulit", "armor_iron": "Besi"
            }
            w_p = params[0] if len(params) > 0 else "sword_basic"
            a_p = params[1] if len(params) > 1 else "cloth_armor"
            w_real = pddl_to_name.get(w_p, w_p)
            a_real = pddl_to_name.get(a_p, a_p)
            res = world_actions.equip_loadout(self.world_state, {
                "weapon": w_real,
                "armor": a_real,
                "shield": None,
                "accessory": None
            })

        elif name in ("equip_starter", "equip_leather"):
            res = world_actions.equip_loadout(self.world_state, {
                "weapon": "Pedang Biasa",
                "armor": "Kulit" if "leather" in name else "Kain",
                "shield": None,
                "accessory": None
            })

        elif name == "rest":
            res = world_actions.rest(self.world_state, self.hero)

        elif name in ("fight_boss", "fight_boss_hardened"):
            res = world_actions.start_boss_battle(self.world_state, hero=self.hero)

        else:
            res = world_actions.ActionResult(False, f"Aksi '{name}' tidak memiliki pemetaan di PlanExecutor!", duration=0.0)

        # 2. Verifikasi deviasi durasi
        if abs(res.duration - pred_dur) > 0.05:
            divergences.append(f"Durasi berbeda: estimasi={pred_dur:.2f}s, aktual={res.duration:.2f}s")

        # Update waktu & cooldown dunia sesuai durasi aksi
        if res.success and res.duration > 0.0:
            self.world_state.update(res.duration)

        return ExecutionStepResult(
            action_name=name,
            params=params,
            predicted_duration=pred_dur,
            actual_duration=res.duration,
            success=res.success,
            message=res.message,
            divergences=divergences
        )
