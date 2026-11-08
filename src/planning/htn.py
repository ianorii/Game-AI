"""
htn.py - Hierarchical Task Network (HTN) Planner untuk NPC Desa Sunnyside (Sub-fase 2C)

Implementasi SHOP-style Total-Order Forward Decomposition dengan Backtracking:
  1. Parsing domain tugas majemuk (compound tasks), metode alternatif, dan operator primitif.
  2. Dekomposisi tugas tingkat tinggi dengan >= 2 metode alternatif per task.
  3. Pohon dekomposisi hierarkis (HTNDecompositionNode) untuk visualisasi panel F8.
  4. Monitoring kondisi dunia dinamis & replanning otonom (misal: hero memanen petak yang dituju).
  5. Pengendali rutinitas NPC (Petani & Penggiling) dengan jam siang-malam (WorldClock)
     dan status expression icon (working, confused, chat, rest).
"""

from dataclasses import dataclass, field
from typing import List, Dict, Set, Tuple, Optional, Any, Callable
import time
import math
import re

import config
from world_state import WorldState
from planning.distance_matrix import DistanceMatrix


# ==============================================================================
# DATA STRUKTUR SIMBOLIK HTN
# ==============================================================================

@dataclass(frozen=True)
class HTNTask:
    """Tugas dalam jaringan HTN: bisa primitif (diawali '!') atau majemuk."""
    name: str
    args: Tuple[str, ...] = ()

    @property
    def is_primitive(self) -> bool:
        return self.name.startswith("!")

    def __str__(self) -> str:
        if self.args:
            return f"({self.name} {' '.join(self.args)})"
        return f"({self.name})"


@dataclass
class HTNOperator:
    """Operator primitif yang langsung mengubah fakta dunia."""
    name: str
    params: Tuple[str, ...]
    preconditions: List[Tuple[str, ...]]
    add_effects: List[Tuple[str, ...]]
    del_effects: List[Tuple[str, ...]]
    duration: float = 1.0


@dataclass
class HTNMethod:
    """Metode pemecahan tugas majemuk menjadi rangkaian subtask."""
    task_name: str
    method_name: str
    params: Tuple[str, ...]
    preconditions: List[Tuple[str, ...]]
    subtasks: List[HTNTask]


@dataclass
class HTNDecompositionNode:
    """Simpul pohon dekomposisi hierarki tugas aktif (untuk panel UI F8)."""
    task: HTNTask
    chosen_method: Optional[str] = None
    precondition_reason: str = ""
    status: str = "PENDING"  # "PENDING", "EXECUTING", "COMPLETED", "FAILED"
    children: List["HTNDecompositionNode"] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task": str(self.task),
            "method": self.chosen_method,
            "reason": self.precondition_reason,
            "status": self.status,
            "children": [c.to_dict() for c in self.children]
        }


# ==============================================================================
# SHOP-STYLE HTN FORWARD DECOMPOSITION ENGINE
# ==============================================================================

class HTNDomain:
    """Domain HTN yang menampung operator dan metode."""
    def __init__(self, name: str = "sunnyside_npc"):
        self.name = name
        self.operators: Dict[str, HTNOperator] = {}
        self.methods: Dict[str, List[HTNMethod]] = {}

    def add_operator(self, op: HTNOperator):
        self.operators[op.name] = op

    def add_method(self, method: HTNMethod):
        self.methods.setdefault(method.task_name, []).append(method)


def match_facts(pattern: Tuple[str, ...], facts: Set[Tuple[str, ...]],
                binding: Dict[str, str]) -> List[Dict[str, str]]:
    """Mencari seluruh unifikasi yang memenuhi fakta pattern dengan binding saat ini."""
    pred_name = pattern[0]
    arg_patterns = pattern[1:]

    results: List[Dict[str, str]] = []
    for f in facts:
        if f[0] != pred_name or len(f) - 1 != len(arg_patterns):
            continue
        new_bind = dict(binding)
        match = True
        for p_arg, f_val in zip(arg_patterns, f[1:]):
            if p_arg.startswith("?"):
                if p_arg in new_bind:
                    if new_bind[p_arg] != f_val:
                        match = False
                        break
                else:
                    new_bind[p_arg] = f_val
            else:
                if p_arg != f_val:
                    match = False
                    break
        if match:
            results.append(new_bind)
    return results


