"""game/ambush/local_search.py - Hill climbing, simulated annealing, GA.

State = SquadConfig valid. Objective = |difficulty - target| (difficulty_gap).
Setiap neighbour dicek constraints.is_consistent SEBELUM dievaluasi; yang
gagal dihitung sebagai rejected_by_constraint (angka untuk overlay).

Catatan move: selain 3 move wajib spek (ganti role, tukar item, tambah/kurang
anggota) ada move GantiItem per slot. Alasannya: tanpa move ini item tidak
pernah bisa dioptimasi bila seed CSP ber-item NONE (swap saja tak cukup),
sehingga local search lumpuh untuk setengah variabel ITEM.
"""
from __future__ import annotations

import math
import random
import time
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple

from game.ambush.config import AmbushConfig
from game.ambush.constraints import check, partial_cost
from game.ambush.difficulty import SquadEvaluator, difficulty_gap
from game.ambush.types import (
    BOSS,
    EMPTY,
    HEALER,
    ITEM_TABLE,
    MINION,
    ROLE_TABLE,
    SquadConfig,
)

EPS = 1e-12  # toleransi perbandingan float agar equal terdeteksi stabil


@dataclass
class LSResult:
    """Hasil satu run local search (satu jenis angka untuk overlay + CSV)."""

    algo: str
    best: SquadConfig
    best_diff: float
    best_gap: float
    iters: int = 0
    evals: int = 0
    rejected: int = 0
    restarts: int = 1
    stop: str = ""
    history: List[Tuple[int, float, float]] = field(default_factory=list)
    extra: Dict = field(default_factory=dict)


def _assign_of(squad: SquadConfig, cfg: AmbushConfig) -> Dict[str, str]:
    out = {}
    for i, (role, item) in enumerate(zip(squad.roles, squad.items), 1):
        out[f"ROLE_{i}"] = role
        out[f"ITEM_{i}"] = item
    return out


def _mode_roles(cfg: AmbushConfig) -> List[str]:
    """Peran pada mode aktif (Minion HANYA di SEQUENTIAL)."""
    return [r for r in ROLE_TABLE if r != EMPTY
            and (cfg.mode == "SEQUENTIAL" or r != MINION)]


def _role_options(slot: int, cfg: AmbushConfig) -> List[str]:
    opts = _mode_roles(cfg)
    if slot != 1:  # Boss hanya di domain slot lead (lihat constraints)
        opts = [r for r in opts if r != BOSS]
    return opts


_ITEM_OPTIONS = [it for it in ITEM_TABLE]  # urutan tetap deterministik


def neighbours(
    squad: SquadConfig, wins: int, budget: int, cfg: AmbushConfig
) -> Tuple[List[SquadConfig], int]:
    """Semua neighbour VALID + jumlah kandidat ditolak constraint.

    Move: (1) ganti role 1 slot, (2) ganti item 1 slot, (3) tukar item 2 slot,
    (4) tambah anggota (append di slot kosong pertama), (5) hapus 1 anggota
    lalu padatkan. Canonical (tanpa lubang) selalu terjaga oleh konstruksi.
    """
    seen: Dict[Tuple[Tuple[str, ...], Tuple[str, ...]], SquadConfig] = {}
    rejected = 0

    def consider(roles: List[str], items: List[str]) -> None:
        nonlocal rejected
        cand = SquadConfig(roles=tuple(roles), items=tuple(items))
        if cand.key() in seen or cand.key() == squad.key():
            return
        if check(_assign_of(cand, cfg), wins, budget, cfg):
            rejected += 1
            return
        seen[cand.key()] = cand

    roles, items = list(squad.roles), list(squad.items)

    for i, role in enumerate(roles):
        if role == EMPTY:
            continue
        # (1) Ganti role: item dipertahankan bila masih kompatibel, else NONE.
        for alt in _role_options(i + 1, cfg):
            if alt == role:
                continue
            r2 = list(roles)
            r2[i] = alt
            i2 = list(items)
            if (i2[i] != EMPTY
                    and alt not in ITEM_TABLE[i2[i]].allowed_roles):
                i2[i] = EMPTY
            consider(r2, i2)
        # (2) Ganti item satu slot.
        for alt_item in _ITEM_OPTIONS:
            if alt_item == items[i]:
                continue
            i2 = list(items)
            i2[i] = alt_item
            consider(roles, i2)

    # (3) Tukar item antar dua slot terisi.
    filled = [i for i, r in enumerate(roles) if r != EMPTY]
    for a in range(len(filled)):
        for b in range(a + 1, len(filled)):
            i, j = filled[a], filled[b]
            if items[i] == items[j]:
                continue
            i2 = list(items)
            i2[i], i2[j] = i2[j], i2[i]
            consider(roles, i2)

    # (4) Tambah anggota di slot kosong pertama (append canonical).
    if EMPTY in roles:
        f = roles.index(EMPTY)
        for alt in _role_options(f + 1, cfg):
            r2 = list(roles)
            r2[f] = alt
            consider(r2, items)

    # (5) Hapus 1 anggota lalu padatkan ke kiri.
    members = [(r, it) for r, it in zip(roles, items) if r != EMPTY]
    for k in range(len(members)):
        rest = members[:k] + members[k + 1 :]
        r2 = [r for r, _ in rest] + [EMPTY] * (cfg.kmax - len(rest))
        i2 = [it for _, it in rest] + [EMPTY] * (cfg.kmax - len(rest))
        consider(r2, i2)

    return list(seen.values()), rejected


