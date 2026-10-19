"""game/ambush/csp_solver.py - Backtracking + MRV/degree + LCV + AC-3/FC.

Solver GENERIK atas CSPProblem supaya bisa diuji pada contoh klasik (X<Y<Z,
pewarnaan peta); squad Tahap 3 adalah satu instansiasi (squad_problem).

Alur backtracking: pilih variabel -> urutkan value -> assign yang konsisten
(unary + biner + partial_ok) -> inferensi -> rekursi -> restore jika gagal.

Semua heuristik bisa dimatikan untuk perbandingan: polos (semua mati) vs
+MRV vs +MRV/degree vs +LCV vs +AC-3 vs forward checking. Urutan value bisa
diacak dengan seed -> CSP menjadi pembangkit seed random restart.

Solusi = complete (semua X terisi) DAN consistent (partial_ok dicek di tiap
assign, jadi solusi yang keluar dijamin keduanya).

Step-mode: run() adalah generator yang yield tiap event; solve() memompa
sampai habis (director fase 4 memompa bertahap per frame agar game tidak
membeku; solver tidak tahu-menahu soal frame).
"""
from __future__ import annotations

import random
import time
from collections import deque
from dataclasses import dataclass
from typing import Any, Callable, Deque, Dict, List, Optional, Tuple

from game.ambush.config import AmbushConfig
from game.ambush.constraints import (
    build_domains,
    check,
    neighbors_of,
    slot_of,
    variable_names,
)
from game.ambush.types import BOSS, EMPTY, HEALER, ITEM_TABLE

INFERENCE_MODES = ("ac3", "fc", "none")


class _TimeUp(Exception):
    """Alasan berhenti paksa: 'time' atau 'nodes'."""


@dataclass
class CSPProblem:
    """Rumus CSP generik: X, D, tetangga, predikat unary/biner/parsial."""

    variables: List[str]
    domains: Dict[str, List[Any]]
    neighbors: Dict[str, List[str]]
    pair_ok: Callable[[str, Any, str, Any], bool]
    unary_ok: Callable[[str, Any], bool] = lambda var, val: True
    partial_ok: Callable[[Dict[str, Any]], bool] = lambda assign: True
    metainfo: Optional[Dict[str, Any]] = None  # konteks pesan alasan


def squad_problem(wins: int, budget: int, cfg: AmbushConfig,
                  queue_rules: bool = False,
                  min_active: int = 1,
                  avoid_roles: Tuple[str, ...] = ()) -> CSPProblem:
    """Bungkus X/D/C squad menjadi CSPProblem untuk solver generik.

    queue_rules/min_active = aturan antrean (Boss terakhir, larangan
    defensif berturutan, peran musuh saling berbeda, min 2 aktif).
    Default False/1 = perilaku BUFF lama; mesin solver tidak berubah,
    hanya predikatnya. avoid_roles = peran pertemuan sebelumnya yang
    sebaiknya tidak muncul lagi (variasi antar-pertemuan).
    """
    variables = variable_names(cfg)

    def unary_ok(var: str, val: str) -> bool:
        if var.startswith("ROLE_") and val == BOSS and wins < cfg.boss_min_wins:
            return False
        # Variasi antar-pertemuan: peran musuh lama keluar dari domain
        # slot manapun (partial: nilai pantangan ditolak sejak awal).
        if queue_rules and avoid_roles and val in avoid_roles:
            return False
        return True

    defensive = {"Healer", "Tank"}

    def pair_ok(xi: str, vi: str, xj: str, vj: str) -> bool:
        ri, rj = xi.startswith("ROLE_"), xj.startswith("ROLE_")
        if ri and rj:
            if vi == HEALER and vj == HEALER:  # biner: maks 1 Healer
                return False
            # Biner: slot kosong tidak di tengah (versi pairwise).
            si, sj = slot_of(xi), slot_of(xj)
            if si < sj and vi == EMPTY and vj != EMPTY:
                return False
            if sj < si and vj == EMPTY and vi != EMPTY:
                return False
            if queue_rules:
                # Antrean: semua peran musuh harus berbeda (diagonal
                # domain; dipangkas pula oleh check() saat komplit).
                if vi != EMPTY and vj != EMPTY and vi == vj:
                    return False
                # Boss-last pairwise: Boss + slot belakang terisi = langgar.
                if si < sj and vi == BOSS and vj != EMPTY:
                    return False
                if sj < si and vj == BOSS and vi != EMPTY:
                    return False
                # Adjacency defensif pairwise (slot bersebelahan saja;
                # canonical + trailing-NONE membuat slot aktif selalu
                # bersebelahan indeks).
                if abs(si - sj) == 1 and vi in defensive and vj in defensive:
                    return False
            return True
        if not ri and not rj:
            # AllDifferent penuh bentuk pairwise: NONE boleh berulang,
            # non-NONE harus saling berbeda.
            if vi == EMPTY or vj == EMPTY:
                return True
            return vi != vj
        # Pasangan role-item hanya bermakna dalam slot yang sama.
        if slot_of(xi) != slot_of(xj):
            return True
        role, item = (vi, vj) if ri else (vj, vi)
        if item != EMPTY and role == EMPTY:
            return False
        return item == EMPTY or role in ITEM_TABLE[item].allowed_roles

    def partial_ok(assign: Dict[str, str]) -> bool:
        # check() menilai partial assignment (variabel tak dikenal di-skip),
        # mencakup pula global budget di tiap langkah.
        return not check(assign, wins, budget, cfg, queue_rules, min_active,
                         avoid_roles)

    return CSPProblem(
        variables=variables,
        domains=build_domains(wins, cfg),
        neighbors={v: neighbors_of(v, cfg) for v in variables},
        pair_ok=pair_ok,
        unary_ok=unary_ok,
        partial_ok=partial_ok,
        metainfo={"wins": wins, "budget": budget, "cfg": cfg,
                  "queue_rules": queue_rules, "min_active": min_active,
                  "avoid_roles": tuple(avoid_roles)},
    )


