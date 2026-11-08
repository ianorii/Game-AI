"""
csp.py - CONSTRAINT SATISFACTION PROBLEM untuk validasi penempatan jebakan
         dan monster oleh pemain (Dungeon Overseer).

Variabel  : item yang akan dipasang (fire_trap / ice_trap / ice_monster)
Domain    : sel lantai yang legal di grid dungeon
Aturan (constraints):
  R1 - Jalur Spawn -> Core harus tetap ADA (tidak terblokir penuh).
  R2 - Fire Trap tidak boleh bersebelahan (4-arah) dengan Ice Monster.
  R3 - Total konsumsi energi tidak boleh melebihi kapasitas Core.

Solver backtracking internal dipakai untuk menyusun layout otomatis
(dipakai tombol [O] saat peta masih kosong); bila pustaka
`python-constraint` terinstal (requirements.txt), solver tersebut juga
tersedia lewat solve_with_python_constraint().
"""

import random
from dataclasses import dataclass, field

import config
from ai.pathfinding import astar, manhattan


# ==============================================================================
# STRUKTUR DATA
# ==============================================================================
@dataclass(frozen=True)
class Placement:
    kind: str          # "fire_trap" | "ice_trap" | "ice_monster"
    gx: int
    gy: int

    @property
    def cell(self):
        return (self.gx, self.gy)


@dataclass
class Violation:
    cell: tuple
    kind: str
    rule: str
    message: str


@dataclass
class CSPReport:
    constraints: list = field(default_factory=list)   # [(kode, terpenuhi, detail)]
    violations: list = field(default_factory=list)    # [Violation]
    ok_cells: set = field(default_factory=set)        # sel penempatan yang valid
    bad_cells: set = field(default_factory=set)       # sel penempatan yang melanggar
    energy_used: int = 0
    capacity: int = config.CORE_ENERGY_CAPACITY
    path_valid: bool = True

    @property
    def satisfied(self):
        return not self.violations


try:                                   # opsional - lihat requirements.txt
    from constraint import Problem, AllDifferentConstraint
    HAS_PYTHON_CONSTRAINT = True
except Exception:                      # pragma: no cover
    Problem = None
    HAS_PYTHON_CONSTRAINT = False