# ---------------------------------------------------------------------------
# Hill climbing (steepest-ascent) + sideways + random restart
# ---------------------------------------------------------------------------

def hill_climb(
    start: SquadConfig,
    evaluator: SquadEvaluator,
    target: float,
    wins: int,
    budget: int,
    cfg: AmbushConfig,
    sideways_limit: Optional[int] = None,
    max_iters: Optional[int] = None,
    time_limit: Optional[float] = None,
    tracer=None,
) -> LSResult:
    """Steepest-ascent: tiap iterasi nilai SEMUA neighbour, pindah ke terbaik.

    Berhenti: target tercapai | local maximum (tak ada yang >=) | plateau
    (sideways habis) | iter/time limit.
    """
    if sideways_limit is None:
        sideways_limit = cfg.hc_sideways
    if max_iters is None:
        max_iters = cfg.hc_max_iters
    if time_limit is None:
        time_limit = cfg.hc_time_limit
    t0 = time.perf_counter()
    cur = start
    cur_diff = evaluator.evaluate(cur)
    cur_gap = difficulty_gap(cur_diff, target)
    best, best_gap, best_diff = cur, cur_gap, cur_diff
    evals = 1
    rejected = 0
    sideways_left = sideways_limit
    sideways_used = 0
    history = [(0, cur_gap, best_gap)]
    stop = "iter_limit"
    it = 0
    if tracer is not None:
        tracer.emit("ls_start", algo="hill_climbing", start_gap=cur_gap,
                    target=target)
    if best_gap <= cfg.target_tol:
        stop = "target"  # start sudah dalam toleransi: tak ada search
    while stop == "iter_limit" and it < max_iters \
            and time.perf_counter() - t0 < time_limit:
        it += 1
        nbs, rej = neighbours(cur, wins, budget, cfg)
        rejected += rej
        scored = []
        for nb in nbs:
            nb_diff = evaluator.evaluate(nb)
            scored.append((difficulty_gap(nb_diff, target), nb_diff, nb))
        evals += len(nbs)
        if tracer is not None:
            tracer.emit("ls_iter", algo="hill_climbing", it=it,
                        current=cur_gap, best=best_gap, evaluated=len(nbs),
                        rejected=rej, sideways_left=sideways_left)
        if not scored:
            stop = "no_valid_neighbour"
            break
        scored.sort(key=lambda t: t[0])
        top_gap, top_diff, top_nb = scored[0]
        if top_gap < cur_gap - EPS:
            cur, cur_gap, cur_diff = top_nb, top_gap, top_diff
        elif top_gap <= cur_gap + EPS and sideways_left > 0:
            cur, cur_gap, cur_diff = top_nb, top_gap, top_diff
            sideways_left -= 1
            sideways_used += 1
        else:
            stop = ("plateau" if top_gap <= cur_gap + EPS
                    else "local_maximum")
            break
        if top_gap < best_gap:
            best, best_gap, best_diff = cur, top_gap, top_diff
        history.append((it, cur_gap, best_gap))
        if best_gap <= cfg.target_tol:
            stop = "target"
            break
    return LSResult(
        algo="hill_climbing", best=best, best_diff=best_diff,
        best_gap=best_gap, iters=it, evals=evals, rejected=rejected,
        stop=stop, history=history,
        extra={"sideways_used": sideways_used,
               "sideways_limit": sideways_limit},
    )