class CSPSolver:
    """Backtracking search dengan heuristik yang bisa di-toggle."""

    def __init__(
        self,
        problem: CSPProblem,
        use_mrv: bool = True,
        use_degree: bool = True,
        use_lcv: bool = True,
        inference: str = "ac3",
        seed: Optional[int] = None,
        time_limit: float = 2.0,
        max_nodes: int = 50000,
        tracer=None,
    ):
        if inference not in INFERENCE_MODES:
            raise ValueError(f"inference harus salah satu {INFERENCE_MODES}")
        self.problem = problem
        self.use_mrv = use_mrv
        self.use_degree = use_degree
        self.use_lcv = use_lcv
        self.inference = inference
        self.seed = seed
        self.time_limit = time_limit
        self.max_nodes = max_nodes
        self.tracer = tracer
        # Nilai placeholder (slot kosong) dicoba terakhir di _order.
        self.empty_values: Tuple[Any, ...] = ("NONE",)
        self.stats: Dict[str, Any] = {}
        self._solution: Optional[Dict[str, Any]] = None
        self._rng: Optional[random.Random] = None
        self._t0 = 0.0

    # -- driver ------------------------------------------------------
    def run(self):
        """Generator: yield tiap event langkah; solusi ada di self._solution."""
        self._rng = random.Random(self.seed) if self.seed is not None else None
        self._t0 = time.perf_counter()
        self.stats = {
            "nodes": 0, "backtracks": 0, "pruned": 0, "revises": 0,
            "queue_max": 0, "time_ms": 0.0, "stop": "unsatisfiable",
        }
        domains = {}
        for var in self.problem.variables:
            kept = [v for v in self.problem.domains[var]
                    if self.problem.unary_ok(var, v)]
            self.stats["pruned"] += len(self.problem.domains[var]) - len(kept)
            domains[var] = kept
        yield from self._step(
            "csp_start",
            variables=len(self.problem.variables),
            inference=self.inference,
            mrv=self.use_mrv, degree=self.use_degree, lcv=self.use_lcv,
        )
        if any(len(domains[v]) == 0 for v in self.problem.variables):
            yield from self._finish()  # domain awal sudah kosong
            return
        if self.inference == "ac3":
            queue: Deque[Tuple[str, str]] = deque(
                (x, y) for x in self.problem.variables
                for y in self.problem.neighbors[x]
            )
            # Jejak kontribusi pra-pencarian (Fase 2c): FC tak punya fase
            # ini; overlay menampilkannya sebagai "AC-3 pra: hapus N".
            rev0 = (len(self.tracer.of_kind("revise"))
                    if self.tracer is not None else 0)
            pre_pruned = self.stats["pruned"]
            if not (yield from self._ac3(domains, queue)):
                yield from self._finish()
                return
            det = []
            if self.tracer is not None:
                det = [(e["xi"], e["xj"], e["removed"])
                       for e in self.tracer.of_kind("revise")[rev0:][:6]]
            yield from self._step(
                "ac3_pre", removed=self.stats["pruned"] - pre_pruned,
                details=det, queue_max=self.stats["queue_max"],
            )
        try:
            solution = yield from self._bt({}, domains)
        except _TimeUp as stop:
            self.stats["stop"] = str(stop)
            solution = None
        if solution is not None:
            self.stats["stop"] = "solved"
            self._solution = solution
        yield from self._finish()

    def _finish(self):
        self.stats["time_ms"] = (time.perf_counter() - self._t0) * 1000.0
        yield from self._step("csp_done", **self.stats)

    def solve(self) -> Tuple[Optional[Dict[str, Any]], Dict[str, Any]]:
        """Pompa run() sampai habis; kembalikan (solusi, statistik)."""
        for _event in self.run():
            pass
        return self._solution, dict(self.stats)

    def _step(self, kind: str, **data: Any):
        # Tempelkan counter kumulatif di tiap event agar overlay/CSV bisa
        # membaca nodes/backtrack/prune berjalan tanpa merekonstruksi.
        if self.stats:
            data.setdefault("nodes", self.stats["nodes"])
            data.setdefault("backtracks", self.stats["backtracks"])
            data.setdefault("pruned", self.stats["pruned"])
        if self.tracer is not None:
            self.tracer.emit(kind, **data)
        yield {"kind": kind, **data}

    def _check_time(self) -> None:
        if time.perf_counter() - self._t0 > self.time_limit:
            raise _TimeUp("time")
        if self.stats["nodes"] >= self.max_nodes:
            raise _TimeUp("nodes")

    # -- inti backtracking -------------------------------------------
    def _bt(self, assign: Dict[str, Any], domains: Dict[str, List[Any]]):
        self._check_time()
        self.stats["nodes"] += 1
        if len(assign) == len(self.problem.variables):
            return dict(assign)
        var = yield from self._select(assign, domains)
        for val in (yield from self._order(var, assign, domains)):
            # Penolakan dicatat (trace saja, bukan gambar): overlay log
            # butuh baris "X melanggar: <alasan>" (Fase 6). Solver tetap
            # murni: tak ada logika search yang berubah.
            if not self.problem.unary_ok(var, val):
                yield from self._step("reject", var=var, val=val,
                                      reason="unary")
                continue
            other, oval, ok_pair = self._first_clash(var, val, assign)
            if not ok_pair:
                yield from self._step(
                    "reject", var=var, val=val,
                    reason=_pair_reason(var, val, other, oval))
                continue
            assign[var] = val
            if not self.problem.partial_ok(assign):
                violated = ""
                meta = self.problem.metainfo or {}
                if "cfg" in meta and meta["cfg"] is not None:
                    try:
                        from game.ambush.constraints import check as _check
                        bad = _check(assign, meta.get("wins", 0),
                                     meta.get("budget", 0), meta["cfg"],
                                     meta.get("queue_rules", False),
                                     meta.get("min_active", 1))
                        violated = bad[0] if bad else ""
                    except Exception:
                        violated = ""
                del assign[var]
                yield from self._step("reject", var=var, val=val,
                                      reason=violated or "partial")
                continue
            yield from self._step(
                "assign", var=var, val=val, depth=len(assign),
                domain_size=len(domains[var]),
            )
            # Kunci domain variabel yang di-assign menjadi singleton AGAR
            # inferensi (FC/AC-3) melihat assignment. Tanpa ini, revise()
            # memeriksa dukungan terhadap domain penuh (pra-assign) sehingga
            # tak pernah memangkas apa pun (revises selalu 0).
            saved = {v: list(domains[v]) for v in domains}
            domains[var] = [val]
            if self.inference == "fc":
                ok = yield from self._fc(var, assign, domains)
            elif self.inference == "ac3":
                ok = yield from self._ac3_after(var, assign, domains)
            else:
                ok = True
            if ok:
                found = yield from self._bt(assign, domains)
                if found is not None:
                    return found
            for v, old in saved.items():
                domains[v] = old
            del assign[var]
            yield from self._step("restore", var=var, val=val)
        self.stats["backtracks"] += 1
        yield from self._step("backtrack", depth=len(assign))
        return None

    def _pairs_with_assigned(
        self, var: str, val: Any, assign: Dict[str, Any]
    ) -> bool:
        for other, oval in assign.items():
            if not self.problem.pair_ok(var, val, other, oval):
                return False
            if not self.problem.pair_ok(other, oval, var, val):
                return False
        return True

    def _first_clash(self, var: str, val: Any, assign: Dict[str, Any]):
        """Pasangan pertama yang menolak (other, oval, False) atau OK."""
        for other, oval in assign.items():
            if not self.problem.pair_ok(var, val, other, oval):
                return other, oval, False
            if not self.problem.pair_ok(other, oval, var, val):
                return other, oval, False
        return None, None, True

    # -- SELECT-VARIABLE: MRV + degree + urutan tetap -----------------
    def _select(self, assign: Dict[str, Any], domains: Dict[str, List[Any]]):
        cands = [v for v in self.problem.variables if v not in assign]
        if not self.use_mrv:
            var, reason = cands[0], "fixed-order"
        else:
            def key(v: str):
                deg = (
                    sum(1 for n in self.problem.neighbors[v] if n not in assign)
                    if self.use_degree else 0
                )
                return (len(domains[v]), -deg,
                        self.problem.variables.index(v))

            ranked = sorted(cands, key=key)
            var = ranked[0]
            mrv = len(domains[var])
            deg = sum(1 for n in self.problem.neighbors[var]
                      if n not in assign)
            reason = f"mrv={mrv}" + (f",deg={deg}" if self.use_degree else "")
        yield from self._step(
            "select", var=var, reason=reason,
            domain_size=len(domains[var]),
            domains={v: len(domains[v]) for v in cands},
        )
        return var

    # -- ORDER-VALUES: LCV (tie = non-NONE dulu, lalu acakan seed) ----
    def _order(self, var: str, assign: Dict[str, Any],
               domains: Dict[str, List[Any]]):
        vals = list(domains[var])
        if self._rng is not None:
            self._rng.shuffle(vals)  # seed -> tie-break acak (random restart)
        # NONE terakhir: nilai placeholder selalu dicoba paling akhir.
        # Tanpa ini LCV sistematis memilih NONE untuk variabel ITEM yang
        # di-assign sebelum ROLE-nya (NONE tak membuang apa pun), sehingga
        # seed CSP lahir tanpa item. Berlaku generik untuk nilai placeholder
        # apa pun di self.empty_values (xyz/pewanaan peta tak terpengaruh).
        vals = ([v for v in vals if v not in self.empty_values]
                + [v for v in vals if v in self.empty_values])
        scored = []
        if self.use_lcv:
            # LCV: untuk tiap value, hitung opsi tetangga yang dibuang.
            # Semakin sedikit dibuang, semakin dulu dicoba. Pengecualian:
            # placeholder (NONE) SELALU terakhir walau removed=0 — NONE
            # memang paling tidak membatasi, tetapi seed tanpa item membuat
            # local search lumpuh setengah variabel (peraturan Tahap 3).
            # Ordering tak memengaruhi kebenaran (solusi tetap complete +
            # consistent), hanya solusi mana yang ditemukan dulu.
            for val in vals:
                removed = 0
                for nb in self.problem.neighbors[var]:
                    if nb in assign:
                        continue
                    for nval in domains[nb]:
                        if not self.problem.pair_ok(var, val, nb, nval):
                            removed += 1
                            continue
                        if not self.problem.pair_ok(nb, nval, var, val):
                            removed += 1
                scored.append((removed, val))
            scored.sort(key=lambda item: (item[1] in self.empty_values,
                                          item[0]))  # stabil: tie ikut urutan
            ordered = [val for _, val in scored]
        else:
            scored = [(0, val) for val in vals]
            ordered = vals
        yield from self._step(
            "lcv" if self.use_lcv else "order", var=var,
            candidates=[{"val": v, "removed": r} for r, v in scored],
        )
        return ordered

    # -- INFERENCE: forward checking ----------------------------------
    def _fc(self, var: str, assign: Dict[str, Any],
            domains: Dict[str, List[Any]]):
        val = assign[var]
        for nb in self.problem.neighbors[var]:
            if nb in assign:
                continue
            before = len(domains[nb])
            domains[nb] = [
                w for w in domains[nb]
                if self.problem.pair_ok(var, val, nb, w)
                and self.problem.pair_ok(nb, w, var, val)
            ]
            removed = before - len(domains[nb])
            if removed:
                self.stats["pruned"] += removed
                yield from self._step(
                    "fc_prune", var=nb, removed=removed, left=len(domains[nb])
                )
            if not domains[nb]:
                return False
        return True

    # -- INFERENCE: AC-3 (REVISE + queue arc) --------------------------
    def _ac3_after(self, var: str, assign: Dict[str, Any],
                   domains: Dict[str, List[Any]]):
        queue: Deque[Tuple[str, str]] = deque(
            (nb, var) for nb in self.problem.neighbors[var] if nb not in assign
        )
        return (yield from self._ac3(domains, queue))

    def _ac3(self, domains: Dict[str, List[Any]],
             queue: Deque[Tuple[str, str]]):
        self.stats["queue_max"] = max(self.stats["queue_max"], len(queue))
        while queue:
            xi, xj = queue.popleft()
            removed = self._revise(domains, xi, xj)
            if removed:
                self.stats["pruned"] += removed
                self.stats["revises"] += 1
                yield from self._step(
                    "revise", xi=xi, xj=xj, removed=removed,
                    left=len(domains[xi]), queue=len(queue),
                )
                if not domains[xi]:
                    return False
                # Arc (xk, xi) mungkin terpengaruh penghapusan di xi.
                for xk in self.problem.neighbors[xi]:
                    if xk != xj:
                        queue.append((xk, xi))
                self.stats["queue_max"] = max(
                    self.stats["queue_max"], len(queue)
                )
        return True

    def _revise(self, domains: Dict[str, List[Any]], xi: str, xj: str) -> int:
        """Hapus value xi yang tak punya pasangan konsisten di xj.

        REVISE menegakkan arc-consistency satu arc: value v di D(xi) hanya
        bertahan jika ADA w di D(xj) dengan pair_ok dua arah. Nilai yang
        dihapus pasti tak bisa dipakai di solusi apa pun (sound pruning).
        """
        kept = [
            v for v in domains[xi]
            if any(
                self.problem.pair_ok(xi, v, xj, w)
                and self.problem.pair_ok(xj, w, xi, v)
                for w in domains[xj]
            )
        ]
        removed = len(domains[xi]) - len(kept)
        if removed:
            domains[xi] = kept
        return removed


