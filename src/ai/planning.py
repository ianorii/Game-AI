"""
planning.py - AUTOMATED PLANNING (STRIPS / Goal-Based Planning)

Hero mempunyai RENCANA (plan) berupa urutan aksi STRIPS:
    Cast Buff -> Cross Trap -> Attack Boss -> Steal Core
(persisnya disusun otomatis oleh planner berdasarkan kondisi dunia).

Setiap aksi STRIPS punya:
    preconditions : fakta yang harus benar sebelum aksi dieksekusi
    add_effects   : fakta yang menjadi benar setelah aksi dieksekusi

Planner mencari rencana via BFS pada ruang state fakta (goal-based).
Bila LINGKUNGAN BERUBAH (mis. pemain memasang jebakan baru di jalur hero),
PlanMonitor mendeklarasikan "PLAN FAILURE" lalu melakukan DYNAMIC RE-PLAN.
Progress rencana ini ditampilkan real-time pada overlay debug [F5].
"""

from collections import deque
from dataclasses import dataclass


# ==============================================================================
# DEFINISI AKSI STRIPS
# ==============================================================================
@dataclass(frozen=True)
class STRIPSAction:
    name: str
    preconditions: frozenset
    add_effects: frozenset
    description: str = ""

    def applicable(self, facts):
        return self.preconditions <= facts


DEFAULT_ACTIONS = [
    STRIPSAction("RESTORE_MANA", frozenset({"hero_ready"}), frozenset({"has_mana"}),
                 "Isi ulang Mana di altar spawn"),
    STRIPSAction("CAST_BUFF", frozenset({"hero_ready", "has_mana"}), frozenset({"buffed"}),
                 "Cast Buff: +50% damage"),
    STRIPSAction("CROSS_TRAP", frozenset({"hero_ready", "buffed", "traps_on_path"}),
                 frozenset({"traps_crossed"}),
                 "Seberangi ladang jebakan dengan buff aktif"),
    STRIPSAction("APPROACH_BOSS", frozenset({"hero_ready"}), frozenset({"confronted_boss"}),
                 "Menuju Boss penjaga Core"),
    STRIPSAction("ATTACK_BOSS", frozenset({"confronted_boss", "buffed"}),
                 frozenset({"boss_defeated"}),
                 "Kalahkan Boss dalam turn-based battle"),
    STRIPSAction("STEAL_CORE", frozenset({"boss_defeated"}), frozenset({"core_stolen"}),
                 "Curi Inti (Core) Dungeon"),
]


# ==============================================================================
# PLANNER (forward search / BFS pada ruang state fakta)
# ==============================================================================
def plan(initial_facts, goal, actions=DEFAULT_ACTIONS, max_depth=14):
    """
    Mencari urutan aksi STRIPS dari `initial_facts` menuju `goal`
    memakai BFS (setiap langkah state = himpunan fakta).
    Mengembalikan list[STRIPSAction] atau None bila tak ada solusi.
    """
    start = frozenset(initial_facts)
    goal = frozenset(goal)
    if goal <= start:
        return []
    queue = deque([(start, [])])
    visited = {start}
    while queue:
        facts, path = queue.popleft()
        if len(path) >= max_depth:
            continue
        for action in actions:
            if not action.applicable(facts):
                continue
            new_facts = facts | action.add_effects
            if new_facts == facts:
                continue
            if new_facts in visited:
                continue
            new_path = path + [action]
            if goal <= new_facts:
                return new_path
            visited.add(new_facts)
            queue.append((new_facts, new_path))
    return None


# ==============================================================================
# PLAN MONITOR - deteksi plan failure + dynamic re-plan
# ==============================================================================
class PlanMonitor:
    """
    Memantau rencana Hero vs kondisi dunia nyata.
      - update(world_facts) dipanggil tiap frame oleh game.
      - declare_failure(alasan) dipanggil saat lingkungan berubah
        (mis. jebakan baru terpasang) -> langsung re-plan.
    """

    def __init__(self, initial_facts, goal=("core_stolen",),
                 actions=DEFAULT_ACTIONS):
        self.goal = tuple(goal)
        self.actions = actions
        self.facts = set(initial_facts)
        self.plan = []
        self.replan_count = 0
        self.status = "OK"
        self.last_failure = "-"
        self.failure_log = []
        self.status_timer = 0.0
        self.replan()

    # ------------------------------------------------------------------ plan
    def replan(self):
        result = plan(self.facts, self.goal, self.actions)
        self.replan_count += 1
        if result is None:
            self.plan = []
            self.status = "NO PLAN"
        else:
            self.plan = result
            if self.status != "PLAN FAILURE":
                self.status = "OK"
        return result

    def declare_failure(self, reason):
        """Deklarasi PLAN FAILURE (lingkungan berubah) -> dynamic re-plan."""
        self.status = "PLAN FAILURE"
        self.last_failure = reason
        self.failure_log.append(reason)
        if len(self.failure_log) > 6:
            self.failure_log.pop(0)
        self.status_timer = 1.4
        self.replan()

    # ---------------------------------------------------------------- update
    def update(self, world_facts, dt=0.0):
        self.facts = set(world_facts)
        if self.status_timer > 0:
            self.status_timer -= dt
            if self.status_timer <= 0 and self.status == "PLAN FAILURE":
                self.status = "OK"

    # ------------------------------------------------------------------ view
    def step_states(self):
        """
        [(status_langkah, action)] dengan aturan progres:
        langkah DONE bila seluruh efeknya sudah ada di fakta dunia
        ATAU langkah berikutnya sudah tercapai (dunia bergerak melewatinya).
        """
        achieved = [set(a.add_effects) <= self.facts for a in self.plan]
        out = []
        first_open = True
        for i, action in enumerate(self.plan):
            later = any(achieved[j] for j in range(i + 1, len(self.plan)))
            if achieved[i] or later:
                state = "DONE"
            elif first_open:
                state = "ACTIVE"
                first_open = False
            else:
                state = "PENDING"
            out.append((state, action))
        return out

    def active_action(self):
        for state, action in self.step_states():
            if state == "ACTIVE":
                return action
        return None

    def progress(self):
        """(selesai, total) langkah rencana."""
        states = self.step_states()
        return sum(1 for s, _ in states if s == "DONE"), len(states)