def random_restart(
    initial_fn: Callable[[int], SquadConfig],
    evaluator: SquadEvaluator,
    target: float,
    wins: int,
    budget: int,
    cfg: AmbushConfig,
    n_restarts: Optional[int] = None,
    tracer=None,
    **hc_kwargs,
) -> LSResult:
    """Jalankan hill_climb dari n start berbeda (seed CSP acak); simpan terbaik."""
    if n_restarts is None:
        n_restarts = cfg.hc_restarts
    overall: Optional[LSResult] = None
    for r in range(n_restarts):
        res = hill_climb(initial_fn(r), evaluator, target, wins, budget,
                         cfg, tracer=tracer, **hc_kwargs)
        res.restarts = n_restarts
        res.algo = "random_restart"
        if tracer is not None:
            tracer.emit("ls_restart", restart=r, best_gap=res.best_gap,
                        stop=res.stop)
        if overall is None or res.best_gap < overall.best_gap - EPS:
            overall = res
        else:
            overall.evals += res.evals
            overall.iters += res.iters
        if overall.best_gap <= cfg.target_tol:
            overall.stop = "target"
            break
    assert overall is not None
    return overall


# ---------------------------------------------------------------------------
# Simulated annealing
# ---------------------------------------------------------------------------

def simulated_annealing(
    start: SquadConfig,
    evaluator: SquadEvaluator,
    target: float,
    wins: int,
    budget: int,
    cfg: AmbushConfig,
    t0: Optional[float] = None,
    cooling: Optional[float] = None,
    tmin: Optional[float] = None,
    max_iters: Optional[int] = None,
    time_limit: Optional[float] = None,
    seed: int = 0,
    tracer=None,
) -> LSResult:
    """Neighbour acak; deltaE = cost_lama - cost_baru (>0 = membaik).

    Langkah buruk diterima dengan probabilitas e^(deltaE/T) memakai sampel
    u ~ Uniform(0,1): terima bila u < p. T <- T * cooling tiap iterasi.
    """
    if t0 is None:
        t0 = cfg.sa_t0
    if cooling is None:
        cooling = cfg.sa_cooling
    if tmin is None:
        tmin = cfg.sa_tmin
    if max_iters is None:
        max_iters = cfg.sa_max_iters
    if time_limit is None:
        time_limit = cfg.sa_time_limit
    rng = random.Random(seed)
    wall = time.perf_counter()
    cur = start
    cur_gap = difficulty_gap(evaluator.evaluate(cur), target)
    best, best_gap = cur, cur_gap
    best_diff = evaluator.evaluate(cur)
    evals = 1
    rejected = 0
    accepted_bad = 0
    history = [(0, cur_gap, best_gap)]
    temp = t0
    stop = "iter_limit"
    it = 0
    if tracer is not None:
        tracer.emit("ls_start", algo="simulated_annealing",
                    start_gap=cur_gap, target=target, t0=t0)
    if best_gap <= cfg.target_tol:
        stop = "target"  # start sudah dalam toleransi: tak ada search
    while stop == "iter_limit" and it < max_iters \
            and time.perf_counter() - wall < time_limit:
        if temp < tmin:
            stop = "cooled"
            break
        it += 1
        nbs, rej = neighbours(cur, wins, budget, cfg)
        rejected += rej
        if not nbs:
            stop = "no_valid_neighbour"
            break
        nb = rng.choice(nbs)
        nb_gap = difficulty_gap(evaluator.evaluate(nb), target)
        evals += 1
        delta_e = cur_gap - nb_gap
        prob = 1.0 if delta_e >= 0 else math.exp(delta_e / temp)
        u = rng.random()
        accepted = delta_e >= 0 or u < prob
        if tracer is not None:
            tracer.emit("ls_sa", it=it, current=cur_gap, best=best_gap,
                        temp=temp, delta_e=delta_e, prob=prob, u=u,
                        accepted=accepted)
        if accepted:
            if delta_e < 0:
                accepted_bad += 1
            cur, cur_gap = nb, nb_gap
            if nb_gap < best_gap:
                best, best_gap = nb, nb_gap
                best_diff = evaluator.evaluate(nb)
        history.append((it, cur_gap, best_gap))
        temp *= cooling
        if best_gap <= cfg.target_tol:
            stop = "target"
            break
    return LSResult(
        algo="simulated_annealing", best=best, best_diff=best_diff,
        best_gap=best_gap, iters=it, evals=evals, rejected=rejected,
        stop=stop, history=history,
        extra={"t_final": temp, "cooling": cooling,
               "accepted_bad": accepted_bad},
    )