def satisfy_preconditions(preconditions: List[Tuple[str, ...]], facts: Set[Tuple[str, ...]],
                          binding: Dict[str, str]) -> List[Dict[str, str]]:
    """Memeriksa konjungsi prasyarat dan mengembalikan seluruh binding yang sah."""
    if not preconditions:
        return [binding]

    current_bindings = [binding]
    for pre in preconditions:
        next_bindings = []
        for b in current_bindings:
            matches = match_facts(pre, facts, b)
            next_bindings.extend(matches)
        current_bindings = next_bindings
        if not current_bindings:
            return []

    return current_bindings


def ground_task(task: HTNTask, binding: Dict[str, str]) -> HTNTask:
    """Mengganti variabel parameter tugas dengan nilai konkret dari binding."""
    ground_args = tuple(binding.get(a, a) for a in task.args)
    return HTNTask(name=task.name, args=ground_args)


class SHOPPlanner:
    """
    SHOP-Style Total-Order Forward Decomposition Planner.
    Mendekomposisi agenda tugas secara maju dengan pelacakan pohon dan rekursi sederhana.
    """

    def __init__(self, domain: HTNDomain, distance_matrix: Optional[DistanceMatrix] = None):
        self.domain = domain
        self.distance_matrix = distance_matrix or DistanceMatrix()

    def plan(self, initial_facts: Set[Tuple[str, ...]], tasks: List[HTNTask],
             initial_binding: Optional[Dict[str, str]] = None) -> Tuple[bool, List[HTNTask], List[HTNDecompositionNode]]:
        """
        Menghasilkan rangkaian operator primitif dan pohon dekomposisi dari agenda tugas.
        """
        facts = set(initial_facts)
        binding = dict(initial_binding or {})
        plan_ops: List[HTNTask] = []
        root_nodes: List[HTNDecompositionNode] = []

        success, final_plan, tree = self._seek_plan(facts, tasks, binding, depth=0)
        if success:
            return True, final_plan, tree
        return False, [], []

    def _seek_plan(self, facts: Set[Tuple[str, ...]], task_agenda: List[HTNTask],
                   binding: Dict[str, str], depth: int) -> Tuple[bool, List[HTNTask], List[HTNDecompositionNode]]:
        if depth > 50:
            return False, [], []  # Pencegahan rekursi tak hingga

        if not task_agenda:
            return True, [], []

        task = task_agenda[0]
        ground_t = ground_task(task, binding)
        remaining_tasks = task_agenda[1:]

        # 1. Kasus Tugas Primitif (Operator)
        if ground_t.is_primitive:
            op_def = self.domain.operators.get(ground_t.name)
            if op_def is None:
                return False, [], []

            # Periksa prasyarat operator
            bound_preconds = []
            param_map = dict(zip(op_def.params, ground_t.args))
            for pre in op_def.preconditions:
                bound_p = tuple(param_map.get(a, a) for a in pre)
                bound_preconds.append(bound_p)

            valid_binds = satisfy_preconditions(bound_preconds, facts, {})
            if not valid_binds:
                return False, [], []  # Prasyarat primitif gagal, backtrack!

            # Terapkan add & del effects pada state simulasi maju
            next_facts = set(facts)
            for d in op_def.del_effects:
                del_fact = tuple(param_map.get(a, a) for a in d)
                next_facts.discard(del_fact)
            for a in op_def.add_effects:
                add_fact = tuple(param_map.get(a, a) for a in a)
                next_facts.add(add_fact)

            node = HTNDecompositionNode(task=ground_t, chosen_method="primitive_operator",
                                       precondition_reason="Prasyarat primitif terpenuhi", status="COMPLETED")

            ok, downstream_plan, downstream_nodes = self._seek_plan(next_facts, remaining_tasks, binding, depth + 1)
            if ok:
                return True, [ground_t] + downstream_plan, [node] + downstream_nodes
            return False, [], []

        # 2. Kasus Tugas Majemuk (Compound Task)
        methods = self.domain.methods.get(ground_t.name, [])
        for m in methods:
            # Petakan argumen tugas ke parameter metode
            m_bind = dict(binding)
            for p_name, t_val in zip(m.params, ground_t.args):
                m_bind[p_name] = t_val

            # Dapatkan binding yang memenuhi prasyarat metode
            valid_binds = satisfy_preconditions(m.preconditions, facts, m_bind)
            for bind_candidate in valid_binds:
                # Siapkan subtasks dengan grounding
                subtasks_to_add = [ground_task(st, bind_candidate) for st in m.subtasks]
                new_agenda = subtasks_to_add + remaining_tasks

                reason_desc = f"Memilih '{m.method_name}' karena prasyarat {m.preconditions} terpenuhi di state."
                node = HTNDecompositionNode(task=ground_t, chosen_method=m.method_name,
                                           precondition_reason=reason_desc, status="COMPLETED")

                ok, sub_plan, sub_nodes = self._seek_plan(facts, new_agenda, bind_candidate, depth + 1)
                if ok:
                    # Ambil sub_nodes yang dihasilkan oleh subtasks_to_add sebagai anak
                    num_children = len(subtasks_to_add)
                    node.children = sub_nodes[:num_children]
                    remaining_nodes = sub_nodes[num_children:]
                    return True, sub_plan, [node] + remaining_nodes

        return False, [], []