# ==============================================================================
# CSP UTAMA
# ==============================================================================
class PlacementCSP:
    """Validasi & penjadwalan penempatan item di dungeon."""

    RULES = {
        "R1": "Jalur Spawn -> Core harus tetap valid (tidak terblokir penuh)",
        "R2": "Fire Trap dilarang bersebelahan dengan Ice Monster",
        "R3": "Total energi terpasang <= kapasitas Core",
    }

    def __init__(self, tile_map):
        self.map = tile_map

    # ---------------------------------------------------------------- domain
    def monster_cells(self, placements):
        return {p.cell for p in placements if p.kind == "ice_monster"}

    def energy_used(self, placements):
        return sum(config.ITEM_ENERGY.get(p.kind, 0) for p in placements)

    def candidate_cells(self, placements=None):
        """
        Sel lantai legal untuk penempatan.

        Di dunia open-world, memilih acak dari SELURUH peta membuat layout
        tersebar terlalu jauh dari jalur Hero. Karena itu solver memakai
        `defense_cells` (area sekitar Core) bila tersedia; penempatan manual
        pemain tetap bebas di sel lantai mana pun.
        """
        taken = set(self.monster_cells(placements or []))
        cells = getattr(self.map, "defense_cells", None) or self.map.floor_cells
        out = []
        for cell in cells:
            if cell in taken:
                continue
            if cell == self.map.spawn or cell == self.map.core:
                continue
            out.append(cell)
        return out

    # ---------------------------------------------------------------- R1
    def static_blockers(self, placements):
        """Dinding + monster hasil pasangan pemain (tidak termasuk patroli)."""
        return self.monster_cells(placements)

    def path_valid(self, placements):
        blockers = self.static_blockers(placements)
        w, h = self.map.width, self.map.height

        def blocked(x, y):
            return self.map.is_wall(x, y) or (x, y) in blockers

        res = astar(w, h, self.map.spawn, self.map.core, blocked, track=False)
        return res.found

    # ---------------------------------------------------------------- cek 1 sel
    def can_place(self, placements, kind, cell, check_path=True):
        """
        Validasi 1 penempatan terhadap seluruh constraint.
        -> (True, []) bila valid / (False, [pesan-pelanggaran])

        `check_path=False` dipakai untuk pratinjau massal (overlay F2): aturan
        R1 (A* Spawn->Core) hanya diuji saat pemain benar-benar memasang item,
        sehingga audit ribuan sel di dunia besar tetap ringan.
        """
        problems = []
        gx, gy = cell

        # domain: harus lantai, bukan area terlarang, belum terisi
        if not self.map.in_bounds(gx, gy) or self.map.is_wall(gx, gy):
            problems.append("Sel adalah dinding / di luar grid")
        if cell in (self.map.spawn, self.map.core):
            problems.append("Spawn & Core tidak boleh ditimpa")
        occupied = {p.cell for p in placements}
        if cell in occupied:
            problems.append("Sel sudah terisi item lain")
        if cell == (self.map.hero_start if hasattr(self.map, "hero_start") else (-1, -1)):
            problems.append("Tidak boleh di atas Hero")

        # R3 - energi
        cost = config.ITEM_ENERGY.get(kind, 0)
        if self.energy_used(placements) + cost > config.CORE_ENERGY_CAPACITY:
            problems.append(
                f"R3 melanggar: energi {self.energy_used(placements)}+{cost} > "
                f"kapasitas {config.CORE_ENERGY_CAPACITY}")

        # R2 - adjansi fire trap <-> ice monster
        if kind == "fire_trap":
            for d in ((0, 1), (0, -1), (1, 0), (-1, 0)):
                if (gx + d[0], gy + d[1]) in self.monster_cells(placements):
                    problems.append("R2 melanggar: Fire Trap bersebelahan dengan Ice Monster")
                    break
        elif kind == "ice_monster":
            for p in placements:
                if p.kind == "fire_trap" and manhattan(p.cell, cell) == 1:
                    problems.append("R2 melanggar: Ice Monster bersebelahan dengan Fire Trap")
                    break

        # R1 - jalur spawn->core tetap ada (hanya monster yang memblokir)
        if check_path and kind == "ice_monster" and not problems:
            probe = list(placements) + [Placement(kind, gx, gy)]
            if not self.path_valid(probe):
                problems.append("R1 melanggar: monster ini memblokir penuh jalur Spawn->Core")

        return (not problems), problems

    # ---------------------------------------------------------------- audit
    def audit(self, placements, selected_kind=None):
        """Audit seluruh layout terpasang -> CSPReport untuk overlay F2."""
        report = CSPReport()
        report.energy_used = self.energy_used(placements)
        report.capacity = config.CORE_ENERGY_CAPACITY
        report.path_valid = self.path_valid(placements)

        # R1
        if report.path_valid:
            report.constraints.append(("R1", True, "Jalur Spawn -> Core terbuka"))
        else:
            report.constraints.append(("R1", False, "Jalur Spawn -> Core TERBLOKIR"))
            for p in placements:
                if p.kind == "ice_monster":
                    report.violations.append(Violation(
                        p.cell, p.kind, "R1", "Monster memblokir jalur Spawn->Core"))

        # R2
        bad_pair = set()
        monsters = self.monster_cells(placements)
        for p in placements:
            if p.kind != "fire_trap":
                continue
            for d in ((0, 1), (0, -1), (1, 0), (-1, 0)):
                ncell = (p.gx + d[0], p.gy + d[1])
                if ncell in monsters:
                    bad_pair.add(p.cell)
                    report.violations.append(Violation(
                        p.cell, p.kind, "R2", f"Fire Trap bersebelahan dengan Ice Monster di {ncell}"))
        for cell in bad_pair:
            for mcell in monsters:
                if manhattan(mcell, cell) == 1:
                    report.violations.append(Violation(
                        mcell, "ice_monster", "R2", f"Ice Monster bersebelahan dengan Fire Trap di {cell}"))
        report.constraints.append(
            ("R2", not any(v.rule == "R2" for v in report.violations),
             "Fire Trap <-> Ice Monster saling berjauhan"
             if not any(v.rule == "R2" for v in report.violations)
             else "Ada pasangan Fire Trap <-> Ice Monster yang terlalu dekat"))

        # R3
        over = report.energy_used > report.capacity
        report.constraints.append(
            ("R3", not over,
             f"Energi terpakai {report.energy_used}/{report.capacity}"
             + (" - MELEBIHI KAPASITAS!" if over else " (aman)")))
        if over:
            for p in placements:
                report.violations.append(Violation(
                    p.cell, p.kind, "R3", "Total energi melebihi kapasitas Core"))

        # sel penempatan yang terlibat pelanggaran
        bad = {v.cell for v in report.violations}
        for p in placements:
            if p.cell in bad:
                report.bad_cells.add(p.cell)
            else:
                report.ok_cells.add(p.cell)

        # pratinjau grid utk item terpilih (dipakai overlay F2 & kursor)
        if selected_kind:
            occupied = {p.cell for p in placements}
            for cell in self.map.floor_cells:
                if cell in (self.map.spawn, self.map.core) or cell in occupied:
                    continue
                ok, _ = self.can_place(placements, selected_kind, cell,
                                       check_path=False)
                (report.ok_cells if ok else report.bad_cells).add(cell)
        return report

    # ---------------------------------------------------------------- solver
    def suggest_layout(self, kinds, rng: random.Random, limit=12):
        """
        Solver backtracking CSP: susun seluruh `kinds` pada domain legal
        tanpa melanggar R1-R3. Mengembalikan list[Placement] (bisa parsial).
        """
        placements = []
        cells = self.candidate_cells([])
        rng.shuffle(cells)

        def bt(i):
            if i >= len(kinds):
                return True
            kind = kinds[i]
            for cell in cells:
                if any(p.cell == cell for p in placements):
                    continue
                ok, _ = self.can_place(placements, kind, cell)
                if not ok:
                    continue
                placements.append(Placement(kind, cell[0], cell[1]))
                if bt(i + 1):
                    return True
                placements.pop()
            return False

        #acak urutan jenis agar hasil bervariasi
        order = list(kinds)
        rng.shuffle(order)
        kinds = order
        bt(0)
        return placements

    def solve_with_python_constraint(self, kinds):
        """
        Contoh pemakaian pustaka python-constraint (bila terinstal) untuk
        memverifikasi bahwa domain penempatan masih memuat solusi valid.
        """
        if not HAS_PYTHON_CONSTRAINT:
            return None
        problem = Problem()
        cells = self.candidate_cells([])
        domains = {f"item{i}": list(cells) for i in range(len(kinds))}
        for var, dom in domains.items():
            problem.addVariable(var, dom)
        problem.addConstraint(AllDifferentConstraint())

        def ok(*assign):
            probe = []
            for kind, cell in zip(kinds, assign):
                valid, _ = self.can_place(probe, kind, cell)
                if not valid:
                    return False
                probe.append(Placement(kind, cell[0], cell[1]))
            return True

        problem.addConstraint(ok, list(domains))
        return problem.getSolutions()