# ---------------------------------------------------------------------------
# Genetic algorithm
# ---------------------------------------------------------------------------
#
# ENCODING: kromosom = tuple per slot (role_idx, item_idx) atas domain
# berurutan tetap. CROSSOVER single-point ANTAR slot (titik 1..kmax-1)
# bermakna karena tiap gen adalah "kaset anggota utuh": offspring mewarisi
# anggota-anggota utuh dari kedua induk sehingga koherensi role-item dalam
# satu anggota tidak pernah disobek (beda dengan crossover per-bit yang
# bisa memisahkan role dari itemnya). Mutasi mengubah satu gen acak.
#
# INFEASIBLE: default PENALTI fitness = -gap - penalty * n_pelanggaran
# (populasi boleh melintasi daerah infeasible, sederhana, tanpa solver).
# Opsi repair=True memproyeksikan tiap kromosom ke feasible terdekat via
# project_to_feasible (murah, deterministik) lalu menilai gap-nya.

def _role_opts(slot: int, cfg: AmbushConfig) -> List[str]:
    opts = _mode_roles(cfg)
    return opts if slot == 1 else [r for r in opts if r != BOSS]


def encode(squad: SquadConfig, cfg: AmbushConfig) -> Tuple[Tuple[int, int], ...]:
    """Squad -> kromosom indeks (role_idx, item_idx) per slot."""
    chrom = []
    for i, (role, item) in enumerate(zip(squad.roles, squad.items), 1):
        chrom.append((_role_opts(i, cfg).index(role) if role != EMPTY else -1,
                      _ITEM_OPTIONS.index(item)))
    return tuple(chrom)


def decode(chrom: Tuple[Tuple[int, int], ...],
           cfg: AmbushConfig) -> SquadConfig:
    """Kromosom -> squad (indeks -1 = slot NONE)."""
    roles, items = [], []
    for i, (ri, ii) in enumerate(chrom, 1):
        if ri < 0:
            roles.append(EMPTY)
            items.append(EMPTY)
        else:
            roles.append(_role_opts(i, cfg)[ri])
            items.append(_ITEM_OPTIONS[ii])
    return SquadConfig(roles=tuple(roles), items=tuple(items))