# ==============================================================================
# WORLD CLOCK & NPC AGENT RUNTIME
# ==============================================================================

class WorldClock:
    """Jam simulasi siklus siang-malam desa Sunnyside."""
    def __init__(self, day_duration: float = 60.0, night_duration: float = 30.0):
        self.day_duration = day_duration
        self.night_duration = night_duration
        self.total_cycle = day_duration + night_duration
        self.time_seconds: float = 0.0

    def update(self, dt: float):
        self.time_seconds = (self.time_seconds + dt) % self.total_cycle

    @property
    def is_daytime(self) -> bool:
        return (self.time_seconds % self.total_cycle) < self.day_duration

    @property
    def time_string(self) -> str:
        cycle_pos = self.time_seconds % self.total_cycle
        phase = "SIANG" if self.is_daytime else "MALAM"
        return f"{phase} ({cycle_pos:.1f}s / {self.total_cycle:.1f}s)"


class ExpressionIcon:
    IDLE = "idle"
    WORKING = "working"
    CONFUSED = "confused"
    CHAT = "chat"
    REST = "rest"


class HTNNPCAgent:
    """
    Agen NPC otonom (Petani / Penggiling) yang digerakkan oleh perencana HTN.
    """

    def __init__(self, name: str, role: str, starting_loc: str, domain: HTNDomain,
                 world_state: WorldState, hair_style: str = "curly", distance_matrix: Optional[DistanceMatrix] = None):
        self.name = name
        self.role = role  # "farmer" atau "miller"
        self.current_location = starting_loc
        self.hair_style = hair_style
        self.domain = domain
        self.world_state = world_state
        self.distance_matrix = distance_matrix or DistanceMatrix()
        self.planner = SHOPPlanner(domain, distance_matrix=self.distance_matrix)

        locs = getattr(config, "LOCATIONS", {})
        pos = locs.get(starting_loc, (1000, 750))
        self.px = float(pos[0])
        self.py = float(pos[1])
        self.sort_y = self.py

        self.expression: str = ExpressionIcon.IDLE
        self.expression_timer: float = 0.0
        self.active_operator_queue: List[HTNTask] = []
        self.active_tree: List[HTNDecompositionNode] = []
        self.replan_history: List[str] = []
        self.current_op_duration: float = 0.0
        self.current_op_elapsed: float = 0.0
        self.replan_count: int = 0

    def get_world_facts(self, clock: Optional[WorldClock] = None) -> Set[Tuple[str, ...]]:
        """Mengekstraksi fakta-fakta simbolik dunia saat ini untuk input perencana HTN."""
        facts: Set[Tuple[str, ...]] = set()

        # Lokasi NPC
        facts.add(("at", self.role, self.current_location))

        # Jam dunia
        if clock is not None:
            if clock.is_daytime:
                facts.add(("is_daytime",))
            else:
                facts.add(("is_night",))
        else:
            facts.add(("is_daytime",))

        # Status petak ladang
        plots = self.world_state.farm.plots if hasattr(self.world_state, "farm") else []
        has_mature = False
        has_dry = False
        has_empty = False

        for idx, p in enumerate(plots):
            p_name = f"plot{idx}"
            if p.crop_type is None:
                facts.add(("plot_empty", p_name))
                has_empty = True
            elif p.is_mature:
                facts.add(("plot_mature", p_name))
                facts.add(("has_mature_crop", p_name))
                has_mature = True
            else:
                facts.add(("plot_planted", p_name))
                if not p.is_watered:
                    facts.add(("plot_dry", p_name))
                    facts.add(("has_dry_plot", p_name))
                    has_dry = True
                else:
                    facts.add(("plot_watered", p_name))

        if has_mature:
            facts.add(("has_mature_crop", "plot0"))
        if has_dry:
            facts.add(("has_dry_plot", "plot0"))
        if has_empty:
            facts.add(("has_empty_plot", "plot0"))

        # Status gandum di toko untuk penggiling
        # Toko selalu memiliki suplai gandum untuk penggiling
        facts.add(("wheat_available",))

        # Hewan ternak
        facts.add(("chickens_hungry",))

        return facts

    def request_htn_plan(self, clock: Optional[WorldClock] = None) -> bool:
        """Menghasilkan rencana HTN baru berdasarkan peran dan jam dunia."""
        facts = self.get_world_facts(clock)

        if self.role == "farmer":
            root_task = HTNTask("daily_routine_farmer", (self.role,))
        elif self.role == "miller":
            root_task = HTNTask("daily_routine_miller", (self.role,))
        else:
            root_task = HTNTask("daily_routine_farmer", (self.role,))

        ok, plan_ops, tree = self.planner.plan(facts, [root_task], initial_binding={"?npc": self.role, "?from": self.current_location})
        if ok and plan_ops:
            self.active_operator_queue = list(plan_ops)
            self.active_tree = tree
            self.current_op_elapsed = 0.0
            chosen = tree[0].chosen_method if tree else "None"
            log_entry = f"[{time.strftime('%H:%M:%S')}] Replan #{self.replan_count + 1}: Metode '{chosen}' ({len(plan_ops)} operator)"
            self.replan_history.append(log_entry)
            self.replan_count += 1
            return True
        return False

    def check_and_replan_if_needed(self, clock: Optional[WorldClock] = None) -> bool:
        """
        Memeriksa apakah aksi primitif berikutnya masih sah di dunia.
        Jika tidak sah (misal petak ladang diambil hero), seketika picu replan otonom!
        """
        if not self.active_operator_queue:
            return self.request_htn_plan(clock)

        # Pengecekan prasyarat panen: jika hero memanen tanaman matang duluan
        has_harvest_op = any(op.name == "!harvest_crop" for op in self.active_operator_queue)
        if has_harvest_op:
            plots = self.world_state.farm.plots if hasattr(self.world_state, "farm") else []
            has_mature = any(p.is_mature for p in plots)
            if not has_mature:
                # Precondition gagal! Hero mengambil tanaman matang duluan!
                self.expression = ExpressionIcon.CONFUSED
                self.expression_timer = 2.0
                self.replan_history.append(f"[{time.strftime('%H:%M:%S')}] ANOMALI: Tanaman matang dipanen pemain! Memicu replanning...")
                return self.request_htn_plan(clock)

        return True

    def update(self, dt: float, clock: Optional[WorldClock] = None, hero: Any = None):
        """Update langkah NPC tiap frame."""
        if self.expression_timer > 0:
            self.expression_timer -= dt
            if self.expression_timer <= 0:
                self.expression = ExpressionIcon.IDLE

        # Cek interaksi hero (chat jika hero dekat < 40px)
        if hero is not None and hasattr(hero, "px") and hasattr(hero, "py"):
            dist_to_hero = math.hypot(self.px - hero.px, self.py - hero.py)
            if dist_to_hero < 45.0:
                self.expression = ExpressionIcon.CHAT

        if not self.active_operator_queue:
            self.request_htn_plan(clock)
            return

        # Validasi prasyarat
        self.check_and_replan_if_needed(clock)
        if not self.active_operator_queue:
            return

        current_op = self.active_operator_queue[0]
        self.current_op_elapsed += dt

        # Jalankan aksi
        if current_op.name == "!goto":
            dest_loc = current_op.args[2] if len(current_op.args) > 2 else current_op.args[-1]
            locs = getattr(config, "LOCATIONS", {})
            target_pos = locs.get(dest_loc, (self.px, self.py))

            # Gerakkan posisi menuju sasaran
            dx = target_pos[0] - self.px
            dy = target_pos[1] - self.py
            dist = math.hypot(dx, dy)
            speed = 80.0  # piksel per detik
            if dist > 4.0:
                self.px += (dx / dist) * speed * dt
                self.py += (dy / dist) * speed * dt
                self.sort_y = self.py
            else:
                self.px, self.py = float(target_pos[0]), float(target_pos[1])
                self.current_location = dest_loc
                self.active_operator_queue.pop(0)
                self.current_op_elapsed = 0.0

        elif current_op.name in ("!harvest_crop", "!water_crop", "!plant_crop", "!mill_wheat", "!feed_animals"):
            self.expression = ExpressionIcon.WORKING
            if self.current_op_elapsed >= 1.0:
                if current_op.name == "!harvest_crop":
                    plot_idx = 0
                    if hasattr(self.world_state, "farm"):
                        self.world_state.farm.harvest(self.world_state.inventory, plot_idx=plot_idx)
                elif current_op.name == "!water_crop":
                    if hasattr(self.world_state, "farm"):
                        self.world_state.farm.water(plot_idx=0)
                elif current_op.name == "!mill_wheat":
                    pass
                self.active_operator_queue.pop(0)
                self.current_op_elapsed = 0.0
                self.expression = ExpressionIcon.IDLE

        elif current_op.name in ("!sell_produce", "!buy_seed", "!take_wheat", "!deliver_flour", "!inspect_mill", "!rest"):
            if self.current_op_elapsed >= 0.5:
                if current_op.name == "!rest":
                    self.expression = ExpressionIcon.REST
                self.active_operator_queue.pop(0)
                self.current_op_elapsed = 0.0

    def draw(self, screen: Any, render_cam: Tuple[int, int], time: float = 0.0):
        """Menggambar sprite NPC desa dengan layer Sunnyside, bayangan, nama, dan ikon ekspresi."""
        import pygame
        from hero_sprite import HeroSpriteManager
        hsm = HeroSpriteManager.get_instance()
        frames = hsm.get_npc_world_frames("idle", hair_style=self.hair_style)
        if not frames:
            return

        cam_x, cam_y = render_cam
        f_idx = int(time * 6.0) % len(frames)
        frame_surf = frames[f_idx]

        draw_x = int(self.px - cam_x - 24)
        draw_y = int(self.py - cam_y - 42)

        # Bayangan kaki
        shadow_surf = pygame.Surface((28, 12), pygame.SRCALPHA)
        pygame.draw.ellipse(shadow_surf, (0, 0, 0, 90), (0, 0, 28, 12))
        screen.blit(shadow_surf, (draw_x + 10, draw_y + 36))

        screen.blit(frame_surf, (draw_x, draw_y))

        # Label nama NPC
        font_xs = pygame.font.Font(None, 14)
        name_surf = font_xs.render(self.name, True, (240, 235, 180))
        screen.blit(name_surf, (draw_x + 24 - name_surf.get_width() // 2, draw_y - 12))

        # Ikon ekspresi jika aktif
        if getattr(self, "expression", None) and self.expression != "idle":
            from asset_catalog import get_asset_catalog
            cat = get_asset_catalog()
            icon_key = f"UI/expression_{self.expression}.png"
            expr_surf = cat.get_image(icon_key)
            if expr_surf is not None:
                screen.blit(expr_surf, (draw_x + 24 - expr_surf.get_width() // 2, draw_y - 28))


# ==============================================================================
# PARSER & FACTORY DOMAIN HTN DARI FILE npc.htn (S-Expression Recursive Descent)
# ==============================================================================

def _tokenize(text: str) -> List[str]:
    """Membersihkan komentar dan memecah teks ke dalam token tanda kurung dan kata."""
    clean = []
    for line in text.splitlines():
        if ";" in line:
            line = line[:line.index(";")]
        clean.append(line)
    text_clean = "\n".join(clean)
    return text_clean.replace("(", " ( ").replace(")", " ) ").split()


def _parse_tokens(tokens: List[str]) -> Any:
    """Menguraikan token menjadi struktur nested list S-expression."""
    if not tokens:
        return []
    tok = tokens.pop(0)
    if tok == "(":
        lst = []
        while tokens and tokens[0] != ")":
            lst.append(_parse_tokens(tokens))
        if tokens and tokens[0] == ")":
            tokens.pop(0)
        return lst
    else:
        return tok


def parse_htn_file(file_path: str = "data/planning/npc.htn") -> HTNDomain:
    """Membaca file domain npc.htn dan membangun objek HTNDomain lengkap."""
    with open(file_path, "r", encoding="utf-8") as f:
        tokens = _tokenize(f.read())

    sexpr = _parse_tokens(tokens)
    if not sexpr or not isinstance(sexpr, list) or len(sexpr) < 2:
        return HTNDomain("sunnyside_npc")

    domain_name = sexpr[1] if len(sexpr) > 1 else "sunnyside_npc"
    domain = HTNDomain(domain_name)

    for item in sexpr[2:]:
        if not isinstance(item, list) or not item:
            continue
        tag = item[0]

        if tag == ":operator":
            # (:operator (!name ?p1 ?p2) :precondition (...) :del (...) :add (...) :duration D)
            task_decl = item[1]
            op_name = task_decl[0]
            params = tuple(task_decl[1:]) if len(task_decl) > 1 else ()

            preconditions: List[Tuple[str, ...]] = []
            add_effects: List[Tuple[str, ...]] = []
            del_effects: List[Tuple[str, ...]] = []
            dur = 1.0

            idx = 2
            while idx < len(item):
                key = item[idx]
                if key == ":precondition" and idx + 1 < len(item):
                    pre_list = item[idx + 1]
                    if isinstance(pre_list, list):
                        preconditions = [tuple(p) for p in pre_list if isinstance(p, list) and p]
                    idx += 2
                elif key == ":del" and idx + 1 < len(item):
                    del_list = item[idx + 1]
                    if isinstance(del_list, list):
                        del_effects = [tuple(p) for p in del_list if isinstance(p, list) and p]
                    idx += 2
                elif key == ":add" and idx + 1 < len(item):
                    add_list = item[idx + 1]
                    if isinstance(add_list, list):
                        add_effects = [tuple(p) for p in add_list if isinstance(p, list) and p]
                    idx += 2
                elif key == ":duration" and idx + 1 < len(item):
                    val = item[idx + 1]
                    try:
                        dur = float(val) if not isinstance(val, list) else 1.0
                    except (ValueError, TypeError):
                        dur = 1.0
                    idx += 2
                else:
                    idx += 1

            domain.add_operator(HTNOperator(
                name=op_name, params=params, preconditions=preconditions,
                add_effects=add_effects, del_effects=del_effects, duration=dur
            ))

        elif tag == ":method":
            # (:method (task_name ?p1) :name method_name :precondition (...) :subtasks (...))
            task_decl = item[1]
            task_name = task_decl[0]
            params = tuple(task_decl[1:]) if len(task_decl) > 1 else ()

            method_name = ""
            preconditions = []
            subtasks: List[HTNTask] = []

            idx = 2
            while idx < len(item):
                key = item[idx]
                if key == ":name" and idx + 1 < len(item):
                    method_name = item[idx + 1]
                    idx += 2
                elif key == ":precondition" and idx + 1 < len(item):
                    pre_list = item[idx + 1]
                    if isinstance(pre_list, list):
                        preconditions = [tuple(p) for p in pre_list if isinstance(p, list) and p]
                    idx += 2
                elif key == ":subtasks" and idx + 1 < len(item):
                    st_list = item[idx + 1]
                    if isinstance(st_list, list):
                        for st in st_list:
                            if isinstance(st, list) and st:
                                subtasks.append(HTNTask(name=st[0], args=tuple(st[1:])))
                    idx += 2
                else:
                    idx += 1

            domain.add_method(HTNMethod(
                task_name=task_name, method_name=method_name,
                params=params, preconditions=preconditions, subtasks=subtasks
            ))

    return domain