def _pair_reason(xi: str, vi: object, xj: str, vj: object) -> str:
    """Alasan manusiawi untuk pasangan yang ditolak pair_ok (trace log)."""
    from game.ambush.constraints import slot_of
    from game.ambush.types import EMPTY
    ri, rj = xi.startswith("ROLE_"), xj.startswith("ROLE_")
    if ri and rj:
        if vi == "Healer" and vj == "Healer":
            return "maks 1 Healer"
        si, sj = slot_of(xi), slot_of(xj)
        if vi == "Boss" and sj > si and vj != EMPTY:
            return "Boss bukan slot terakhir"
        if vj == "Boss" and si > sj and vi != EMPTY:
            return "Boss bukan slot terakhir"
        if abs(si - sj) == 1 and vi in ("Healer", "Tank") \
                and vj in ("Healer", "Tank"):
            return f"{vi}-{vj} berturutan (defensif ganda)"
        if (si < sj and vi == EMPTY and vj != EMPTY) or (
                sj < si and vj == EMPTY and vi != EMPTY):
            return "slot kosong di tengah"
        return "pasangan ROLE"
    if not ri and not rj:
        return "item harus berbeda" if vi != EMPTY and vj != EMPTY else "pair"
    role, item = (vi, vj) if ri else (vj, vi)
    return f"{role} tak kompatibel {item}" if item != EMPTY else "pair"