def project_to_feasible(squad: SquadConfig, wins: int, budget: int,
                        cfg: AmbushConfig) -> SquadConfig:
    """Proyeksi deterministik ke squad feasible terdekat (untuk repair=True).

    Urutan: item tanpa role -> NONE; Healer kedua+ -> kosong; pasangan
    terlarang -> item NONE; Fang ganda -> NONE; Boss tanpa wins -> Warrior;
    padatkan lubang; bila over-budget kosongkan slot terakhir dulu.
    """
    roles = list(squad.roles)
    items = list(squad.items)
    for i in range(cfg.kmax):
        if roles[i] == EMPTY:
            items[i] = EMPTY
    seen_healer = False
    for i in range(cfg.kmax):
        if roles[i] == HEALER:
            if seen_healer:
                roles[i], items[i] = EMPTY, EMPTY
            seen_healer = True
    for i in range(cfg.kmax):
        if (roles[i] != EMPTY and items[i] != EMPTY
                and roles[i] not in ITEM_TABLE[items[i]].allowed_roles):
            items[i] = EMPTY
    # AllDifferent: item non-NONE ganda -> pertahankan pertama, NONE-kan sisa.
    seen_items = set()
    for i in range(cfg.kmax):
        if items[i] == EMPTY:
            continue
        if items[i] in seen_items:
            items[i] = EMPTY
        seen_items.add(items[i])
    for i in range(cfg.kmax):
        if roles[i] == BOSS and wins < cfg.boss_min_wins:
            roles[i] = "Warrior"
            if "Warrior" not in ITEM_TABLE[items[i]].allowed_roles:
                items[i] = EMPTY
    members = [(r, it) for r, it in zip(roles, items) if r != EMPTY]
    while True:
        cand = SquadConfig(
            roles=tuple([r for r, _ in members]
                        + [EMPTY] * (cfg.kmax - len(members))),
            items=tuple([it for _, it in members]
                        + [EMPTY] * (cfg.kmax - len(members))),
        )
        # Pertahankan minimal 1 anggota (aturan global anti-squad-kosong).
        if partial_cost(_assign_of(cand, cfg)) <= budget or len(members) <= 1:
            return cand
        members.pop()  # kosongkan slot terakhir hingga muat budget


