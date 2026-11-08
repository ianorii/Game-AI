"""
local_search.py - SIMULATED ANNEALING untuk auto-optimise layout dungeon

Tekan [O] di dalam game untuk menjalankan algoritma ini:
  1. Layout jebakan/monster saat ini dianggap state awal.
  2. Secara acak "merelokasi" posisi sebuah item (neighbor).
  3. Difficulty Score dievaluasi ulang; state lebih buruk masih bisa
     diterima dengan probabilitas exp(delta / temperature)  -> escape local optima.
  4. Temperature diturunkan tiap iterasi (cooling) sampai batas minimum,
     lalu layout terbaik yang ditemukan diterapkan kembali ke dungeon.

Statistik live (Current Temp / Current Score / Best Score) ditampilkan
lewat overlay debug [F3].
"""

import math
import random
from dataclasses import dataclass, field

import config
from ai.csp import Placement
from ai.pathfinding import manhattan


# ==============================================================================
# EVALUASI "SEBERAPA MEMATIKAN" SEBUAH LAYOUT  (objective function)
# ==============================================================================
def evaluate_difficulty(placements, hero_path, tile_map, core_cell, boss_cell, csp):
    """
    Difficulty Score:
      +12  jebakan tepat di jalur A* hero
      +10  monster mengintai di sekitar jalur hero (jarak <= 2)
      +14  monster persis di jalur hero (AMBUSH)
      +6   jebakan dekat Core (last line of defense)
      -20  per pelanggaran constraint (CSP)
      -80  jalur Spawn -> Core terblokir penuh
      -2   biaya tiap item (mencegah spam)
    """
    score = 0.0
    path_set = set(hero_path)
    for p in placements:
        cell = p.cell
        if p.kind in ("fire_trap", "ice_trap"):
            if cell in path_set:
                score += 12
            if manhattan(cell, core_cell) <= 2:
                score += 6
            if boss_cell and manhattan(cell, boss_cell) <= 1:
                score += 4
        else:  # ice_monster
            if cell in path_set:
                score += 14
            elif any(manhattan(cell, c) <= 2 for c in hero_path):
                score += 10
        score -= 2  # biaya per item

    report = csp.audit(placements)
    score -= 20 * len(report.violations)
    if not report.path_valid:
        score -= 80
    return round(score, 2)


# ==============================================================================
# SIMULATED ANNEALING
# ==============================================================================
@dataclass
class SASnapshot:
    running: bool = False
    finished: bool = False
    temp: float = config.SA_START_TEMP
    current_score: float = 0.0
    best_score: float = 0.0
    iteration: int = 0
    accepted: int = 0
    rejected: int = 0
    start_score: float = 0.0
    history: list = field(default_factory=list)   # (iter, score)


class SimulatedAnnealing:
    """SA sederhana yang berjalan incremental (beberapa iterasi per frame)."""

    def __init__(self, tile_map, csp, seed=config.LEVEL_SEED_DEFAULT):
        self.map = tile_map
        self.csp = csp
        self.rng = random.Random(seed)
        self.snapshot = SASnapshot()
        self.best_layout = []
        self._placements = []
        self._hero_path = []
        self._core = (0, 0)
        self._boss = None

    # -------------------------------------------------------------- lifecycle
    @property
    def running(self):
        return self.snapshot.running

    def start(self, placements, hero_path, core_cell, boss_cell):
        self._placements = [Placement(p.kind, p.gx, p.gy) for p in placements]
        self._hero_path = list(hero_path)
        self._core = core_cell
        self._boss = boss_cell
        cur = self._score(self._placements)
        self.snapshot = SASnapshot(
            running=True, finished=False,
            temp=config.SA_START_TEMP,
            current_score=cur, best_score=cur, start_score=cur)
        self.best_layout = list(self._placements)

    def stop(self, apply_best=False):
        self.snapshot.running = False
        self.snapshot.finished = True
        return self.best_layout if apply_best else None

    # -------------------------------------------------------------- internals
    def _score(self, placements):
        return evaluate_difficulty(placements, self._hero_path, self.map,
                                   self._core, self._boss, self.csp)

    def _neighbor(self, placements):
        """Proposal state tetangga: relokasi / pertukaran / mutasi jenis item."""
        out = [Placement(p.kind, p.gx, p.gy) for p in placements]
        if not out:
            return out
        occupied = {p.cell for p in out}
        cells = getattr(self.map, "defense_cells", None) or self.map.floor_cells
        floor = [c for c in cells
                 if c not in (self.map.spawn, self.map.core)]
        roll = self.rng.random()
        if roll < 0.70:                       # relokasi satu item
            i = self.rng.randrange(len(out))
            p = out.pop(i)
            free = [c for c in floor if c not in occupied]
            if not free:
                out.insert(i, p)
                return out
            cell = self.rng.choice(free)
            out.append(Placement(p.kind, cell[0], cell[1]))
        elif roll < 0.90 and len(out) >= 2:   # tukar posisi dua item
            i, j = self.rng.sample(range(len(out)), 2)
            a, b = out[i], out[j]
            out[i] = Placement(a.kind, b.gx, b.gy)
            out[j] = Placement(b.kind, a.gx, a.gy)
        else:                                 # mutasi jenis item
            i = self.rng.randrange(len(out))
            kind = self.rng.choice(list(config.ITEM_ENERGY))
            out[i] = Placement(kind, out[i].gx, out[i].gy)
        return out

    def step(self, iterations=1):
        """Jalankan N iterasi SA (dipanggil tiap frame saat [O] aktif)."""
        snap = self.snapshot
        if not snap.running:
            return
        for _ in range(iterations):
            snap.iteration += 1
            cand = self._neighbor(self._placements)
            cand_score = self._score(cand)
            delta = cand_score - snap.current_score
            if delta >= 0:
                accept = True
            else:
                prob = math.exp(delta / max(snap.temp, 1e-6))
                accept = self.rng.random() < prob
            if accept:
                self._placements = cand
                snap.current_score = cand_score
                snap.accepted += 1
                if cand_score > snap.best_score:
                    snap.best_score = cand_score
                    self.best_layout = [Placement(p.kind, p.gx, p.gy) for p in cand]
            else:
                snap.rejected += 1
            snap.temp *= config.SA_ALPHA
            if snap.iteration % 4 == 0:
                snap.history.append((snap.iteration, snap.current_score))
                if len(snap.history) > 240:
                    snap.history.pop(0)
            if snap.temp < config.SA_MIN_TEMP:
                snap.running = False
                snap.finished = True
                snap.temp = config.SA_MIN_TEMP
                break