def genetic(
    seeds: List[SquadConfig],
    evaluator: SquadEvaluator,
    target: float,
    wins: int,
    budget: int,
    cfg: AmbushConfig,
    pop_size: Optional[int] = None,
    generations: Optional[int] = None,
    cx_prob: Optional[float] = None,
    mut_prob: Optional[float] = None,
    tour_size: Optional[int] = None,
    penalty: Optional[float] = None,
    repair: Optional[bool] = None,
    seed: int = 0,
    time_limit: Optional[float] = None,
    tracer=None,
) -> LSResult:
    """GA dengan encoding per-slot; fitness = -gap [- penalti]."""
    if pop_size is None:
        pop_size = cfg.ga_pop
    if generations is None:
        generations = cfg.ga_gens
    if cx_prob is None:
        cx_prob = cfg.ga_cx
    if mut_prob is None:
        mut_prob = cfg.ga_mut
    if tour_size is None:
        tour_size = cfg.ga_tour
    if penalty is None:
        penalty = cfg.ga_penalty
    if repair is None:
        repair = cfg.ga_repair
    if time_limit is None:
        time_limit = cfg.ga_time_limit
    rng = random.Random(seed)
    wall = time.perf_counter()

    def fitness_of(chrom) -> Tuple[float, float, int, SquadConfig]:
        squad = decode(chrom, cfg)
        if repair:
            squad = project_to_feasible(squad, wins, budget, cfg)
            nviol = 0
        else:
            nviol = len(check(_assign_of(squad, cfg), wins, budget, cfg))
        gap = difficulty_gap(evaluator.evaluate(squad), target)
        return (-gap - penalty * nviol, gap, nviol, squad)

    def random_chrom():
        chrom = []
        for i in range(1, cfg.kmax + 1):
            if rng.random() < 0.8:  # bias ke slot terisi agar beragam
                chrom.append((rng.randrange(len(_role_opts(i, cfg))),
                              rng.randrange(len(_ITEM_OPTIONS))))
            else:
                chrom.append((-1, _ITEM_OPTIONS.index(EMPTY)))
        return tuple(chrom)

    pop = [encode(s, cfg) for s in seeds[:pop_size]]
    while len(pop) < pop_size:
        pop.append(random_chrom())
    evals = 0
    best_overall: Optional[Tuple[float, SquadConfig, float]] = None
    best_feas: Optional[Tuple[float, SquadConfig, float]] = None
    history = []
    stop = "generations"
    gen = 0
    if tracer is not None:
        tracer.emit("ls_start", algo="genetic", target=target,
                    pop=pop_size, repair=repair)
    for gen in range(1, generations + 1):
        if time.perf_counter() - wall > time_limit:
            stop = "time_limit"
            break
        scored = [fitness_of(ch) for ch in pop]
        evals += len(pop)
        fits = [s[0] for s in scored]
        feas_gaps = [s[1] for s in scored if s[2] == 0]
        for fit, gap, nviol, squad in scored:
            if best_overall is None or fit > best_overall[0]:
                best_overall = (fit, squad, gap)
            if nviol == 0 and (best_feas is None or gap < best_feas[0]):
                best_feas = (gap, squad, gap)
        cur_best_gap = best_feas[0] if best_feas else best_overall[2]
        history.append((gen, cur_best_gap, best_feas[0] if best_feas
                        else best_overall[2]))
        if tracer is not None:
            tracer.emit("ga_gen", gen=gen,
                        best_fit=max(fits), avg_fit=sum(fits) / len(fits),
                        best_gap=cur_best_gap,
                        pop_summary=_pop_summary(scored))
        if best_feas is not None and best_feas[0] <= cfg.target_tol:
            stop = "target"
            break
        # Seleksi turnamen + elitisme 1 + crossover + mutasi.
        elite = max(range(len(pop)), key=lambda i: scored[i][0])
        nxt = [pop[elite]]
        while len(nxt) < pop_size:
            p1 = _tournament(pop, scored, tour_size, rng)
            p2 = _tournament(pop, scored, tour_size, rng)
            c1, c2 = _crossover(p1, p2, cx_prob, rng, cfg)
            nxt.append(_mutate(c1, mut_prob, rng, cfg))
            if len(nxt) < pop_size:
                nxt.append(_mutate(c2, mut_prob, rng, cfg))
        pop = nxt
    if best_feas is not None:
        gap, squad, _ = best_feas
    else:
        _, squad, gap = best_overall  # type: ignore[misc]
    return LSResult(
        algo="genetic", best=squad, best_diff=evaluator.evaluate(squad),
        best_gap=gap, iters=gen, evals=evals, rejected=0,
        stop=stop, history=[(g, c, b) for g, c, b in history],
        extra={"pop_size": pop_size, "repair": repair,
               "feasible_found": best_feas is not None},
    )


def _pop_summary(scored) -> str:
    kinds: Dict[str, int] = {}
    for _, _, nviol, squad in scored:
        key = "ok" if nviol == 0 else "bad"
        kinds[key] = kinds.get(key, 0) + 1
        kinds[squad.leader()] = kinds.get(squad.leader(), 0) + 1
    return ",".join(f"{k}:{v}" for k, v in sorted(kinds.items()))


def _tournament(pop, scored, size: int, rng: random.Random):
    cand = rng.sample(range(len(pop)), min(size, len(pop)))
    return pop[max(cand, key=lambda i: scored[i][0])]


def _crossover(p1, p2, prob: float, rng: random.Random, cfg: AmbushConfig):
    if rng.random() >= prob or cfg.kmax < 2:
        return p1, p2
    point = rng.randrange(1, cfg.kmax)  # titik antar slot 1..kmax-1
    return p1[:point] + p2[point:], p2[:point] + p1[point:]


def _mutate(chrom, prob: float, rng: random.Random, cfg: AmbushConfig):
    out = list(chrom)
    for i in range(1, cfg.kmax + 1):
        if rng.random() >= prob:
            continue
        ri, ii = out[i - 1]
        if rng.random() < 0.5 or ri < 0:
            ri = rng.randrange(len(_role_opts(i, cfg)))
            ii = _ITEM_OPTIONS.index(EMPTY) if rng.random() < 0.3 else ii
        else:
            ii = rng.randrange(len(_ITEM_OPTIONS))
        if ri < 0:
            ii = _ITEM_OPTIONS.index(EMPTY)
        out[i - 1] = (ri, ii)
    return tuple(out)
